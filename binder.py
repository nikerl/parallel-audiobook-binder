import argparse
import multiprocessing
import os
import subprocess
import sys
import signal
import shutil
import time
from tqdm import tqdm
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

import libs.metadata as metadata
import libs.audio as audio
from libs.tui import *


def signal_handler(sig, frame):
    # Only cleanup in the parent process, not in worker processes
    if multiprocessing.current_process().name == 'MainProcess':
        audio.cancel_active_executors()
        audio.terminate_active_processes()
        # Close any tqdm progress bars
        for instance in list(tqdm._instances):
            instance.close()
        
        print('\n\nExiting program...')
        # Attempt to cleanup temporary files
        for _ in range(10):
            try:
                cleanup()
                break
            except PermissionError:
                time.sleep(0.1)

    sys.exit(0)

def init_worker():
    """Initialize worker process to ignore SIGINT"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def convert_chapterized_files(temp_dir_path: str, input_dir: str, bitrate: int):
    """
    Convert to m4b with chapterized files as the source of the chapters
    """
    # Sort mp3 files by track number or alphabetically if no track number is available
    files_mp3: list = metadata.create_sorted_list_of_files(input_dir)

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
    files: list = metadata.create_sorted_list_of_files(input_dir)

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


def check_ffmpeg():
    """Check if ffmpeg is installed and accessible"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.tracebacklimit = 0
        raise Exception(
            "FFmpeg is not installed or not in PATH\n"
            "Please install FFmpeg from https://ffmpeg.org/download.html\n"
            "Or using package manager:\n"
            "  Windows: winget install Gyan.FFmpeg\n"
            "  Linux (deb): sudo apt install ffmpeg\n"
            "  macOS: brew install ffmpeg"
        ) from None


def arg_problems():
    cleanup()
    sys.tracebacklimit = 0
    if os.name == "nt":
        raise Exception(
            "Either no chapter option selected, please use the -c/--chapters argument.\n"
            "Or there are trailing backslashes in the input or output path, remove them.\n"
            "See --help for more information."
        ) from None
    else:
        raise Exception("No chapter option selected, please use the -c/--chapters argument.\nSee --help for more information.")


def cleanup():
    if os.path.isdir(temp_dir_path):
        shutil.rmtree(temp_dir_path)

    # Fix for terminal becoming unresponsive on linux
    if os.name != "nt":
        os.system("stty sane")


def sanitize_filename(filename: str) -> str:
    """Remove or replace illegal characters from filename"""
    # Characters not allowed in Windows filenames
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '-')
    # Remove leading/trailing spaces and dots (Windows doesn't allow these)
    filename = filename.strip('. ')
    return filename


def main() -> None:
    global temp_dir_path; temp_dir_path = ""

    signal.signal(signal.SIGINT, signal_handler)

    check_ffmpeg()

    parser = argparse.ArgumentParser(description='A highly parallelized audiobook binder', epilog='Run without arguments to use the TUI')
    parser.add_argument('-i', '--input', type=str, default='./', help='Path to the input files (optional, default is current directory)')
    parser.add_argument('-o', '--output', type=str, help='Path to the output file (optional, default is same as input)')
    parser.add_argument('-b', '--bitrate', type=int, default=128, help='Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)')
    parser.add_argument('-c', '--chapters', type=str, choices=['files', 'cue', 'none'], help='Set the source for chapter data. Use "files" to use each mp3 file as a chapter, "cue" to get chapter data from a CUE sheet, "none" to not embed chapters')
    try:
        args = parser.parse_args()
    except SystemExit:
        arg_problems()


    if len(sys.argv) == 1:
        args = tui(args)
    else:
        l : int = (TUI_WIDTH - 27) / 2
        print("\n\n" + "%" * int(l) + " Parallel Audiobook Binder " + "%" * int(l))


    if args.chapters is None:
        arg_problems()


    # Resolve relative paths to absolute paths
    args.input = os.path.abspath(args.input)
    if args.output is None:
        args.output = args.input
    else:
        args.output = os.path.abspath(args.output)

    lenght : int = (TUI_WIDTH - 22 - len(os.path.basename(args.input))); l = int(lenght / 2); r = l if lenght % 2 == 0 else l + 1
    print('\n' + '%' * int(l) + f' Converting "{os.path.basename(args.input)}" to M4B ' + '%' * int(r) + '\n')

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
            cleanup()
            sys.tracebacklimit = 0
            raise Exception("No CUE file found, put the CUE file in the root of the book directory,\nor use one of the other options for chapters")
        metadata_dict, chapters_path, concat_m4b_path = convert_cue_sheet(temp_dir_path, cue_sheet_path, args.input, args.bitrate)

    elif args.chapters == 'none':
        metadata_dict, _, concat_m4b_path = convert_no_chapters(temp_dir_path, args.input, args.bitrate)

    print("Embeding metadata")
    metadata_m4b_path = os.path.join(temp_dir_path, "metadata.m4b")
    audio.embed_metadata(concat_m4b_path, metadata_m4b_path, metadata_dict)

    output_file_path = sanitize_filename(metadata_dict['album'])
    if not args.chapters == 'none':
        print("Embedding Chapters")
        chapterize_m4b_path = os.path.join(temp_dir_path, "chapterized.m4b")
        audio.chapterize_m4b(metadata_m4b_path, chapters_path, chapterize_m4b_path)
        shutil.move(chapterize_m4b_path, os.path.join(args.output, f"{output_file_path}.m4b"))
    else:
        shutil.move(metadata_m4b_path, os.path.join(args.output, f"{output_file_path}.m4b"))
    
    cleanup()

    l : int = (TUI_WIDTH - 7) / 2
    print("\n" + "%" * int(l) + " Done! " + "%" * int(l) + "\n")


if __name__ == '__main__':
    main()
