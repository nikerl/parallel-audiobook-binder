import argparse
import os
import shutil
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen import MutagenError
import concurrent.futures
from tqdm import tqdm


def create_filelist(path: str, files: list) -> None:
    """ 
    Create a filelist for ffmpeg to concatenate files.

    Takes python list of file paths and a path to write the list to.
    """
    with open(path, "w") as f:
        for file in files:
            f.write(f"file '{file}'\n")


def get_track_number(file_path: str) -> int:
    """ 
    Get ID3v2 track number from mp3 file
    """
    try:
        audio = EasyID3(file_path)
        track_number = int(audio.get('tracknumber', [0])[0].split('/')[0])
        return track_number
    except Exception:
        return 0
    

def create_sorted_list_of_files(path: str, file_type: str) -> list:
    """
    Creates a sorted list of files in a directory of a specific type.

    MP3 files are sorted by ID3v2 track number if available. All other files are sorted 
    by alphabetically by file name
    """
    files = []
    for file in os.listdir(path):
        if file.endswith(file_type):
            files.append(os.path.join(path, file))
    
    files.sort()
    
    if file_type == ".mp3":
        files.sort(key=lambda file: get_track_number(os.path.join(path, file)))

    return files


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


def mp3_to_m4a(sequence, mp3_path: str, bitrate: int, output_path: str) -> str:
    """ 
    Converts a list of mp3 files to a single m4b file using ffmpeg.

    Takes a sequence number to name the temporary files, a path to a filelist of mp3 files, 
    the output bitrate, and the output path.
    """
    sequence = f"{sequence:04}" # Zero pad the sequence number to 4 digits

    output_m4b_path = os.path.join(output_path, f"{sequence}-{os.path.splitext(os.path.basename(mp3_path))[0]}.m4b")

    # Convert mp3 to m4b, ignoring any video streams (e.g., cover images)
    os.system(f'ffmpeg -hide_banner -loglevel error -i "{mp3_path}" -vn -c:a aac -b:a {bitrate}k -movflags +faststart "{output_m4b_path}"')

    return output_m4b_path


def parallel_mp3_to_m4a(files: list, bitrate: int, output_path: str) -> list:
    """
    Creates tasks of two or three mp3 files to convert to m4b files in parallel.
    """
    output_m4b_paths = []

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []
        for i, mp3_path in enumerate(files):
            futures.append(executor.submit(mp3_to_m4a, i, mp3_path, bitrate, output_path))

        # Create a progress bar
        with tqdm(total=len(futures), desc="Processing MP3 to M4A", unit="chapter") as pbar:
            for future in concurrent.futures.as_completed(futures):
                output_m4b_paths.append(future.result())
                pbar.update(1)  # Update the progress bar for each completed task

    output_m4b_paths.sort()
    return output_m4b_paths


def concat_m4b(files: list, input_path: str) -> str:
    """
    Concatenates m4b files into a single m4b file.
    """
    filelist_m4b_path = os.path.join(input_path, "m4b_filelist.txt")
    create_filelist(filelist_m4b_path, files)

    concat_m4b_path = os.path.join(input_path, "concat.m4b")
    os.system(f'ffmpeg -hide_banner -loglevel error -f concat -safe 0 -i "{filelist_m4b_path}" -c copy "{concat_m4b_path}"')

    os.remove(filelist_m4b_path)
    for file in files:
        os.remove(file)

    return concat_m4b_path


def chapterize_m4b(m4b_path: str, chapters_path: str, output_path) -> None:
    """
    Uses ffmpeg to embed chapters in a m4b file.
    """
    os.system(f'ffmpeg -hide_banner -loglevel error -i "{m4b_path}" -i "{chapters_path}" -c copy -map 0:a -map_chapters 1 "{output_path}"')
    os.remove(chapters_path)
    os.remove(m4b_path)


def extract_metadata(file: str, bitrate) -> dict:
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


def embed_metadata(input_file: str, output_file: str, metadata: dict) -> None:
    """
    Embeds artist, album, and date metadata in a m4b file.
    """
    os.system(f'ffmpeg -hide_banner -loglevel error -i "{input_file}" -c copy -metadata artist="{metadata["artist"]}" -metadata album="{metadata["album"]}" -metadata date="{metadata["date"]}" "{output_file}"')
    os.remove(input_file)


def main() -> None:
    parser = argparse.ArgumentParser(description='Script to process a zip file of CSVs')
    parser.add_argument('-i', '--input', type=str, required=True, help='Path to a directory containing mp3 files')
    parser.add_argument('-o', '--output', type=str, help='Path to the the output directory (optional, default is same as the input directory)')
    parser.add_argument('-b', '--bitrate', type=int, default=128, help='Bitrate of the output m4b file in kb/s (optional, default is 128k, use "-1" to get the same bitrate as the input mp3 files)')
    parser.add_argument('--no-chapterize', action='store_true', help='Prevent embeding of chapters in m4b file (optional)')
    args = parser.parse_args()

    # Resolve relative paths to absolute paths
    args.input = os.path.abspath(args.input)
    if args.output is None:
        args.output = args.input
    else:
        args.output = os.path.abspath(args.output)

    print(f'Starting conversion of "{os.path.basename(args.input)}" to M4B')

    # Create temporary directory for processing files
    temp_dir_path: str = os.path.join(args.input, ".temp")
    os.makedirs(temp_dir_path, exist_ok=True)

    # Sort mp3 files by track number or alphabetically if no track number is available
    files_mp3: list = create_sorted_list_of_files(args.input, ".mp3")

    # Extract metadata from the first mp3 file
    metadata: dict = extract_metadata(files_mp3[0], args.bitrate)

    # Convert mp3 files to m4a files in parallel
    files_m4b = parallel_mp3_to_m4a(files_mp3, metadata["bitrate"], temp_dir_path)

    # Create a file containing chapter information
    chapters_path: str = os.path.join(temp_dir_path, "chapters.txt")
    create_chapter_file(files_m4b, chapters_path)

    # Concatenate m4b files into a single m4b file
    concat_m4b_path = concat_m4b(files_m4b, temp_dir_path)

    print("Embeding metadata")
    metadata_m4b_path = os.path.join(temp_dir_path, "metadata.m4b")
    embed_metadata(concat_m4b_path, metadata_m4b_path, metadata)

    if not args.no_chapterize:
        chapterize_m4b_path = os.path.join(temp_dir_path, "chapterized.m4b")
        chapterize_m4b(metadata_m4b_path, chapters_path, chapterize_m4b_path)
        shutil.move(chapterize_m4b_path, os.path.join(args.output, f"{metadata['album']}.m4b"))
    else:
        shutil.move(metadata_m4b_path, os.path.join(args.output, f"{metadata['album']}.m4b"))
    
    shutil.rmtree(temp_dir_path)

    print("Done!")


if __name__ == '__main__':
    main()