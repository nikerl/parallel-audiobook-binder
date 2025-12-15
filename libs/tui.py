import argparse
import os

global TUI_WIDTH; TUI_WIDTH = 85
PROMPT = ">>> "

def tui(args) -> argparse.Namespace:

    l : int = (TUI_WIDTH - 27) / 2
    print("\n\n" + "%" * int(l) + " Parallel Audiobook Binder " + "%" * int(l))
    
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

    print("\n" + "%" * TUI_WIDTH)

    return args
