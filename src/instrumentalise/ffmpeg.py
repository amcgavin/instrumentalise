"""Locate the bundled static ffmpeg binary (no system install needed)."""
import shutil

import static_ffmpeg

static_ffmpeg.add_paths()  # puts ffmpeg/ffprobe on PATH for this process
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
