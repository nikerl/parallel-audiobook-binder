## Parallel Audiobook Binder
This is a fully parallelized audiobook binder.

### Features:
- Parallelized MP3 to M4B conversion
- Set chapters from either a CUE sheet or chapterized MP3 files
- Sort input files by ID3v2 track number if available, alphabetically if not

### Installation
- Clone the repo
- Install requirements: 
```bash
pip3 install -r requirments.txt
```

### Running the program
Run binder.py using the following command: 
```bash
python3 binder.py [-i INPUT] [-o OUTPUT] [-b BITRATE] -c {mp3files,cue,none}
```

Arguments:

|Argument|Description|
|---|---|
|-h, --help|Show list of arguments|
|-i INPUT, --input INPUT|Path to the input files (optional, default is current directory)|
|-o OUTPUT, --output OUTPUT|Path to the output file (optional, default is same as INPUT)|
|-b BITRATE, --bitrate BITRATE|Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)|
|-c {files,cue,none}, --chapters {files,cue,none}|Set the source for chapter data. Use "files" to use each mp3 file as a chapter, "cue" to get chapter data from a CUE sheet, "none" to not embed chapters (Required)|

### Dependencies
- Python 3
- pip3
- ffmpeg
