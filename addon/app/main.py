"""FastAPI app: search, radio stations, playlists; streams finished instrumentals."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, radio, ytdl
from .processor import Processor, audio_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("instrumentalise")
processor = Processor()


def _advance(pid: int, index: int) -> None:
    """Record where playback is, top up a radio if it's running low, and queue the window."""
    pl_kind = (db.get_playlist(pid) or {}).get("kind")
    if pl_kind == "radio" and db.count(pid) - index - 1 < config.RADIO_REFILL_BELOW:
        current = db.track_at(pid, index)
        if current:
            try:
                added = db.append_tracks(pid, radio.radio(current))
                log.info("radio %s extended by %d tracks", pid, added)
            except Exception:
                log.exception("radio refill failed")  # keep playing what we have
    db.set_position(pid, index)
    processor.submit_many(db.window(pid, index, config.lookahead()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.setup()
    db.init()
    if (pid := db.latest_playlist_id()) is not None:  # resume after a restart
        _advance(pid, (db.get_playlist(pid) or {}).get("position", 0))
    yield


app = FastAPI(title="Instrumentalise", lifespan=lifespan)


class NewPlaylist(BaseModel):
    url: str


class NewRadio(BaseModel):
    video_id: str


class Position(BaseModel):
    index: int


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/search")
def search(q: str):
    if not q.strip():
        return []
    try:
        return radio.search(q.strip())
    except Exception as exc:
        raise HTTPException(502, f"Search failed: {exc}") from exc


@app.post("/api/radio", status_code=201)
def start_radio(body: NewRadio):
    try:
        tracks = radio.radio(body.video_id)
    except Exception as exc:
        raise HTTPException(502, f"Couldn't start radio: {exc}") from exc
    if not tracks:
        raise HTTPException(502, "YouTube Music returned an empty radio")
    pid = db.add_playlist(f"radio:{body.video_id}", f"{tracks[0]['title']} Radio", tracks,
                          kind="radio", seed=body.video_id)
    _advance(pid, 0)
    return db.get_playlist(pid)


@app.get("/api/playlists")
def playlists():
    return db.list_playlists()


@app.post("/api/playlists", status_code=201)
def add_playlist(body: NewPlaylist):
    try:
        title, tracks = ytdl.resolve(body.url.strip())
    except Exception as exc:
        raise HTTPException(400, f"Couldn't read that URL: {exc}") from exc
    if not tracks:
        raise HTTPException(400, "No tracks found")
    pid = db.add_playlist(body.url.strip(), title, tracks)
    _advance(pid, 0)
    return db.get_playlist(pid)


@app.get("/api/playlists/{pid}")
def playlist(pid: int):
    pl = db.get_playlist(pid)
    if not pl:
        raise HTTPException(404)
    return pl


@app.post("/api/playlists/{pid}/position")
def position(pid: int, body: Position):
    """Called by the player on every track change (and as a heartbeat)."""
    if not db.get_playlist(pid):
        raise HTTPException(404)
    _advance(pid, max(0, body.index))
    return {"total": db.count(pid)}


@app.delete("/api/playlists/{pid}", status_code=204)
def delete_playlist(pid: int):
    db.delete_playlist(pid)


@app.post("/api/tracks/{track_id}/retry", status_code=202)
def retry(track_id: str):
    if not db.get_track(track_id):
        raise HTTPException(404)
    db.set_status(track_id, "queued")
    processor.submit(track_id)


@app.get("/api/tracks/{track_id}/audio")
def audio(track_id: str):
    path = audio_path(track_id)
    if not path.exists():
        raise HTTPException(404, "Not ready")
    # FileResponse supports HTTP Range requests, which iOS Safari requires for <audio>
    return FileResponse(path, media_type="audio/mp4")


static = Path(__file__).parent / "static"
if static.exists():
    app.mount("/", StaticFiles(directory=static, html=True), name="static")
