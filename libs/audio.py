import os
import subprocess
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
import concurrent.futures
from tqdm import tqdm

from binder import init_worker
from libs.metadata import create_filelist
from libs.tui import TUI_WIDTH


def mp3_to_m4b(sequence, mp3_path: str, bitrate: int, output_path: str) -> str:
    """ 
    Converts a list of mp3 files to a single m4b file using ffmpeg.

    Takes a sequence number to name the temporary files, a path to a filelist of mp3 files, 
    the output bitrate, and the output path.
    """
    sequence = f"{sequence:04}" # Zero pad the sequence number to 4 digits

    output_m4b_path = os.path.join(output_path, f"{sequence}-{os.path.splitext(os.path.basename(mp3_path))[0]}.m4b")

    # Convert mp3 to m4b, ignoring any video streams (e.g., cover images)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-y", "-i", mp3_path,
        "-vn", "-c:a", "aac", "-b:a", f"{bitrate}k", "-movflags", "+faststart",
        output_m4b_path
    ]
    subprocess.run(command, check=True)

    return output_m4b_path


def parallel_mp3_to_m4a(files: list, bitrate: int, output_path: str) -> list:
    """
    Creates tasks of two or three mp3 files to convert to m4b files in parallel.
    """
    output_m4b_paths = []

    with concurrent.futures.ProcessPoolExecutor(initializer=init_worker) as executor:
        futures = []
        for i, mp3_path in enumerate(files):
            futures.append(executor.submit(mp3_to_m4b, i, mp3_path, bitrate, output_path))

        # Create a progress bar
        with tqdm(total=len(futures), desc="Processing MP3 to M4B", unit="chapter", ncols=TUI_WIDTH) as pbar:
            for future in concurrent.futures.as_completed(futures):
                output_m4b_paths.append(future.result())
                pbar.update(1)  # Update the progress bar for each completed task

    output_m4b_paths.sort()
    return output_m4b_paths


def concat_audio(files: list, input_path: str, file_type: str) -> str:
    """
    Concatenates m4b files into a single m4b file.
    """
    filelist_path = os.path.join(input_path, "filelist.txt")
    create_filelist(filelist_path, files)

    concat_path = os.path.join(input_path, f"concat{file_type}")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-f", "concat", "-safe", "0",
        "-i", filelist_path, "-c:a", "copy", concat_path
    ]
    subprocess.run(command, check=True)

    return concat_path


def split_mp3(mp3_path: str, mp3_file_list: list, temp_dir: str, split_count: int):
    """ 
    Split an mp3 file into a number of equal length mp3 files. 
    """
    duration = MP3(mp3_path).info.length
    split_duration = duration / split_count

    # Use ffmpeg's segment option to split the file
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", mp3_path,
        "-f", "segment", "-segment_time", str(split_duration), "-c", "copy",
        os.path.join(temp_dir, "part-%04d.mp3")
    ]
    subprocess.run(command, check=True)

    # Collect the split files
    for i in range(split_count):
        split_mp3 = os.path.join(temp_dir, f"part-{i:04}.mp3")
        if os.path.exists(split_mp3):
            mp3_file_list.append(split_mp3)


def chapterize_m4b(m4b_path: str, chapters_path: str, output_path: str) -> None:
    """
    Uses ffmpeg to embed chapters in a m4b file.
    """
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", m4b_path,
        "-i", chapters_path, "-c", "copy", "-map", "0:a", "-map_chapters", "1",
        output_path
    ]
    subprocess.run(command, check=True)
    os.remove(chapters_path)
    os.remove(m4b_path)
