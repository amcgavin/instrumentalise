"""FastAPI app: submit playlists, watch progress, stream finished instrumentals."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, ytdl
from .processor import Processor, audio_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
processor = Processor()


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.setup()
    db.init()
    processor.submit_pending()  # resume anything unfinished from before a restart
    yield


app = FastAPI(title="Instrumentalise", lifespan=lifespan)


class NewPlaylist(BaseModel):
    url: str


@app.get("/api/health")
def health():
    return {"ok": True}


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
    processor.submit_pending()
    return db.get_playlist(pid)


@app.get("/api/playlists/{pid}")
def playlist(pid: int):
    pl = db.get_playlist(pid)
    if not pl:
        raise HTTPException(404)
    return pl


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
