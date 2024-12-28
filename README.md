## Parallel Audiobook Binder
Parallel Audiobook Binder is, as the name implies, a fully parallelized audiobook binder aka MP3 to M4B converter. It supports setting chapters from either MP3 files or from a CUE sheet.

### Features:
- **Parallelized Conversion:** Parallelized audio trancoding from MP3 to M4B/AAC
- **Chapter Support:** Set chapters from CUE sheets or chapterized MP3 files.
- **Sorting Mechanism:** Sort input files by ID3v2 track number if available, or alphabetically if not.
- **Metadata Management:** Extracts and embeds metadata such as author, title, and release date.

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
- Python3
- pip3
- FFmpeg
