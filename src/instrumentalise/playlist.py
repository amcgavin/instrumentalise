"""Resolve a YouTube / YouTube Music URL to tracks and download their audio."""
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from . import config
from .ffmpeg import FFMPEG


@dataclass(frozen=True)
class Track:
    id: str
    title: str

    @property
    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.id}"


def _opts(**extra) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
        "ffmpeg_location": FFMPEG,
        **extra,
    }


def resolve(url: str) -> list[Track]:
    """Enumerate the tracks of a playlist (or a single video) without downloading."""
    with yt_dlp.YoutubeDL(_opts(extract_flat="in_playlist")) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = info.get("entries") or [info]
    return [Track(id=e["id"], title=e.get("title") or e["id"]) for e in entries if e]


def download(track: Track) -> Path:
    """Download a track's audio as FLAC into the cache (no-op if already there)."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RAW_DIR / f"{track.id}.flac"
    if out.exists():
        return out
    opts = _opts(
        format="bestaudio/best",
        outtmpl=str(config.RAW_DIR / "%(id)s.%(ext)s"),
        noplaylist=True,
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "flac"}],
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([track.url])
    if not out.exists():
        raise RuntimeError(f"download produced no file for {track.id}")
    return out
