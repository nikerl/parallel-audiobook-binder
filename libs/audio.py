import os
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
from libs.metadata import create_filelist
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
    _run_subprocess(command)

    return output_m4b_path


def parallel_mp3_to_m4a(files: list, bitrate: int, output_path: str) -> list:
    """
    Creates tasks of two or three mp3 files to convert to m4b files in parallel.
    """
    output_m4b_paths = []

    with _managed_executor(initializer=init_worker) as executor:
        futures = []
        for i, mp3_path in enumerate(files):
            futures.append(executor.submit(mp3_to_m4b, i, mp3_path, bitrate, output_path))

        # Create a progress bar
        with tqdm(total=len(futures), desc="Processing MP3 to M4B", unit="chapter", ncols=TUI_WIDTH) as pbar:
            for future in concurrent.futures.as_completed(futures):
                try:
                    output_m4b_paths.append(future.result())
                except (concurrent.futures.CancelledError, BrokenProcessPool):
                    break
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
    _run_subprocess(command)

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
    _run_subprocess(command)

    # Collect the split files
    for i in range(split_count):
        split_mp3 = os.path.join(temp_dir, f"part-{i:04}.mp3")
        if os.path.exists(split_mp3):
            mp3_file_list.append(split_mp3)


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
