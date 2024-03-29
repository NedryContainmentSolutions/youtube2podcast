# youtube2podcast
Python code designed to run on AWS Lambda which will check a YouTube playlist, then download the audio to S3 and host it as a podcast.

## How to configure
0. Create a YouTube playlist to contain the videos you'd like to add to your podcast feed. For example create a playlist called 'Podcast this later'
1. Set the playlist to be publically readable
2. Go to the playlist and copy its URL, something like https://www.youtube.com/playlist?list=AbCdEFgHiJkLmNoPqRsTuVwXyZ
3. Create an AWS S3 bucket
4. Add a logo file to the bucket, eg. 'logo.png'
5. Create a new AWS Lambda function.
6. Create a new execution role and then attach a policy to allow access to the S3 bucket (read and write are needed). See 'sample_policy.json' as an example and remember to update your bucket name.
7. Set the execution timeout to a few minutes.
8. Create a [Lambda layer](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies) for '[pytube](https://pytube.io/)' and attach it to the Lambda function
9. Upload the code from 'youtube2podcast.py' and then update the variables to set your AWS region, the name of your bucket, your playlist URL and any changes to the feed title or description.

At this point you should be able to test the code, add a video to your playlist, deploy and hit 'Test' on the lambda. Your S3 bucket should now contain an m4a audio file, a RSS file for the podcast and an index file.

10. Assuming that worked you need to find a way to trigger your new Lambda. I used [Eventbridge Scheduled events](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html) to trigger the Lambda every 15 mins. Assuming no new videos the code only runs for a few seconds and so you could make it more frequent but I don't know if YouTube has any rate limits.
11. To be able to access the audio files and .RSS file you need to make your S3 bucket public and grant public read access. Use the AWS documentation to do this and ensure you understand how this is set up.
12. Go to your podcast app (I recommend [Overcast](https://overcast.fm/podcasts)) and add the URL of your RSS file as a private podcast feed.

## How to use youtube2podcast
0. Browse YouTube and find a video you'd like to listen to
1. Add the video to your 'Podcast this later' playlist
2. Wait around 15 mins
3. Refresh your podcast app
4. Listen to your new podcast episode

Hopefully this works, I put the code together very quickly and I plan to tidy it up later. I've tested it with [Overcast](https://overcast.fm/podcasts) but it should work with any podcast app.
