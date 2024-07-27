# youtube2podcast

Python script to poll a YouTube playlist, download clips as audio and and make them available as an audio podcast. 

Designed to run on AWS Lambda, the code downloads new clips to S3 and updates a podcast.rss file suitable for podcast apps.

## How to configure

0. Create a YouTube playlist to contain the videos you'd like to add to your podcast feed. For example create a playlist called 'Podcast this later'
1. Set the playlist visibility to `Unlisted`
2. Go to the playlist and copy its URL, something like https://www.youtube.com/playlist?list=AbCdEFgHiJkLmNoPqRsTuVwXyZ
3. Create an AWS S3 bucket
4. Optionally, create an obscure folder in the root of the bucket to reduce visibility 
5. Add a logo file to the bucket/folder, eg. 'logo.png'
6. Create a new AWS Lambda function.
7. Create a new execution role and then attach a policy to allow access to the S3 bucket (read and write are needed). See `sample_execution_policy.json` as an example and remember to update your bucket name.
8. Set the execution timeout to a few minutes.
9. Create a [Lambda layer](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies) for ffmpeg (see `create_ffmpeg_layer.sh`) and attach it to the Lambda function
10. Use `build.sh` to package youtube2podcast into a deployment_package.zip and upload as the Lambda code
11. Edit the Lambda's environment variables, optionally including a Webhook URL for notifications

```
AWS_REGION="yr-region-1"
BUCKET_NAME="my-podcast-bucket-01"
CONTENT_PATH="some-obscure-folder-name/"
PLAYLIST_URL="https://www.youtube.com/playlist?list=AbCdEFgHiJkLmNoPqRsTuVwXyZ"
WEBHOOK_TARGET="https://discord.com/api/webhooks/1234567890/somelongstring"
```

12. Test the code:

- Add a video to your YouTube playlist
- Deploy and hit 'Test' on the lambda.
- Your S3 bucket should now contain an m4a audio file, a RSS file for the podcast and an index file.

14. Schedule the Lambda. I used [Eventbridge Scheduled events](https://docs.aws.amazon.com/scheduler/latest/UserGuide/setting-up.html) to trigger the Lambda every 15 mins. Assuming no new videos the code only runs for a few seconds and so you could make it more frequent but I don't know if YouTube has any rate limits.
15. To be able to access the audio files and .RSS file you need to make your S3 bucket public and grant public read access. , See `sample_bucket_policy` in this repo but ensure you understand what you're configuring - refer to the AWS documentation as required.
16. Go to your podcast app (I recommend [Overcast](https://overcast.fm/podcasts)) and add the URL of your RSS file as a private podcast feed.
## How to use youtube2podcast

0. Browse YouTube and find a video you'd like to listen to
1. Add the video to your 'Podcast this later' playlist
2. Wait around 15 mins (depending on your EventBridge schedule)
3. Refresh your podcast app
4. Listen to your new podcast episode
## Notifications

The code will post `{"content": "[video title]"}` to a webhook URL if defined as the WEBHOOK_URL environment variable. This approach works with Discord - which lets you setup a private server for free, resulting in an easy way of getting push notifications on your phone.
## Known Issues

- Currently incompatible with Apple Podcasts (works fine with [Overcast](https://overcast.fm/podcasts) ) - likely an RSS format issue
- YouTube can change often so [yt-dlp]([yt-dlp/yt-dlp: A feature-rich command-line audio/video downloader (github.com)](https://github.com/yt-dlp/yt-dlp)) is updated frequently to handle breaking changes - for this reason, you may need to `pip update` and re-upload the deployment package 

## Troubleshooting

Check CloudWatch for logs output by the Python script. The sample execution policy includes ACLs to let the lambda create a log group in CloudWatch and write to it.

You can also run this code locally and debug using your IDE of choice. Use the AWS CLI to authenticate before execution.

- Clone the repo
- Create src/.env file containing the relevant environment variables (or populate them some other way)
- `pip install -r requirements.txt`, ideally having created a [venv]([venv — Creation of virtual environments — Python 3.12.4 documentation](https://docs.python.org/3/library/venv.html)) first.
- run lambda_function.py

## Release Process

The `.github/workflows/release.yml` workflow file uses `build.sh` to produce a deployment package zip suitable for updating the Lambda.

The workflow runs on push, where there's a semver-based tag

```yml
on:
  push:
    tags: [ 'v*.*.*' ]
```

When ready to create a release, tag your commit (e.g., `git tag v1.0.0` and `git push origin v1.0.0`). This will trigger the workflow, run your `build.sh` script, and publish the resultant `deployment_package.zip` as a release asset.