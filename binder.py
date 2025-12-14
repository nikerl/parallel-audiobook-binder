import argparse
import multiprocessing
import os
import sys
import signal
import shutil
import time
from tqdm import tqdm
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

import libs.metadata as metadata
import libs.audio as audio
from libs.tui import tui


def signal_handler(sig, frame):
    # Only cleanup in the parent process, not in worker processes
    if multiprocessing.current_process().name == 'MainProcess':
        # Close any tqdm progress bars
        for instance in list(tqdm._instances):
            instance.close()
        
        print('\n\nExiting program...')
        # Attempt to cleanup temporary files
        while True:
            try:
                cleanup()
                break
            except PermissionError:
                time.sleep(0.1)

    sys.exit(0)

def init_worker():
    """Initialize worker process to ignore SIGINT"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def create_filelist(path: str, files: list) -> None:
    """ 
    Create a filelist for ffmpeg to concatenate files.

    Takes python list of file paths and a path to write the list to.
    """
    with open(path, "w") as f:
        for file in files:
            filepath = os.path.abspath(file)
            filepath = filepath.replace("'", "'\\''") # Escape single quotes in file paths
            f.write(f"file '{filepath}'\n")


def create_sorted_list_of_files(path: str) -> list:
    """
    Creates a sorted list of files in a directory of a specific type.

    MP3 files are sorted by ID3v2 track number if available. All other files are sorted 
    by alphabetically by file name
    """

    dir = os.listdir(path)
    _, file_type = os.path.splitext(dir[0])

    numMP3 = 0
    numM4B = 0
    for file in dir:
        if file.endswith(".mp3"): numMP3 += 1
        if file.endswith(".m4b"): numM4B += 1
    if numMP3 > numM4B: file_type = ".mp3"
    else: file_type = ".m4b"

    files = []
    for file in dir:
        full_path = os.path.join(path, file)
        if not os.path.isdir(full_path) and audio.isAudioFile(full_path):
            if file.endswith(file_type):
                files.append(full_path)
            else:
                print("Ignoring: " + file)
    
    files.sort()
    
    if file_type == ".mp3" or file_type == ".m4b":
        files.sort(key=lambda file: metadata.get_track_number(os.path.join(path, file), file_type))

    return files


def convert_chapterized_files(temp_dir_path: str, input_dir: str, bitrate: int):
    """
    Convert to m4b with chapterized files as the source of the chapters
    """
    # Sort mp3 files by track number or alphabetically if no track number is available
    files_mp3: list = create_sorted_list_of_files(input_dir)

    # Extract metadata from the first mp3 file
    print("Extract metadata")
    metadata_dict: dict = metadata.extract_metadata_mp3(files_mp3[0], bitrate)

    # Convert mp3 files to m4a files in parallel
    files_m4b = audio.parallel_mp3_to_m4a(files_mp3, metadata_dict["bitrate"], temp_dir_path)

    # Create a file containing chapter information
    chapters_path: str = os.path.join(temp_dir_path, "chapters.txt")
    metadata.create_chapter_file(files_m4b, chapters_path)

    # Concatenate m4b files into a single m4b file
    concat_m4b_path = audio.concat_audio(files_m4b, temp_dir_path, ".m4b")

    return metadata_dict, chapters_path, concat_m4b_path


def convert_cue_sheet(temp_dir_path: str, cue_sheet_path: str, input_dir: str, bitrate: int):
    """
    Convert to m4b with a cue sheet as the source of the chapters
    """
    files: list = create_sorted_list_of_files(input_dir)

    _, file_type = os.path.splitext(files[0])

    print("Concatonate audio files")
    concat_path = audio.concat_audio(files, temp_dir_path, file_type)

    audio_duration = None
    chapters_path = None

    if file_type == '.mp3':
        print("Extract metadata")
        metadata_dict = metadata.extract_metadata_mp3(files[0], bitrate)
        audio_duration = MP3(concat_path).info.length  # Use concat_path here

        # Split into multiple files for parallel conversion
        split_mp3_list = []
        split_count = multiprocessing.cpu_count() * 2
        audio.split_mp3(concat_path, split_mp3_list, temp_dir_path, split_count)

        # Convert to m4b
        files_m4b = audio.parallel_mp3_to_m4a(split_mp3_list, metadata_dict["bitrate"], temp_dir_path)
        concat_m4b_path = audio.concat_audio(files_m4b, temp_dir_path, ".m4b")

    elif file_type == '.m4b':
        print("Extract metadata")
        metadata_dict = metadata.extract_metadata_m4b(files[0], bitrate)
        audio_duration = MP4(concat_path).info.length  # Use concat_path here
        concat_m4b_path = concat_path

    if cue_sheet_path is not None:
        print("Parsing CUE sheet")  
        chapters_path: str = os.path.join(temp_dir_path, "chapters.txt")
        metadata.parse_cue_sheet(cue_sheet_path, chapters_path, audio_duration)

    return metadata_dict, chapters_path, concat_m4b_path


def convert_no_chapters(temp_dir_path: str, input_dir: str, bitrate: int):
    """
    Convert to m4b without embedding chapters
    """
    return convert_cue_sheet(temp_dir_path, None, input_dir, bitrate)


def cleanup():
    if os.path.isdir(temp_dir_path):
        shutil.rmtree(temp_dir_path)

    # Fix for terminal becoming unresponsive on linux
    if os.name != "nt":
        os.system("stty sane")


def main() -> None:
    global temp_dir_path
    temp_dir_path = ""

    signal.signal(signal.SIGINT, signal_handler)

    parser.add_argument('-i', '--input', type=str, default='./', help='Path to the input files (optional, default is current directory)')
    parser.add_argument('-o', '--output', type=str, help='Path to the output file (optional, default is same as input)')
    parser.add_argument('-b', '--bitrate', type=int, default=128, help='Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)')
    parser.add_argument('-c', '--chapters', type=str, choices=['files', 'cue', 'none'], required=True, help='Set the source for chapter data. Use "files" to use each mp3 file as a chapter, "cue" to get chapter data from a CUE sheet, "none" to not embed chapters')
    args = parser.parse_args()

    # Resolve relative paths to absolute paths
    args.input = os.path.abspath(args.input)
    if args.output is None:
        args.output = args.input
    else:
        args.output = os.path.abspath(args.output)

    print(f'Starting conversion of "{os.path.basename(args.input)}" to M4B')

    # Create temporary directory for processing files
    temp_dir_path = os.path.join(args.input, ".temp")
    os.makedirs(temp_dir_path, exist_ok=True)

    if args.chapters == 'files':
        metadata_dict, chapters_path, concat_m4b_path = convert_chapterized_files(temp_dir_path, args.input, args.bitrate)

    elif args.chapters == 'cue':
        cue_sheet_path = None
        for file in os.listdir(args.input):
            if file.endswith(".cue"):
                cue_sheet_path = os.path.join(args.input, file)
                break
        if cue_sheet_path is None:
            cleanup(temp_dir_path)
            raise Exception("No CUE file found, put the CUE file in the root of the book directory or use one of the other options for chapters")
        metadata_dict, chapters_path, concat_m4b_path = convert_cue_sheet(temp_dir_path, cue_sheet_path, args.input, args.bitrate)

    elif args.chapters == 'none':
        metadata_dict, _, concat_m4b_path = convert_no_chapters(temp_dir_path, args.input, args.bitrate)

    print("Embeding metadata")
    metadata_m4b_path = os.path.join(temp_dir_path, "metadata.m4b")
    metadata.embed_metadata(concat_m4b_path, metadata_m4b_path, metadata_dict)

    if not args.chapters == 'none':
        print("Embedding Chapters")
        chapterize_m4b_path = os.path.join(temp_dir_path, "chapterized.m4b")
        audio.chapterize_m4b(metadata_m4b_path, chapters_path, chapterize_m4b_path)
        shutil.move(chapterize_m4b_path, os.path.join(args.output, f"{metadata_dict['album']}.m4b"))
    else:
        shutil.move(metadata_m4b_path, os.path.join(args.output, f"{metadata_dict['album']}.m4b"))
    
    cleanup()

    print("Done!")


if __name__ == '__main__':
    main()
