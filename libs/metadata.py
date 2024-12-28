from math import ceil
import os
import subprocess
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen import MutagenError


def get_track_number(file_path: str, file_type: str) -> int:
    """ 
    Get track number from audio file
    """

    if file_type == ".mp3":
        try:
            audio = EasyID3(file_path)
            track_number = int(audio.get('tracknumber', [0])[0].split('/')[0])
            return track_number
        except Exception:
            return 0
    
    elif file_type == ".m4b":
        try:    
            audio = MP4(file_path)
            track_number = int(audio["trkn"][0][0])
            return track_number
        except Exception:
            return 0


def get_m4b_length(file: str) -> int:
    """
    Get the length of an M4B file in seconds.

    :param file_path: Path to the M4B file.
    :return: Length of the file in 1/10th of seconds.
    """
    audio = MP4(file)
    length: float = int(audio.info.length * 10)
    return length


def create_chapter_file(files: list, chapters_path: str) -> None:
    """
    Creates a file containing chapter information for ffmpeg to embed in a m4b file.
    """
    cumulative_length: float = 0
    with open(chapters_path, "w") as ch:
        ch.write(";FFMETADATA1\n\n")
        for file in files:
            ch.write(f"[CHAPTER]\n")
            ch.write(f"TIMEBASE=1/10\n")
            ch.write(f"START={int(cumulative_length)}\n")
            cumulative_length += get_m4b_length(file)
            ch.write(f"END={int(cumulative_length)}\n")
            title = os.path.splitext(os.path.basename(file))[0][5:]
            ch.write(f"title={title}\n\n")


def get_mp3_bitrate(file: str) -> int:
    try:
        audio = MP3(file)
        bitrate = audio.info.bitrate // 1000
        return bitrate
    except (MutagenError, AttributeError):
        print(f"Warning: Could not retrieve bitrate for {file}. Using default bitrate of 128 kbps.")
        return 128


def extract_metadata_mp3(file: str, bitrate) -> dict:
    """
    Extracts artist, album, and date metadata from an mp3 file.
    """
     # If bitrate is not provided, get the bitrate of the input mp3 files
    if bitrate == -1 or bitrate is None:
        bitrate = get_mp3_bitrate(file)

    try:
        audio = EasyID3(file)
        artist = audio.get('artist', ['Unknown Artist'])[0]
        album = audio.get('album', ['Unknown Album'])[0]
        date = audio.get('date', ['Unknown Date'])[0]
        return {'artist': artist, 'album': album, 'date': date, 'bitrate': bitrate}
    except Exception as e:
        print(f"Error extracting metadata from {file}: {e}")
        sys.stdout.flush()
        return {'artist': 'Unknown Artist', 'album': 'Unknown Album', 'date': 'Unknown Date', 'bitrate': bitrate}


def extract_metadata_m4b(file: str, bitrate: int) -> dict:
    if bitrate == -1 or bitrate is None:
        bitrate = ceil(audio.info.bitrate / 1000)

    audio = MP4(file)
    artist = audio.tags.get("\xa9ART", ["Unknown Artist"])[0]
    album = audio.tags.get("\xa9alb", ["Unknown Album"])[0]
    date = audio.tags.get("\xa9day", ["Unknown Date"])[0]

    return {'artist': artist, 'album': album, 'date': date, 'bitrate': bitrate}


def embed_metadata(input_file: str, output_file: str, metadata: dict) -> None:
    """
    Embeds artist, album, and date metadata in a m4b file.
    """
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", input_file,
        "-c", "copy",
        "-metadata", f'artist={metadata["artist"]}',
        "-metadata", f'album={metadata["album"]}',
        "-metadata", f'date={metadata["date"]}',
        output_file
    ]
    subprocess.run(command, check=True)
    os.remove(input_file)


def parse_cue_sheet(cue_file_path: str, chapters_path: str, audio_length: str):
    """
    Parses a CUE sheet and converts it to a FFMPEG chapter file
    Takes the path to the cue file, the path to the output chapter file, and the length of the audio file
    """
    cue = open(cue_file_path, 'r')
    cueSheet = cue.readlines()
    cue.close()
    
    i = 0
    chapters = []
    while i < len(cueSheet):
        if 'TRACK' in cueSheet[i]:
            i += 1
            chapter = {}
            while(i < len(cueSheet) and 'TRACK' not in cueSheet[i]):
                if 'TITLE' in cueSheet[i]:
                    title = cueSheet[i].strip().split('TITLE ')[1].strip('"')
                    chapter['title'] = title
                if 'INDEX' in cueSheet[i]:
                    duration = cueSheet[i].strip().split(' ')[2]
                    minutes, seconds, frames = duration.split(':')
                    length = float(minutes) * 60 + float(seconds) + float(frames) / 75
                    chapter['length'] = length
                i += 1
            chapters.append(chapter)
            i -= 1
        i += 1    

    with open(chapters_path, "w") as ch:
        ch.write(";FFMETADATA1\n\n")
        for i in range(0, len(chapters)):
            ch.write("[CHAPTER]\n")
            ch.write("TIMEBASE=1/10\n")
            ch.write(f"START={int(chapters[i]['length'] * 10)}\n")
            if i < len(chapters) - 1:
                ch.write(f"END={int(chapters[i+1]['length'] * 10)}\n")
            else:
                ch.write(f"END={int(audio_length * 10)}\n")
            ch.write(f"title={chapters[i]['title']}\n\n")
