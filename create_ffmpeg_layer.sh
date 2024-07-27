wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xf ffmpeg-release-amd64-static.tar.xz
mkdir -p ffmpeg/bin
cp ffmpeg-7.0.1-amd64-static/ffmpeg ffmpeg/bin/
cd ffmpeg
zip -r ../ffmpeg.zip .