import argparse
import os
import shutil
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
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
            f.write(f"file '{os.path.join(os.pardir, file)}'\n")


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


def get_mp3_length(file: str) -> int:
    audio = MP3(file)
    length = int(audio.info.length * 10)
    return length


def create_chapter_file(files: list, chapters_path: str) -> None:
    """
    Creates a file containing chapter information for ffmpeg to embed in a m4b file.
    """
    chapter_file_path = chapters_path
    cumulative_length = 0
    with open(chapter_file_path, "w") as ch:
        ch.write(";FFMETADATA1\n\n")
        for file in files:
            ch.write(f"[CHAPTER]\n")
            ch.write(f"TIMEBASE=1/10\n")
            ch.write(f"START={cumulative_length}\n")
            cumulative_length += get_mp3_length(file)
            ch.write(f"END={cumulative_length}\n")
            ch.write(f"title={os.path.splitext(os.path.basename(file))[0]}\n\n")


def get_mp3_bitrate(file: str) -> int:
    try:
        audio = MP3(file)
        bitrate = audio.info.bitrate // 1000
        return bitrate
    except (MutagenError, AttributeError):
        print(f"Warning: Could not retrieve bitrate for {file}. Using default bitrate of 128 kbps.")
        return 128


def mp3_to_m4a(sequence, filelist_mp3_path: str, bitrate: int, output_path: str) -> str:
    """ 
    Converts a list of mp3 files to a single m4b file usign ffmpeg.

    Takes a sequence number to name the temporary files, a path to a filelist of mp3 files, 
    the output bitrate, and the output path.
    """
    sequence = f"{sequence:04}" # Zero pad the sequence number to 4 digits

    concat_mp3_path = os.path.join(output_path, f"{sequence}-temp.mp3")
    output_m4b_path = os.path.join(output_path, f"{sequence}-temp.m4b")

    # Concatenate mp3 files
    os.system(f'ffmpeg -hide_banner -loglevel error -f concat -safe 0 -i "{filelist_mp3_path}" -c copy "{concat_mp3_path}"')

    # If bitrate is not provided, get the bitrate of the input mp3 files
    if bitrate == -1 or bitrate is None:
        bitrate = get_mp3_bitrate(concat_mp3_path)

    title = os.path.basename(os.getcwd())
    # Convert mp3 to m4b
    os.system(f'ffmpeg -hide_banner -loglevel error -i "{concat_mp3_path}" -c:a aac -b:a {bitrate}k -vn -f mp4 "{output_m4b_path}"')

    # Remove temporary files
    os.remove(concat_mp3_path)
    os.remove(filelist_mp3_path)
    return output_m4b_path


def split_list(lst: list) -> list:
    """ 
    Splits a list into sublists of length 2 or 3.
    """
    remainder = len(lst) % 2
    sublists = []
    start = 0
    for i in range(len(lst) // 2):
        end = start + 2 + (1 if i < remainder else 0)
        sublists.append(lst[start:end])
        start = end

    return sublists
        

def parallel_mp3_to_m4a(files: list, bitrate: int, output_path: str) -> list:
    """
    Creats tasks of two or three mp3 files to convert to m4b files in parallel.
    """
    sublists = split_list(files)
    output_m4b_paths = []

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []
        for i, sublist in enumerate(sublists):
            filelist_mp3_path: str = os.path.join(output_path, f"{i}-filelist.txt")
            create_filelist(filelist_mp3_path, sublist)
            futures.append(executor.submit(mp3_to_m4a, i, filelist_mp3_path, bitrate, output_path))

        # Create a progress bar
        with tqdm(total=len(futures), desc="Processing MP3 to M4A", unit="task") as pbar:
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


def extract_metadata(file: str) -> dict:
    """
    Extracts artist, album, and date metadata from an mp3 file.
    """
    try:
        audio = EasyID3(file)
        artist = audio.get('artist', ['Unknown Artist'])[0]
        album = audio.get('album', ['Unknown Album'])[0]
        date = audio.get('date', ['Unknown Date'])[0]
        return {'artist': artist, 'album': album, 'date': date}
    except Exception as e:
        print(f"Error extracting metadata from {file}: {e}")
        sys.stdout.flush()
        return {'artist': 'Unknown Artist', 'album': 'Unknown Album', 'date': 'Unknown Date'}


def embed_metadata(input_file: str, output_file: str, metadata: dict) -> None:
    """
    Embeds artist, album, and date metadata in a m4b file.
    """
    os.system(f'ffmpeg -hide_banner -loglevel error -i "{input_file}" -c copy -metadata artist="{metadata["artist"]}" -metadata album="{metadata["album"]}" -metadata date="{metadata["date"]}" "{output_file}"')
    os.remove(input_file)



def main() -> None:
    parser = argparse.ArgumentParser(description='Script to process a zip file of CSVs')
    parser.add_argument('-i', '--input', type=str, default='./', help='Path to the mp3 files (optional, default is current directory)')
    parser.add_argument('-o', '--output', type=str, default='./', help='Path to the output file (optional, default is current directory)')
    parser.add_argument('-b', '--bitrate', type=int, default=-1, help='Bitrate of the output m4b file in kb/s (optional, default is same as input mp3 files)')
    parser.add_argument('--no-chapterize', action='store_true', help='Prevent embeding of chapters in m4b file (optional)')
    args = parser.parse_args()

    # Create temporary directory for processing files
    temp_dir_path: str = os.path.join(args.input, ".temp")
    os.makedirs(temp_dir_path, exist_ok=True)

    print("Importing files")
    files_mp3: list = create_sorted_list_of_files(args.input, ".mp3")

    metadata: dict = extract_metadata(files_mp3[0])

    chapters_path: str = os.path.join(temp_dir_path, "chapters.txt")
    create_chapter_file(files_mp3, chapters_path)

    files_m4b = parallel_mp3_to_m4a(files_mp3, args.bitrate, temp_dir_path)

    concat_m4b_path = concat_m4b(files_m4b, temp_dir_path)

    print("Embeding metadata")
    metadata_m4b_path = os.path.join(temp_dir_path, "metadata.m4b")
    embed_metadata(concat_m4b_path, metadata_m4b_path, metadata)

    if not args.no_chapterize:
        chapterize_m4b_path = os.path.join(temp_dir_path, "chapterized.m4b")
        chapterize_m4b(metadata_m4b_path, chapters_path, chapterize_m4b_path)
        shutil.move(chapterize_m4b_path, os.path.join(args.output, f"{metadata["album"]}.m4b"))
    else:
        shutil.move(metadata_m4b_path, os.path.join(args.output, f"{metadata["album"]}.m4b"))
    
    shutil.rmtree(temp_dir_path)

    print("Done")



if __name__ == '__main__':
    main()
