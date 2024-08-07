import os
import boto3
from botocore.exceptions import ClientError
import uuid
import datetime
from datetime import datetime
from dotenv import load_dotenv
import os
import yt_dlp
from loguru import logger
import html
import requests
import json

# Load environment variables from .env file, if present
load_dotenv()

# Access the variables
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
CONTENT_PATH = os.getenv("CONTENT_PATH")
PLAYLIST_URL = os.getenv("PLAYLIST_URL")
WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET")
AUDIO_EXTENSION = "m4a"
MAX_FILES_TO_DOWNLOAD = int(os.getenv("MAX_FILES_TO_DOWNLOAD", "2"))

CONTENT_PATH += '/' if not CONTENT_PATH.endswith('/') and CONTENT_PATH else ''
youtube_url_prefix = "https://www.youtube.com/watch?v="
s3_bucket_url = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{CONTENT_PATH}"
download_log_filename = "videos_downloaded.jsonl"
working_folder = "/tmp"
# For yt-dlp's cache
os.environ["XDG_CACHE_HOME"] = "/tmp/yt-dlp/cache"

# Set up the details for the podcast feed
podcast_title = "My YouTube Playlist"
podcast_description = "A list of videos from my YouTube channel."
podcast_author = "Me"
podcast_email = "anon@example.com"
podcast_explicit = "no"
podcast_category = "Leisure"
podcast_siteURL = ""
podcast_image = "logo.png"  # Put this logo image into your S3 bucket
podcast_GUID = ""
podcast_header = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:atom="http://www.w3.org/2005/Atom">'

channel_header = (
    f"<channel>\n<title>{podcast_title}</title>\n"
    f"<description>{podcast_description}</description>\n"
    "<link>https://example.com</link>\n"
    "<language>en-us</language>\n"
    f"<itunes:author>{podcast_author}</itunes:author>\n"
    f"<itunes:summary>{podcast_description}</itunes:summary>\n"
    f"<itunes:explicit>{podcast_explicit}</itunes:explicit>\n"
    f'<itunes:category text="{podcast_category}"/>\n'
    f'<itunes:image href="{s3_bucket_url}{podcast_image}"/>\n'
    f"<itunes:owner>\n"
    f"<itunes:name>{podcast_author}</itunes:name>\n"
    f"<itunes:email>{podcast_email}</itunes:email>\n"
    f"</itunes:owner>\n"
    f"<image>\n<title>{podcast_title}</title>\n"
    f"<url>{s3_bucket_url}{podcast_image}</url>\n</image>\n"
)

output_rss_filename = "podcast.rss"


def download_audio_from_yt_video(url, format_code="140"):
    logger.info("Downloading audio")

    ydl_opts = {
        "outtmpl": working_folder + "/%(title)s.%(ext)s",
        "format": format_code,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": AUDIO_EXTENSION,
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Copy info dict and change video extension to audio extension
            info_with_audio_extension = dict(info)
            info_with_audio_extension["ext"] = AUDIO_EXTENSION
            # Return filename with the correct extension
            return (
                ydl.prepare_filename(info_with_audio_extension),
                info_with_audio_extension["description"],
                info_with_audio_extension["uploader"] + " | " + info_with_audio_extension["title"]
            )

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None


def get_playlist(playlist_url):
    logger.info(f"Getting playlist {playlist_url} from YouTube")
    ydl_opts = {
        "quiet": False,
        "extract_flat": True,  # Extract metadata only, no video downloads
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(playlist_url, download=False)
        playlist_videos = []
        for entry in info_dict["entries"]:
            video_info = {"id": entry.get("id", ""), "title": entry.get("title", "")}
            playlist_videos.append(video_info)
    logger.info("Done")
    return playlist_videos


def write_download_log(download_list, filename):
    file_path = f"{working_folder}/{filename}"
    logger.info(f"Logging addition to {file_path}")
    with open(file_path, "w") as file:
        for download in download_list:
            json_line = json.dumps(download)
            file.write(json_line + "\n")
    logger.info("Done")


def append_to_file(filename, string):
    logger.info(f"Logging addition to {working_folder}/{filename}")
    with open(f"{working_folder}/{filename}", "a") as file:
        file.write(string)
        file.write("\n")
        logger.info("Done")


def upload_audio_to_s3(filepath, episode_GUID):
    logger.info(f"Uploading {filepath} to AWS")

    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.upload_file(
            filepath,
            BUCKET_NAME,
            CONTENT_PATH + episode_GUID + ".m4a", ExtraArgs = {'ContentType': 'audio/x-m4a'}
        )
        logger.info("Done, deleting local copy")
        os.remove(filepath)
        return True
    except Exception as e:
        logger.error(f"Failed {str(e)}")
        return False


def upload_file_to_s3(filename):
    logger.info(f"Uploading {filename} to AWS")

    extra_args = {}
    if filename.endswith(".rss"):
        extra_args["ContentType"] = "application/rss+xml"

    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.upload_file(
            f"{working_folder}/{filename}", BUCKET_NAME, CONTENT_PATH + filename, ExtraArgs=extra_args
        )
        logger.info("Done")
        return True
    except Exception as e:
        logger.error(f"Failed {str(e)}")
        return False


def get_download_log(filename):
    objects_list = []

    logger.info(f"Getting {filename} from S3")
    output_path = f"{working_folder}/{filename}"
    s3 = boto3.client("s3", region_name=AWS_REGION)

    try:
        s3.download_file(BUCKET_NAME, CONTENT_PATH + filename, output_path)
        logger.info("Done")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            logger.warning("File does not exist. Assuming first run")
            # return an empty object list
            return []
        else:
            logger.error(f"Failed {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Failed {str(e)}")
        return None

    # Open the JSONL file
    with open(output_path, "r") as infile:
        for line in infile:
            # Parse each line as a JSON object and append to the list
            json_obj = json.loads(line.strip())
            objects_list.append(json_obj)

    return objects_list


def get_file_from_s3(filename):
    logger.info(f"Getting {filename} from S3")
    # Create an S3 client and download the file
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.download_file(
            BUCKET_NAME, CONTENT_PATH + filename, f"{working_folder}/{filename}"
        )
        logger.info("Done")
        return True
    except Exception as e:
        logger.error(f"Failed {str(e)}")
        return False


def generate_rss_file(video_list):
    with open(f"{working_folder}/{output_rss_filename}", "w") as output_file:
        output_file.write(podcast_header)
        output_file.write("\n")
        output_file.write(channel_header)

        for video in video_list:
            output_file.write("<item>\n")
            output_file.write(f"<title>{video['title']}</title>\n")
            output_file.write(f"<link>{video['youtube_url']}</link>\n")
            if ("description" in video) and (video['description'] != ""):
                output_file.write(
                    f"<description>Source: {video['youtube_url']}. {video['description']}</description>\n"
                )
            else:
                output_file.write(f"<description>{video['youtube_url']}</description>\n")
            output_file.write(f"<guid>{video['guid']}</guid>\n")
            output_file.write(f"<pubDate>{video['datetime_str']}</pubDate>\n")
            output_file.write(
                f"<enclosure url=\"{video['s3_url']}\" type=\"audio/x-m4a\" length=\"{video['file_size']}\"/>\n"
            )
            output_file.write("</item>\n")

        output_file.write("</channel>\n")
        output_file.write("</rss>")
        output_file.close()


def process_videos():
    logger.info("Get videos from playlist")
    playlist = get_playlist(PLAYLIST_URL)

    logger.info("Get log file from S3")

    download_list = get_download_log(download_log_filename)
    if download_list is None:
        logger.error("Problem reading jsonl-formatted log from S3")
        return

    now = datetime.now()
    logger.info("Processing videos from playlist:")
    files_downloaded = 0
    for video in playlist:
        current_url = youtube_url_prefix + video["id"]
        if any(obj["youtube_url"] == current_url for obj in download_list):
            logger.info(f"{current_url} - Already got this video, skipping")
            continue

        logger.info(f"{current_url} - New video to process")
        episode_GUID = str(uuid.uuid4())

        logger.info("Download audio and process")
        filepath, description, title = download_audio_from_yt_video(current_url)

        if not filepath:
            logger.error(f"ERROR: failed to download {current_url}")
            continue

        description = html.escape(
            description[:500].replace("|", " ").replace("\n", " ")
        )

        file_size = os.path.getsize(filepath)
        logger.info("Upload audio to S3")
        if not upload_audio_to_s3(filepath, episode_GUID):
            logger.error(f"ERROR: failed to upload to s3 {filepath}")
            continue

        s3_URL = f"{s3_bucket_url}{episode_GUID}.m4a"

        new_download = {
            "youtube_url": current_url,
            "title": title,
            "datetime_str": f"{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}",
            "guid": episode_GUID,
            "s3_url": s3_URL,
            "file_size": str(file_size),
            "description": description,
        }

        download_list.append(new_download)
        write_download_log(download_list, download_log_filename)

        # Post to webhook using WEBHOOK_TARGET
        if WEBHOOK_TARGET:
            requests.post(
                url=WEBHOOK_TARGET,
                json={"content": f"New clip saved: {title}"},
            )

        # Updating the RSS every time - less efficient but safer in case lambda times out
        logger.info("Regenerating RSS file")
        generate_rss_file(download_list)
        if upload_file_to_s3(download_log_filename) and upload_file_to_s3(output_rss_filename):
            logger.info("Updated RSS file uploaded to S3")
        else:
            logger.info("Error with RSS file upload to S3")

        files_downloaded += 1
        if files_downloaded >= MAX_FILES_TO_DOWNLOAD:
            logger.info(
                f"Stopping because MAX_FILES_TO_DOWNLOAD is {MAX_FILES_TO_DOWNLOAD}"
            )
            break

    if files_downloaded > 0:
        # Clean up
        os.remove(working_folder + "/" + download_log_filename)
        os.remove(working_folder + "/" + output_rss_filename)
        logger.info("Working folder cleanup complete.")
        logger.info(f"All done - downloaded {files_downloaded} files")
    else:
        logger.info("Nothing new so nothing to do")


def lambda_handler(event, context):
    try:
        logger.info("Invoking Lambda")
        logger.info("-=-=-=-=-=-=-=-")
        process_videos()
    except Exception as e:
        logger.info(e)
        raise e


if __name__ == "__main__":
    process_videos()

    # Regenerate RSS file even if no changes - for dev/test work only
    """
    logger.info("Regenerating RSS file")
    download_list = get_download_log(download_log_filename)
    generate_rss_file(download_list)
    if upload_file_to_s3(download_log_filename) and upload_file_to_s3(output_rss_filename):
        logger.info("Updated RSS file uploaded to S3")
    else:
        logger.info("Error with RSS file upload to S3")
    """
    
    
