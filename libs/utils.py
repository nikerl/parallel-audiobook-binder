import os
import sys
import shutil
import subprocess


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


def arg_problems(temp_dir_path):
    cleanup(temp_dir_path)
    sys.tracebacklimit = 0
    if os.name == "nt":
        raise Exception(
            "Either no chapter option selected, please use the -c/--chapters argument.\n"
            "Or there are trailing backslashes in the input or output path, remove them.\n"
            "See --help for more information."
        ) from None
    else:
        raise Exception("No chapter option selected, please use the -c/--chapters argument.\nSee --help for more information.")


def sanitize_filename(filename: str) -> str:
    """Remove or replace illegal characters from filename"""
    # Characters not allowed in Windows filenames
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '-')
    # Remove leading/trailing spaces and dots (Windows doesn't allow these)
    filename = filename.strip('. ')
    return filename


def cleanup(temp_dir_path):
    if os.path.isdir(temp_dir_path):
        shutil.rmtree(temp_dir_path)

    # Fix for terminal becoming unresponsive on linux
    if os.name != "nt":
        os.system("stty sane")
