import argparse
import os

global TUI_WIDTH; TUI_WIDTH = 85
HEADER_FILLER_CHAR = '%'
PROMPT = ">>> "


def print_header(string: str | None = None) -> None:
    if string is None:
        print('\n' + HEADER_FILLER_CHAR * TUI_WIDTH + '\n')
        return
    else:
        lenght: int = (TUI_WIDTH - (len(string)+2)); 
        l = int(lenght / 2); 
        r = l if lenght % 2 == 0 else l + 1
        print('\n' + HEADER_FILLER_CHAR * int(l) + f' {string} ' + HEADER_FILLER_CHAR * int(r) + '\n')


def print_logo() -> None:
    logo = r"""
             ____                 _ _      _                   
            |  _ \ __ _ _ __ __ _| | | ___| |                  
            | |_) / _` | '__/ _` | | |/ _ \ |                  
            |  __/ (_| | | | (_| | | |  __/ |                  
            |_|   \__,_|_|  \__,_|_|_|\___|_|   _                 _    
                       / \  _   _  __| (_) ___ | |__   ___   ___ | | __
                      / _ \| | | |/ _` | |/ _ \| '_ \ / _ \ / _ \| |/ /
                     / ___ \ |_| | (_| | | (_) | |_) | (_) | (_) |   < 
                    /_/   \_\__,_|\__,_|_|\___/|_.__/ \___/ \___/|_|\_\
                                | __ )(_)_ __   __| | ___ _ __                     
                                |  _ \| | '_ \ / _` |/ _ \ '__|                    
                                | |_) | | | | | (_| |  __/ |                       
                                |____/|_|_| |_|\__,_|\___|_|
    """
    print(HEADER_FILLER_CHAR * TUI_WIDTH, end="")
    print(logo)
    print(HEADER_FILLER_CHAR * TUI_WIDTH)


def tui(args) -> argparse.Namespace:

    print_logo()
    
    print("\nPath to the audiobook files. Press Enter for current directory:")
    while True:
        src: str = input(PROMPT)
        if src == "" or os.path.isdir(src):
            args.input = src if src != "" else "./"
            break
        else:
            print("\nInvalid directory. Please enter a valid directory, or leave blank")

    print("\nPath to the output directory. Press Enter for same as source directory:")
    while True:
        dest: str = input(PROMPT)
        if dest == "" or os.path.isdir(dest):
            args.output = dest if dest != "" else args.input
            break
        else:
            print("\nInvalid directory. Please enter a valid directory, or leave blank")
    
    print("\nBitrate of the output m4b file in kb/s. Press Enter for default (128 kb/s):")
    while True:
        bitrate: str = input(PROMPT)
        if bitrate == "":
            args.bitrate = 128
            break
        else:
            try:
                args.bitrate = int(bitrate)
                break
            except ValueError:
                print("\nInvalid bitrate. Please enter a number, or leave blank")

    print("\nSet the source for chapter data.")
    print("  1. files (each file is a chapter)")
    print("  2. cue (CUE sheet provides chapter information)")
    print("  3. none (don't embed chapters)")
    while True:
        chapters: str = input(PROMPT)
        if chapters == "1": args.chapters = "files"; break
        elif chapters == "2": args.chapters = "cue"; break
        elif chapters == "3": args.chapters = "none"; break
        else: print("\nInvalid option. Please enter 1, 2, or 3.")

    print("\nSummary of settings:")
    print(f"Input directory: {args.input}, Output directory: {args.output}, Bitrate: {args.bitrate} kb/s, Chapters: {args.chapters}")

    print_header()

    return args
