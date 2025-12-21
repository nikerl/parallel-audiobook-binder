import argparse
import multiprocessing
import os
import sys
import signal
import shutil
import time
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from tqdm import tqdm

import libs.metadata as metadata
import libs.audio as audio
import libs.tui as tui
import libs.utils as utils


def signal_handler(sig, frame):
    """Handle SIGINT signal (Ctrl+C) to cleanup and exit gracefully"""
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
                utils.cleanup(temp_dir_path)
                break
            except PermissionError:
                time.sleep(0.1)

    sys.exit(0)

def init_worker():
    """Initialize worker process to ignore SIGINT"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)




def convert_to_m4b(args, temp_dir_path: str, files: list) -> None:
    _, file_type = os.path.splitext(files[0])
    
    if file_type == '.mp3':
        print("Extracting metadata")
        metadata_dict = metadata.extract_metadata_mp3(files[0], args.bitrate)

        print("Splitting mp3 for parallel conversion")
        split_mp3_list: list[str] = []
        audio.split_mp3_chapters(files, split_mp3_list, temp_dir_path, segment_length=args.granularity)

        print("Converting chapters to m4b")
        m4b_parts_path = audio.convert_chapters(split_mp3_list, metadata_dict["bitrate"], temp_dir_path)

        if args.chapters != "none":
            print("Reconstructing chapters")
            chapters_list: list[str] = audio.reconstruct_chapters(m4b_parts_path, files, temp_dir_path)

    elif file_type == '.m4b':
        print("Extracting metadata")
        metadata_dict = metadata.extract_metadata_m4b(files[0], args.bitrate)
        chapters_list = files


    sorted_chapter_list = metadata.create_sorted_list_of_files(temp_dir_path)
    if args.chapters == "none":
        chapter_file_path = None
    elif args.chapters == "files":
        chapter_file_path = os.path.join(temp_dir_path, "chapters.txt")
        metadata.create_chapter_file(sorted_chapter_list, chapter_file_path)
        
    print("Concatenating m4b chapters")
    concat_m4b_path = os.path.join(temp_dir_path, "concat.m4b")
    audio.concat_audio(sorted_chapter_list, temp_dir_path, concat_m4b_path, 0)

    if args.chapters == "cue":
        cue_sheet_path = None
        for file in os.listdir(args.input):
            if file.endswith(".cue"):
                cue_sheet_path = os.path.join(args.input, file)
                print(f"Found CUE file: {file}")
                break
        if cue_sheet_path is None:
            utils.cleanup(temp_dir_path)
            sys.tracebacklimit = 0
            raise Exception("No CUE file found, put the CUE file in the root of the book directory,\nor use one of the other options for chapters")
        chapter_file_path = os.path.join(temp_dir_path, "chapters.txt")
        metadata.parse_cue_sheet(cue_sheet_path, chapter_file_path, metadata.get_audio_length(concat_m4b_path))

    print("Embeding metadata" + (" and chapters" if chapter_file_path is not None else ""))
    output_name = utils.sanitize_filename(metadata_dict['album'])
    output_file_path = os.path.join(args.output, f"{output_name}.m4b")
    audio.finalize_m4b(concat_m4b_path, output_file_path, metadata_dict, chapter_file_path)



def main() -> None:
    global temp_dir_path; temp_dir_path = ""

    signal.signal(signal.SIGINT, signal_handler)

    utils.check_ffmpeg()

    parser = argparse.ArgumentParser(description='A highly parallelized audiobook binder', epilog='Run without arguments to use the TUI')
    parser.add_argument('-i', '--input', type=str, default='./', help='Path to the input files (optional, default is current directory)')
    parser.add_argument('-o', '--output', type=str, help='Path to the output file (optional, default is same as input)')
    parser.add_argument('-b', '--bitrate', type=int, default=128, help='Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)')
    parser.add_argument('-c', '--chapters', type=str, choices=['files', 'cue', 'none'], help='Set the source for chapter data. Use "files" to use each mp3 file as a chapter, "cue" to get chapter data from a CUE sheet, "none" to not embed chapters')
    parser.add_argument('-g', '--granularity', type=int, default=20, help='Granularity of parallel processing in minutes (optional, default is 20 minutes)')
    try:
        args = parser.parse_args()
    except SystemExit:
        utils.arg_problems(temp_dir_path)

    # If no arguments are provided, launch the TUI
    if len(sys.argv) == 1:
        args = tui.tui(args)
    else:
        # Print program header
        l : int = (tui.TUI_WIDTH - 27) / 2
        print("\n\n" + "%" * int(l) + " Parallel Audiobook Binder " + "%" * int(l))

    # Ensure chapter option is selected
    if args.chapters is None:
        utils.arg_problems(temp_dir_path)

    # Resolve relative paths to absolute paths
    args.input = os.path.abspath(args.input)
    if args.output is None:
        args.output = args.input
    else:
        args.output = os.path.abspath(args.output)

    # Create temporary directory for processing files
    temp_dir_path = os.path.join(args.input, ".temp")
    os.makedirs(temp_dir_path, exist_ok=True)

    # Print conversion header
    lenght : int = (tui.TUI_WIDTH - 22 - len(os.path.basename(args.input))); l = int(lenght / 2); r = l if lenght % 2 == 0 else l + 1
    print('\n' + '%' * int(l) + f' Converting "{os.path.basename(args.input)}" to M4B ' + '%' * int(r) + '\n')


    files: list = metadata.create_sorted_list_of_files(args.input)
    convert_to_m4b(args, temp_dir_path, files)

    utils.cleanup(temp_dir_path)

    l : int = (tui.TUI_WIDTH - 7) / 2
    print("\n" + "%" * int(l) + " Done! " + "%" * int(l) + "\n")


if __name__ == '__main__':
    main()
