"""Tiny SQLite store: tracks, playlists/stations, and membership (ordered)."""
import sqlite3
import time
from contextlib import contextmanager

from . import config

# status: new -> queued -> downloading -> separating -> ready   (or failed)
SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY, title TEXT, artist TEXT, duration REAL, thumbnail TEXT,
    status TEXT NOT NULL DEFAULT 'new', error TEXT, updated REAL
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
# columns added after v0.1.0, applied to existing databases
MIGRATIONS = {
    "playlists": {"kind": "TEXT NOT NULL DEFAULT 'playlist'", "seed": "TEXT",
                  "position": "INTEGER NOT NULL DEFAULT 0", "touched": "REAL"},
    "tracks": {"album": "TEXT"},
}


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
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for col, decl in cols.items():
                if col not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        # unfinished work from before a restart is re-queued by the playback window
        c.execute("UPDATE tracks SET status='new' WHERE status IN ('queued','downloading','separating')")


def _upsert_track(c, t: dict) -> None:
    # keep status/audio if the track is already known from another playlist
    c.execute(
        "INSERT INTO tracks (id, title, artist, album, duration, thumbnail, updated) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET title=excluded.title, artist=excluded.artist, "
        "album=COALESCE(excluded.album, tracks.album), "
        "duration=excluded.duration, thumbnail=excluded.thumbnail",
        (t["id"], t["title"], t["artist"], t.get("album"), t["duration"], t["thumbnail"], time.time()),
    )


def add_playlist(url: str, title: str, tracks: list[dict], kind: str = "playlist",
                 seed: str | None = None) -> int:
    with connect() as c:
        pid = c.execute(
            "INSERT INTO playlists (url, title, created, kind, seed, touched) VALUES (?,?,?,?,?,?)",
            (url, title, time.time(), kind, seed, time.time())).lastrowid
    append_tracks(pid, tracks)
    return pid


def append_tracks(pid: int, tracks: list[dict]) -> int:
    """Append tracks not already in this playlist; returns how many were added."""
    with connect() as c:
        have = {r["track_id"] for r in c.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id=?", (pid,))}
        nxt = c.execute("SELECT COALESCE(MAX(position)+1, 0) FROM playlist_tracks WHERE playlist_id=?",
                        (pid,)).fetchone()[0]
        added = 0
        for t in tracks:
            if t["id"] in have:
                continue
            have.add(t["id"])
            _upsert_track(c, t)
            c.execute("INSERT INTO playlist_tracks VALUES (?,?,?)", (pid, nxt + added, t["id"]))
            added += 1
    return added


def get_playlist(pid: int) -> dict | None:
    with connect() as c:
        pl = c.execute("SELECT * FROM playlists WHERE id=?", (pid,)).fetchone()
        if not pl:
            return None
        rows = c.execute(
            "SELECT t.* FROM playlist_tracks pt JOIN tracks t ON t.id = pt.track_id "
            "WHERE pt.playlist_id=? ORDER BY pt.position", (pid,)).fetchall()
    return {"id": pl["id"], "url": pl["url"], "title": pl["title"], "kind": pl["kind"],
            "seed": pl["seed"], "position": pl["position"], "tracks": [dict(r) for r in rows]}


def list_playlists() -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT p.id, p.title, p.url, p.kind, p.position, COUNT(pt.track_id) AS total, "
            "(SELECT t.thumbnail FROM playlist_tracks x JOIN tracks t ON t.id=x.track_id "
            " WHERE x.playlist_id=p.id ORDER BY x.position LIMIT 1) AS thumbnail "
            "FROM playlists p LEFT JOIN playlist_tracks pt ON pt.playlist_id=p.id "
            "GROUP BY p.id ORDER BY COALESCE(p.touched, p.created) DESC").fetchall()
    return [dict(r) for r in rows]


def latest_playlist_id() -> int | None:
    with connect() as c:
        r = c.execute("SELECT id FROM playlists ORDER BY COALESCE(touched, created) DESC LIMIT 1").fetchone()
    return r["id"] if r else None


def delete_playlist(pid: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM playlists WHERE id=?", (pid,))


def set_position(pid: int, index: int) -> None:
    with connect() as c:
        c.execute("UPDATE playlists SET position=?, touched=? WHERE id=?", (index, time.time(), pid))


def track_at(pid: int, index: int) -> str | None:
    with connect() as c:
        r = c.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=? AND position=?",
                      (pid, index)).fetchone()
    return r["track_id"] if r else None


def count(pid: int) -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=?", (pid,)).fetchone()[0]


def window(pid: int, index: int, ahead: int) -> list[str]:
    """Queue the playing track plus `ahead` more; return ids that now need processing.

    Tracks still waiting (not started) outside the window go back to 'new', so skipping
    ahead doesn't leave stale work in front of what you actually want to hear.
    """
    lo, hi = index, index + ahead
    with connect() as c:
        wanted = [r["track_id"] for r in c.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id=? AND position BETWEEN ? AND ? "
            "ORDER BY position", (pid, lo, hi))]
        if not wanted:
            return []
        marks = ",".join("?" * len(wanted))
        c.execute(f"UPDATE tracks SET status='new' WHERE status='queued' AND id NOT IN ({marks}) "
                  "AND id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id=?)", (*wanted, pid))
        c.execute(f"UPDATE tracks SET status='queued', updated=? WHERE status='new' AND id IN ({marks})",
                  (time.time(), *wanted))
        return [r["id"] for r in c.execute(
            f"SELECT id FROM tracks WHERE status='queued' AND id IN ({marks})", wanted)]


def get_track(track_id: str) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    return dict(r) if r else None


def set_status(track_id: str, status: str, error: str | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE tracks SET status=?, error=?, updated=? WHERE id=?",
                  (status, error, time.time(), track_id))


def set_album_if_missing(track_id: str, album: str | None) -> None:
    if album:
        with connect() as c:
            c.execute("UPDATE tracks SET album=? WHERE id=? AND (album IS NULL OR album='')",
                      (album, track_id))


def claim(track_id: str) -> bool:
    """Atomically move queued -> downloading; False if it was cancelled or already taken."""
    with connect() as c:
        cur = c.execute("UPDATE tracks SET status='downloading', error=NULL, updated=? "
                        "WHERE id=? AND status='queued'", (time.time(), track_id))
        return cur.rowcount == 1
