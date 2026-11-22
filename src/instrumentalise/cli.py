import argparse

from . import pipeline


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="instrumentalise",
        description="Play a YouTube (Music) playlist with the vocals removed.",
    )
    ap.add_argument("url", help="playlist or video URL")
    ap.add_argument("--shuffle", action="store_true", help="randomise track order")
    args = ap.parse_args()
    pipeline.run(args.url, shuffle=args.shuffle)


if __name__ == "__main__":
    main()
