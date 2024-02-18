import pytube
import os
import boto3
import uuid
import datetime
import time
from datetime import datetime

# Set up these global variables
aws_region = "" # For example "eu-west-1"
bucket_name = "" # For example "my-podcast-bucket-69"
playlist_url = "" # For example "https://www.youtube.com/playlist?list=AbCdEFgHiJkLmNoPqRsTuVwXyZ"

# These you probably don't need to touch
youtube_url_prefix = "https://www.youtube.com/watch?v="
s3_bucket_url = f'https://{bucket_name}.s3.{aws_region}.amazonaws.com/'
log_file_name = "videos_downloaded.txt"
data_folder = "/tmp"

# Set up the details for the podcast feed
podcast_title = "My Youtube Playlist"
podcast_description = "A list of videos from my YouTube channel."
podcast_siteURL = ""
podcast_image = "logo.png" # Put this logo image into your S3 bucket
podcast_GUID = ""
podcast_header = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\" xmlns:podcast=\"https://podcastindex.org/namespace/1.0\" xmlns:atom=\"http://www.w3.org/2005/Atom\">"  
channel_header = "<channel>\n<title>" + podcast_title + "</title>\n<description>" + podcast_description + "</description>\n<image>\n<title>" + podcast_title + "</title>\n<url>" + s3_bucket_url + podcast_image + "</url>\n</image>\n"
output_rss_filename = "podcast.rss"

def getListOfVideos(playlist_url):
    print("-- Getting playlist " + playlist_url + " from YouTube")
    playlist = pytube.Playlist(playlist_url)
    print("-- Done")
    return(playlist)

def getAudioFromYoutubeVideo(video_url):
    print("---- Downloading audio")
    from pytube import YouTube
    yt=YouTube(video_url)
    t=yt.streams.filter(only_audio=True)
    t[0].download(data_folder)
    print("---- Done")
    return '' + t[0].default_filename + ''

def getTitleFromYoutubeVideo(video_url):
    print("--- Getting title from: " + video_url)
    from pytube import YouTube
    yt=YouTube(video_url)
    video_title = yt.title
    video_title = video_title.replace("|", " ")
    video_title = video_title.replace("&", "&amp;")
    video_title = video_title.replace("<", "&lt;")
    video_title = video_title.replace(">", "&gt;")
    video_title = video_title.replace("'", "&apos;")
    video_title = video_title.replace("\"", "&quot;")
    video_title = video_title.replace("©", "&#xA9;")
    video_title = video_title.replace("℗", "&#x2117;")
    video_title = video_title.replace("™", "&#x2122;")
    print("---- Done")
    return video_title

# You could use this to set the time/date of the podcast to match the video upload time/date
# I preferred to use the runtime do that podcasts appeared as 'current' correctly
def getDatetimeFromYoutubeVideo(video_url):
    print("--- Getting datetime from: " + video_url)
    from pytube import YouTube
    yt=YouTube(video_url)
    print("---- Done")
    return yt.publish_date.strftime("%a, %d %b %Y %H:%M:%S +0000")

def appendToFile(filename, string):
  print("--- Logging addition to " + data_folder + "/" + filename)
  with open(data_folder + "/" + filename, "a") as file:
    file.write(string)
    file.write("\n")
    print("---- Done")

def checkInsideFile(filename, string):
    if os.path.exists(data_folder + "/" + filename):
        # Read the file contents
        with open(data_folder + "/" + filename, "r") as file:
            file_contents = file.read()
        
        # Check if the string is present in the file contents
        return string in file_contents
    else:
        print("File " + data_folder + "/" + filename + " does not exist and so we're starting fresh")
        return False
    
def uploadAudioToS3(filename, episode_GUID):
    print("---- Uploading " + filename + " to AWS")
    # Create an S3 client and upload the file
    s3 = boto3.client("s3", region_name=aws_region)
    try:
        s3.upload_file(data_folder + "/" + filename, bucket_name, episode_GUID + ".mp4a")
        print("---- Done")
        return True
    except Exception as e: 
        print("---- Failed")
        print(e)
        return False

def uploadFiletoS3(filename):
    print("Uploading " + filename + " to AWS")
    # Create an S3 client and upload the file
    s3 = boto3.client("s3", region_name=aws_region)
    try:
        s3.upload_file(data_folder + "/" + filename, bucket_name, filename)
        print("-- Done")
        return True
    except Exception as e: 
        print("-- Failed")
        print(e)
        return False

def getFileFromS3(filename):
    print("-- Getting " + filename + " from S3")
    # Create an S3 client and download the file
    s3 = boto3.client("s3", region_name=aws_region)
    try:
        s3.download_file(bucket_name, filename, data_folder + "/" + filename)
        print("-- Done")
        return True
    except Exception as e: 
        print(e)
        print("-- Failed")
        return False

def formatDate(datetime):
    return datetime.strftime("%a, %d, %b %Y %H:%M:%S +0000")

def writeRSSFile(filename):
    with open(data_folder + "/" + output_rss_filename, "w") as output_file:
        output_file.write(podcast_header)
        output_file.write("\n")
        output_file.write(channel_header)

        if os.path.exists(data_folder + "/" + filename):
            # Read the file contents
            with open(data_folder + "/" + filename, "r") as input_file:
                # Loop through file
                for line in input_file:
                    # Split the line into a list of words
                    words = line.split("|")
                    output_file.write("<item>\n")
                    output_file.write("<title>" + words[1] + "</title>\n")
                    output_file.write("<description>" + words[0] + "</description>\n")
                    output_file.write("<guid>" + words[3] + "</guid>\n")
                    output_file.write("<pubDate>" + words[2] + "</pubDate>\n")
                    output_file.write("<enclosure url=\"" + words[4] + "\" type=\"audio/mpeg\" length=\"" + str(words[5]) + "\"/>\n")
                    output_file.write("</item>\n")
                
        output_file.write("</channel>\n")
        output_file.write("</rss>")
        output_file.close()

def processVideos():
    print("Get videos from playlist")
    playlist = getListOfVideos(playlist_url)

    print("Get log file from S3")
    getFileFromS3(log_file_name)
    now = datetime.now()
    new_videos = False
    print("Processing videos from playlist:")
    for video in playlist.videos:
        this_video = youtube_url_prefix + video.video_id
        if checkInsideFile(log_file_name, this_video):
            print("-- " + this_video + " - Already got this video, skipping")
        else:
            new_videos = True
            print("-- " + this_video + " - New video to process")
            episode_GUID = str(uuid.uuid4())
            print("--- Download audio and process")
            filename = getAudioFromYoutubeVideo(this_video)
            file_size = os.path.getsize(data_folder + "/" + filename)
            print("--- Upload audio to S3")
            if uploadAudioToS3(filename, episode_GUID):
                s3_URL = s3_bucket_url + episode_GUID + ".mp4a"
                # Logfile format: YouTubeURL | Title | Time/Date | GUID | S3 URL | FileSizeBytes |
                # appendToFile(log_file_name, this_video + "|" + getTitleFromYoutubeVideo(this_video) + "|" + getDatetimeFromYoutubeVideo(this_video)+ "|" + episode_GUID + "|" + s3_URL + "|" + str(file_size) + "|")
                appendToFile(log_file_name, this_video + "|" + getTitleFromYoutubeVideo(this_video) + "|" + formatDate(now) + "|" + episode_GUID + "|" + s3_URL + "|" + str(file_size) + "|")

    if new_videos:
        print("Generating RSS file")
        writeRSSFile(log_file_name)
        if uploadFiletoS3(log_file_name) and uploadFiletoS3(output_rss_filename):
            # All good
            print("All good")
        else:
            print("Error with upload to S3")
    else:
        print("Nothing new so nothing to do")

def lambda_handler(event, context):
    try:
        print('Invoking Lambda')
        print('-=-=-=-=-=-=-=-')
        processVideos()
    except Exception as e:
        print(e)
        raise e
