import argparse
import os


def tui(args) -> argparse.Namespace:
    PROMPT = "\n>>> "


    print("\n\n%%%%%%%%%%%%%%%%%%%%%%%%%%%% Parallel Audiobook Binder %%%%%%%%%%%%%%%%%%%%%%%%%%%%")
    
    print("\nPath to the audiobook files. Press Enter for current directory:", end="")
    while True:
        src: str = input(PROMPT)
        if src == "" or os.path.isdir(src):
            args.input = src if src != "" else "./"
            break
        else:
            print("\nInvalid directory. Please enter a valid directory, or leave blank", end="")

    print("\nPath to the output directory. Press Enter for same as source directory:", end="")
    while True:
        dest: str = input(PROMPT)
        if dest == "" or os.path.isdir(dest):
            args.output = dest if dest != "" else args.input
            break
        else:
            print("\nInvalid directory. Please enter a valid directory, or leave blank", end="")
    
    print("\nBitrate of the output m4b file in kb/s. Press Enter for default (128 kb/s):", end="")
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
                print("\nInvalid bitrate. Please enter a number, or leave blank", end="")

    print("""\nSet the source for chapter data. 
    1. files (each file is a chapter)
    2. cue (CUE sheet provides chapter information)
    3. none (don't embed chapters)""", end="")
    while True:
        chapters: str = input(PROMPT)
        if chapters == "1": args.chapters = "files"; break
        elif chapters == "2": args.chapters = "cue"; break
        elif chapters == "3": args.chapters = "none"; break
        else: print("\nInvalid option. Please enter 1, 2, or 3.", end="")

    return args
