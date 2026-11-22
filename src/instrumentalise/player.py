"""Gapless-ish playback: ffmpeg decodes to raw PCM, pw-play (PipeWire) outputs it."""
import subprocess
from pathlib import Path

from . import config
from .ffmpeg import FFMPEG


def play(path: Path) -> None:
    """Block until the file has finished playing. Ctrl-C stops playback cleanly."""
    decode = subprocess.Popen(
        [FFMPEG, "-v", "quiet", "-i", str(path), "-f", "f32le",
         "-ar", str(config.SAMPLE_RATE), "-ac", str(config.CHANNELS), "-"],
        stdout=subprocess.PIPE,
    )
    sink = subprocess.Popen(
        ["pw-play", "--raw", "--format=f32", f"--rate={config.SAMPLE_RATE}",
         f"--channels={config.CHANNELS}", "-"],
        stdin=decode.stdout,
    )
    decode.stdout.close()
    try:
        sink.wait()
    finally:
        for p in (sink, decode):
            if p.poll() is None:
                p.terminate()
        decode.wait()
