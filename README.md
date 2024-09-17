## Parallel Audiobook Binder
This is a fully parallelized audiobook binder / MP3 to M4B converter.

### Installation
- Clone the repo
- Install requirements: `pip install -r requirments.txt`

### Running the program
Run binder.py using the following command: `python binder.py`

The following optional arguemnts are available:
- -h, --help: Show a list of possible arguments
- -i INPUT, --input INPUT: Path to the mp3 files (optional, default is current directory)
- -o OUTPUT, --output OUTPUT: Path to the output file (optional, default is current directory)
- -b BITRATE, --bitrate BITRATE: Bitrate of the output m4b file in kb/s (optional, default is same as input mp3 files)
- --no-chapterize: Prevent embeding of chapters in m4b file (optional)

### Dependencies
- Python 3
- pip
- ffmpeg
