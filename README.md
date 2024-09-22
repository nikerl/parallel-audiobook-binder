## Parallel Audiobook Binder
This is a fully parallelized audiobook binder / MP3 to M4B converter.

### Installation
Install the required pip packages: 
```
pip install -r requirments.txt
```

### Running the program
Run binder.py using the following command: 
```
python binder.py -i INPUT
```

The following arguemnts are available:
- -i INPUT, --input INPUT: Path to the mp3 files (required)
- -o OUTPUT, --output OUTPUT: Path to the output file (optional, default is same as the input directory)
- -b BITRATE, --bitrate BITRATE: Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)
- --no-chapterize: Prevent embeding of chapters in m4b file (optional)
- -h, --help: Show a list of possible arguments

### Dependencies
- Python 3
- pip
- ffmpeg
