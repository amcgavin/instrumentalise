"""YouTube Music search + radio via ytmusicapi (anonymous: no login needed)."""
from ytmusicapi import YTMusic

_yt = YTMusic()


def _seconds(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        total = 0
        for part in value.split(":"):
            total = total * 60 + int(part)
        return float(total)
    return None


def _track(t: dict) -> dict:
    thumbs = t.get("thumbnail") or t.get("thumbnails") or []
    best = max(thumbs, key=lambda x: x.get("width", 0), default=None)
    return {
        "id": t["videoId"],
        "title": t.get("title") or t["videoId"],
        "artist": ", ".join(a["name"] for a in t.get("artists") or [] if a.get("name")) or None,
        "album": (t.get("album") or {}).get("name") if isinstance(t.get("album"), dict) else None,
        "duration": _seconds(t.get("duration_seconds") or t.get("length") or t.get("duration")),
        "thumbnail": best["url"] if best else f"https://i.ytimg.com/vi/{t['videoId']}/hqdefault.jpg",
    }


def search(query: str, limit: int = 15) -> list[dict]:
    results = _yt.search(query, filter="songs")
    return [_track(r) for r in results if r.get("videoId")][:limit]


def radio(video_id: str, limit: int = 50) -> list[dict]:
    """The radio for a song; the seed song comes first."""
    watch = _yt.get_watch_playlist(videoId=video_id, radio=True, limit=limit)
    return [_track(t) for t in watch["tracks"] if t.get("videoId")]
