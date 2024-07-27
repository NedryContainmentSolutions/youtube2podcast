rm deployment_package.zip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd $(pip show yt-dlp | grep Location: | cut -d ' ' -f 2)
zip -r ../../../../deployment_package.zip . -x "./botocore/*"
cd ../../../../src
zip ../deployment_package.zip lambda_function.py
cd ..

deactivate
