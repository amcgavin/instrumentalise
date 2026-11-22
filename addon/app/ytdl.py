"""yt-dlp wrapper: enumerate playlists and download raw audio (runs on the home IP)."""
from pathlib import Path

import yt_dlp

from . import config


def _opts(**extra) -> dict:
    return {"quiet": True, "no_warnings": True, "js_runtimes": {"node": {}}, **extra}


def _thumb(entry: dict) -> str | None:
    thumbs = entry.get("thumbnails") or []
    return thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"


def resolve(url: str) -> tuple[str, list[dict]]:
    """Return (playlist title, track dicts) for a playlist or single-video URL."""
    with yt_dlp.YoutubeDL(_opts(extract_flat="in_playlist")) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = [e for e in (info.get("entries") or [info]) if e]
    tracks = [{
        "id": e["id"],
        "title": e.get("title") or e["id"],
        "artist": e.get("artist") or (e.get("artists") or [None])[0] or e.get("channel") or e.get("uploader"),
        "duration": e.get("duration"),
        "thumbnail": _thumb(e),
    } for e in entries]
    return info.get("title") or "Untitled", tracks


def download(track_id: str) -> Path:
    """Download best audio as-is (Opus/AAC, a few MB); the GPU worker decodes it."""
    opts = _opts(format="bestaudio/best", noplaylist=True,
                 outtmpl=str(config.TMP_DIR / "%(id)s.%(ext)s"))
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://music.youtube.com/watch?v={track_id}", download=True)
        return Path(info["requested_downloads"][0]["filepath"])
