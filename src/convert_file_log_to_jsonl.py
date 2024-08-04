import json
import argparse

def convert_to_jsonl(input_file, output_file):
    # Define the field names
    field_names = ["youtube_url", "title", "datetime_str", "guid", "s3_url", "file_size", "description"]

    # Open the input file and output file
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            # Strip the newline character and split the line by '|'
            values = line.strip().split('|')

            # Create a dictionary from the field names and values
            json_obj = dict(zip(field_names, values))

            # Write the JSON object to the output file in JSONL format
            outfile.write(json.dumps(json_obj) + '\n')

    print(f"Conversion complete! Output written to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Convert pipe-separated values to JSONL format.')
    parser.add_argument('--input', type=str, default='/tmp/videos_downloaded.txt',
                        help='Path to the input text file (default: /tmp/videos_downloaded.txt)')
    parser.add_argument('--output', type=str, default='/tmp/videos_downloaded.jsonl',
                        help='Path to the output JSONL file (default: /tmp/videos_downloaded.jsonl)')

    args = parser.parse_args()

    convert_to_jsonl(args.input, args.output)

if __name__ == '__main__':
    main()
