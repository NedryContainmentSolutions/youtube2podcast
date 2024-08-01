import os
import boto3
import uuid
import datetime
from datetime import datetime
from dotenv import load_dotenv
import os
import yt_dlp
from loguru import logger
import html
import requests

# Load environment variables from .env file, if present
load_dotenv()

# Access the variables
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
CONTENT_PATH = os.getenv("CONTENT_PATH")
PLAYLIST_URL = os.getenv("PLAYLIST_URL")
WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET")
AUDIO_EXTENSION = "m4a"
MAX_FILES_TO_DOWNLOAD = int(os.getenv("MAX_FILES_TO_DOWNLOAD","2"))

youtube_url_prefix = "https://www.youtube.com/watch?v="
s3_bucket_url = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{CONTENT_PATH}"
log_file_name = "videos_downloaded.txt"
data_folder = "/tmp"
# For yt-dlp's cache
os.environ['XDG_CACHE_HOME'] = '/tmp/yt-dlp/cache'

# Set up the details for the podcast feed
podcast_title = "My YouTube Playlist"
podcast_description = "A list of videos from my YouTube channel."
podcast_siteURL = ""
podcast_image = "logo.png"  # Put this logo image into your S3 bucket
podcast_GUID = ""
podcast_header = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:atom="http://www.w3.org/2005/Atom">'
channel_header = (
    f"<channel>\n<title>{podcast_title}</title>\n"
    f"<description>{podcast_description}</description>\n"
    f"<image>\n<title>{podcast_title}</title>\n"
    f"<url>{s3_bucket_url}{podcast_image}</url>\n</image>\n"
)

output_rss_filename = "podcast.rss"

def download_audio_from_yt_video(url, format_code="140"):
    logger.info("---- Downloading audio")

    ydl_opts = {
        "outtmpl": data_folder + "/%(title)s.%(ext)s",
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
            return ydl.prepare_filename(info_with_audio_extension), info_with_audio_extension["description"], info_with_audio_extension["thumbnail"]

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None


def get_playlist(playlist_url):
    logger.info(f"-- Getting playlist {playlist_url} from YouTube")
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
    logger.info("-- Done")
    return playlist_videos


def get_video_title(url):
    logger.info(f"--- Getting title from: {url}")
    ydl_opts = {}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        video_title = info_dict.get("title", None)
    logger.info("---- Done")
    safe_title = video_title.replace("|", " ")
    encoded_text = html.escape(safe_title)
    return safe_title


def append_to_file(filename, string):
    logger.info(f"--- Logging addition to {data_folder}/{filename}")
    with open(f"{data_folder}/{filename}", "a") as file:
        file.write(string)
        file.write("\n")
        logger.info("---- Done")


def check_if_in_file(filename, string):
    if os.path.exists(f"{data_folder}/{filename}"):
        with open(f"{data_folder}/{filename}", "r") as file:
            file_contents = file.read()
        # Check if the string is present in the file contents
        return string in file_contents
    else:
        logger.info(
            f"File {data_folder}/{filename} does not exist and so we're starting fresh"
        )
        return False


def upload_audio_to_s3(filepath, episode_GUID):
    logger.info(f"---- Uploading {filepath} to AWS")
    # Create an S3 client and upload the file
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.upload_file(
            filepath,
            BUCKET_NAME,
            CONTENT_PATH + episode_GUID + ".mp4a",
        )
        logger.info("---- Done")
        return True
    except Exception as e:
        logger.error(f"-- Failed {str(e)}")
        return False


def upload_file_to_s3(filename):
    logger.info(f"Uploading {filename} to AWS")
    # Create an S3 client and upload the file
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.upload_file(
            f"{data_folder}/{filename}", BUCKET_NAME, CONTENT_PATH + filename
        )
        logger.info("-- Done")
        return True
    except Exception as e:
        logger.error(f"-- Failed {str(e)}")
        return False


def get_file_from_s3(filename):
    logger.info(f"-- Getting {filename} from S3")
    # Create an S3 client and download the file
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3.download_file(
            BUCKET_NAME, CONTENT_PATH + filename, f"{data_folder}/{filename}"
        )
        logger.info("-- Done")
        return True
    except Exception as e:
        logger.error(f"-- Failed {str(e)}")
        return False


def write_rss_file(filename):
    # Logfile format: YouTubeURL | Title | Time/Date | GUID | S3 URL | FileSizeBytes | thumbnail_url | description
    with open(f"{data_folder}/{output_rss_filename}", "w") as output_file:
        output_file.write(podcast_header)
        output_file.write("\n")
        output_file.write(channel_header)

        if os.path.exists(f"{data_folder}/{filename}"):
            # Read the file contents
            with open(f"{data_folder}/{filename}", "r") as input_file:
                # Loop through file
                for line in input_file:
                    # Split the line into a list of words
                    words = line.split("|")
                    output_file.write("<item>\n")
                    output_file.write(f"<title>{words[1]}</title>\n")
                    if(len(words) > 7):
                        output_file.write(f"<description>{words[0]}\n{words[7]}</description>\n")
                    else:
                        output_file.write(f"<description>{words[0]}</description>\n")
                    output_file.write(f"<guid>{words[3]}</guid>\n")
                    output_file.write(f"<pubDate>{words[2]}</pubDate>\n")
                    output_file.write(f'<enclosure url="{words[4]}" type="audio/mpeg" length="{words[5]}"/>\n')
                    if(len(words) > 7):
                        output_file.write(f"<itunes:image>{words[6]}</itunes:image>\n")
                    output_file.write("</item>\n")

        output_file.write("</channel>\n")
        output_file.write("</rss>")
        output_file.close()


def process_videos():    
    logger.info("Get videos from playlist")
    playlist = get_playlist(PLAYLIST_URL)

    logger.info("Get log file from S3")
    get_file_from_s3(log_file_name)
    now = datetime.now()
    new_videos = False
    logger.info("Processing videos from playlist:")
    files_downloaded = 0
    for video in playlist:
        this_video = youtube_url_prefix + video["id"]
        if check_if_in_file(log_file_name, this_video):
            logger.info(f"-- {this_video} - Already got this video, skipping")
        else:
            new_videos = True
            logger.info(f"-- {this_video} - New video to process")
            episode_GUID = str(uuid.uuid4())
            
            logger.info("--- Download audio and process")
            filepath, description, thumbnail_url = download_audio_from_yt_video(this_video)
            description = html.escape(description[:500].replace('|'," ").replace('\n', ' '))

            if not filepath:
                logger.error(f"ERROR: failed to download {this_video}")
            else:
                file_size = os.path.getsize(filepath)
                logger.info("--- Upload audio to S3")
                if upload_audio_to_s3(filepath, episode_GUID):
                    s3_URL = f"{s3_bucket_url}{episode_GUID}.mp4a"
                    title = get_video_title(this_video)
                    # Logfile format: YouTubeURL | Title | Time/Date | GUID | S3 URL | FileSizeBytes | thumbnail_url | description
                    log_entry = (
                        f"{this_video}|"
                        f"{title}|"
                        f"{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}|"
                        f"{episode_GUID}|"
                        f"{s3_URL}|"
                        f"{str(file_size)}|"
                        f"{thumbnail_url}|"
                        f"{description}|"
                    )

                    append_to_file(log_file_name, log_entry)
                    # Post to webhook using WEBHOOK_TARGET
                    if WEBHOOK_TARGET:
                        requests.post(url=WEBHOOK_TARGET, json={"content": f"New clip saved: {title}"})

                    # Updating the RSS every time - less efficient but safer in case lambda times out
                    logger.info("Regenerating RSS file")
                    write_rss_file(log_file_name)
                    if upload_file_to_s3(log_file_name) and upload_file_to_s3(output_rss_filename):
                        logger.info("Updated RSS file uploaded to S3")
                    else:
                        logger.info("Error with RSS file upload to S3")
                    
                    files_downloaded += 1
                    if files_downloaded >= MAX_FILES_TO_DOWNLOAD:
                        logger.info(f"Stopping because MAX_FILES_TO_DOWNLOAD is {MAX_FILES_TO_DOWNLOAD}")
                        break

    # if new_videos:
    #     logger.info("Regenerating RSS file")
    #     write_rss_file(log_file_name)
    #     if upload_file_to_s3(log_file_name) and upload_file_to_s3(output_rss_filename):
    #         logger.info("Updated RSS file uploaded to S3")
    #     else:
    #         logger.info("Error with RSS file upload to S3")
    # else:
    #     logger.info("Nothing new so nothing to do")
    if files_downloaded > 0:
        logger.info(f"Done - downloaded {files_downloaded} files")
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
