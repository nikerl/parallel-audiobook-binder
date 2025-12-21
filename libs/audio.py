import os
import re
import subprocess
import threading
import concurrent.futures
from contextlib import contextmanager
from concurrent.futures.process import BrokenProcessPool
from typing import Sequence
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from tqdm import tqdm

from binder import init_worker
from libs.metadata import create_filelist, set_track_number
from libs.tui import TUI_WIDTH


_process_lock = threading.Lock()
_active_processes = set()
_executor_lock = threading.Lock()
_active_executors = set()

def _register_executor(executor: concurrent.futures.ProcessPoolExecutor) -> None:
    with _executor_lock:
        _active_executors.add(executor)

def _deregister_executor(executor: concurrent.futures.ProcessPoolExecutor) -> None:
    with _executor_lock:
        _active_executors.discard(executor)

def _shutdown_executor(executor: concurrent.futures.ProcessPoolExecutor, wait: bool = True) -> None:
    try:
        executor.shutdown(wait=wait)
    except BrokenProcessPool:
        pass

@contextmanager
def _managed_executor(*args, **kwargs):
    executor = concurrent.futures.ProcessPoolExecutor(*args, **kwargs)
    _register_executor(executor)
    try:
        yield executor
    finally:
        _deregister_executor(executor)
        _shutdown_executor(executor, wait=True)

def _run_subprocess(command: Sequence[str], **kwargs) -> None:
    process = subprocess.Popen(command, **kwargs)
    with _process_lock:
        _active_processes.add(process)
    try:
        process.communicate()
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        with _process_lock:
            _active_processes.discard(process)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)

def terminate_active_processes() -> None:
    with _process_lock:
        processes = list(_active_processes)
    for process in processes:
        if process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass

def cancel_active_executors() -> None:
    with _executor_lock:
        executors = list(_active_executors)
    for executor in executors:
        processes = getattr(executor, "_processes", {})
        for process in processes.values():
            if process.is_alive():
                try:
                    process.kill()
                except Exception:
                    pass
        _shutdown_executor(executor, wait=False)


def mp3_to_m4b(chapter_index, sequence, mp3_path: str, bitrate: int, output_path: str) -> str:
    sequence = f"{sequence:04}" # Zero pad the sequence number to 4 digits

    output_m4b_path = os.path.join(output_path, f"chapter-{chapter_index:04}-part-{sequence:04}.m4b")

    # Convert mp3 to m4b, ignoring any video streams (e.g., cover images)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-y", "-i", mp3_path,
        "-vn", "-c:a", "aac", "-b:a", f"{bitrate}k", "-movflags", "+faststart",
        output_m4b_path
    ]
    _run_subprocess(command)
    return output_m4b_path


def convert_chapters(chapter_parts: list[str], bitrate: int, output_path: str) -> list:
    output_m4b_paths: list[list[str]] = []

    with _managed_executor(initializer=init_worker) as executor:
        futures = []
        for part in chapter_parts:
            part_name = os.path.basename(part)
            chapter_index = int(part_name.split('-')[1])
            sequence = int(part_name.split('-')[3].split('.')[0])
            futures.append(executor.submit(mp3_to_m4b, chapter_index, sequence, part, bitrate, output_path))

        # Create a progress bar
        with tqdm(total=len(futures), desc="Processing MP3 to M4B", unit="parts", ncols=TUI_WIDTH) as pbar:
            for future in concurrent.futures.as_completed(futures):
                try:
                    output_m4b_paths.append(future.result())
                except (concurrent.futures.CancelledError, BrokenProcessPool):
                    break
                pbar.update(1)  # Update the progress bar for each completed task

    output_m4b_paths.sort()

    # Clean up temporary mp3 files
    for file in os.listdir(output_path):
        if file.endswith(".mp3"):
            os.remove(os.path.join(output_path, file))

    return output_m4b_paths


def reconstruct_chapters(m4b_parts: list[str], files: list[str], temp_dir: str) -> list[str]:
    """
    Reconstructs chapters from m4b parts into complete chapter m4b files.
    """
    # Sort the m4b parts into chapters
    chapters_list: list[list[str]] = []
    m4b_parts.sort()
    i: int = 0
    while i < len(m4b_parts):
        part_name1 = os.path.basename(m4b_parts[i])
        chapter_index1 = int(part_name1.split('-')[1])
        chapter: list[str] = []
        chapter.append(m4b_parts[i])
        
        i += 1
        while i < len(m4b_parts):
            part_name2 = os.path.basename(m4b_parts[i])
            chapter_index2 = int(part_name2.split('-')[1])
            
            if chapter_index1 == chapter_index2:
                chapter.append(m4b_parts[i])
                i += 1
            else:
                break
        chapters_list.append(chapter)

    # Concatenate each chapter's parts into a single m4b file
    output_m4b_paths: list[str] = []
    with _managed_executor(initializer=init_worker) as executor:
        futures = []
        for index, chapter in enumerate(chapters_list):
            chapter_name = os.path.basename(files[index]).split('.')[0]
            concat_path = os.path.join(temp_dir, f"{chapter_name}.m4b")

            if len(chapter) == 1:
                # If there's only one part, rename it instead of concatenating
                import shutil
                shutil.move(chapter[0], concat_path)
                output_m4b_paths.append(concat_path)
            else:
                futures.append(executor.submit(concat_audio, chapter, temp_dir, concat_path, index))

        for future in concurrent.futures.as_completed(futures):
            try:
                output_m4b_paths.append(future.result())
            except (concurrent.futures.CancelledError, BrokenProcessPool):
                break

    output_m4b_paths.sort()

    # Clean up temporary m4b part files
    pattern = re.compile(r'^chapter-\d+-part-\d+\.m4b$')
    for file in os.listdir(temp_dir):
        if pattern.match(file):
            os.remove(os.path.join(temp_dir, file))
    
    return output_m4b_paths


def concat_audio(files: list, input_path: str, concat_path: str, chapter_index: int) -> str:
    """
    Concatenates m4b files into a single m4b file.
    """
    filelist_path = os.path.join(input_path, f"filelist-{chapter_index}.txt")
    create_filelist(filelist_path, files)

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-f", "concat", "-safe", "0",
        "-i", filelist_path, "-c:a", "copy", concat_path
    ]
    _run_subprocess(command)

    set_track_number(concat_path, chapter_index + 1, ".m4b")

    return concat_path


def split_mp3_file(mp3_path: str, file_index: int, mp3_file_list: list, temp_dir: str, segment_length: int):
    """ 
    Split an mp3 file into a number of equal length mp3 files. 
    """

    # Use ffmpeg's segment option to split the file
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", mp3_path,
        "-f", "segment", "-segment_time", str(segment_length), "-c", "copy",
        os.path.join(temp_dir, f"chapter-{file_index:04d}-part-%04d.mp3")
    ]
    _run_subprocess(command)


def split_mp3_chapters(files: list, mp3_file_list: list[str], temp_dir: str, segment_length: int):
    """
    Split each chapter in the files list into smaller segments of specified length in minutes.
    """
    # Convert segment length to seconds
    segment_length *= 60

    with _managed_executor(initializer=init_worker) as executor:
        futures = []
        for index, chapter in enumerate(files):
            futures.append(executor.submit(split_mp3_file, chapter, index, [], temp_dir, segment_length))

        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except (concurrent.futures.CancelledError, BrokenProcessPool):
                break

    pattern = re.compile(r'^chapter-\d+-part-\d+\.mp3$')
    for file in os.listdir(temp_dir):
        if pattern.match(file):
            mp3_file_list.append(os.path.join(temp_dir, file))



def finalize_m4b(input_file: str, output_file: str, metadata: dict, chapters_path: str | None = None) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "panic", "-i", input_file]
    if chapters_path:
        command += ["-i", chapters_path]
    command += ["-c", "copy"]
    for key in ("artist", "album", "date"):
        if metadata.get(key):
            command += ["-metadata", f"{key}={metadata[key]}"]
    if chapters_path:
        command += ["-map", "0:a", "-map_chapters", "1"]
    command.append(output_file)
    _run_subprocess(command)
