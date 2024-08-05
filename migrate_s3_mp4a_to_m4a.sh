#!/bin/bash

# Set variables
BUCKET_NAME="your-bucket-name"
FOLDER_PATH="your-path-here"

# List all *.mp4a files in the bucket/folder
FILES=$(aws s3 ls s3://$BUCKET_NAME/$FOLDER_PATH/ --recursive | awk '{print $4}' | grep '\.mp4a$')

# Loop through each file and perform the required operations
for FILE in $FILES; do
  # Get the base file name without the extension
  BASE_NAME=$(basename "$FILE" .mp4a)
  
  # Construct new file name with .m4a extension
  NEW_FILE="$FOLDER_PATH/$BASE_NAME.m4a"
  
  # Copy the file to the new file name with updated content type
  aws s3 cp \
    s3://$BUCKET_NAME/$FILE \
    s3://$BUCKET_NAME/$NEW_FILE \
    --no-guess-mime-type \
    --content-type="audio/x-m4a" \
    --metadata-directive="REPLACE"

  # Optionally, you can delete the old file if required
  aws s3 rm s3://$BUCKET_NAME/$FILE
done


# Download the JSONL file from S3
aws s3 cp s3://$BUCKET_NAME/$FOLDER_PATH/$LOCAL_JSON_FILE .

# Replace .mp4a with .m4a in the JSONL file
sed -i 's/\.mp4a/\.m4a/g' $LOCAL_JSON_FILE

# Upload the modified JSONL file back to S3
aws s3 cp $LOCAL_JSON_FILE s3://$BUCKET_NAME/$FOLDER_PATH/$LOCAL_JSON_FILE

# Clean up local JSONL file
rm $LOCAL_JSON_FILE