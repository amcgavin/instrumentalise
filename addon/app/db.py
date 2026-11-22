"""Tiny SQLite store: tracks, playlists, and playlist membership."""
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY, title TEXT, artist TEXT, duration REAL, thumbnail TEXT,
    status TEXT NOT NULL DEFAULT 'queued', error TEXT, updated REAL
);
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, title TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL, track_id TEXT NOT NULL REFERENCES tracks(id),
    PRIMARY KEY (playlist_id, position)
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        # work interrupted by a restart goes back in the queue
        c.execute("UPDATE tracks SET status='queued' WHERE status IN ('downloading','separating')")


def set_status(track_id: str, status: str, error: str | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE tracks SET status=?, error=?, updated=? WHERE id=?",
                  (status, error, time.time(), track_id))


def add_playlist(url: str, title: str, tracks: list[dict]) -> int:
    with connect() as c:
        pid = c.execute("INSERT INTO playlists (url, title, created) VALUES (?,?,?)",
                        (url, title, time.time())).lastrowid
        for pos, t in enumerate(tracks):
            # keep status/audio if the track is already known from another playlist
            c.execute(
                "INSERT INTO tracks (id, title, artist, duration, thumbnail, updated) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, artist=excluded.artist, "
                "duration=excluded.duration, thumbnail=excluded.thumbnail",
                (t["id"], t["title"], t["artist"], t["duration"], t["thumbnail"], time.time()),
            )
            c.execute("INSERT INTO playlist_tracks VALUES (?,?,?)", (pid, pos, t["id"]))
    return pid


def get_playlist(pid: int) -> dict | None:
    with connect() as c:
        pl = c.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()
        if not pl:
            return None
        rows = c.execute(
            "SELECT t.* FROM playlist_tracks pt JOIN tracks t ON t.id = pt.track_id "
            "WHERE pt.playlist_id=? ORDER BY pt.position", (pid,)).fetchall()
    return {"id": pl["id"], "url": pl["url"], "title": pl["title"],
            "tracks": [dict(r) for r in rows]}


def list_playlists() -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT p.id, p.title, p.url, COUNT(pt.track_id) AS total, "
            "SUM(t.status='ready') AS ready "
            "FROM playlists p LEFT JOIN playlist_tracks pt ON pt.playlist_id=p.id "
            "LEFT JOIN tracks t ON t.id=pt.track_id GROUP BY p.id ORDER BY p.created DESC").fetchall()
    return [dict(r) | {"ready": r["ready"] or 0} for r in rows]


def delete_playlist(pid: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM playlists WHERE id=?", (pid,))


def pending_track_ids() -> list[str]:
    """Unfinished tracks, in playlist order (so a playlist's start becomes playable first)."""
    with connect() as c:
        rows = c.execute(
            "SELECT t.id FROM tracks t JOIN playlist_tracks pt ON pt.track_id=t.id "
            "WHERE t.status IN ('queued') GROUP BY t.id ORDER BY MIN(pt.playlist_id), MIN(pt.position)"
        ).fetchall()
    return [r["id"] for r in rows]


def get_track(track_id: str) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    return dict(r) if r else None
