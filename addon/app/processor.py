"""Background pipeline per track: download (home IP) -> Modal GPU -> cached m4a."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from . import config, db, ytdl

log = logging.getLogger("instrumentalise")


def audio_path(track_id: str):
    return config.AUDIO_DIR / f"{track_id}.m4a"


def _separate_remote(data: bytes) -> bytes:
    import modal

    cls = modal.Cls.from_name(config.MODAL_APP, config.MODAL_CLS)
    return cls().separate.remote(data)


class Processor:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=config.WORKERS)
        self._inflight: set[str] = set()
        self._lock = threading.Lock()
        self._download_lock = threading.Lock()  # one YouTube download at a time

    def submit(self, track_id: str) -> None:
        with self._lock:
            if track_id in self._inflight:
                return
            self._inflight.add(track_id)
        self._pool.submit(self._run, track_id)

    def submit_pending(self) -> None:
        for tid in db.pending_track_ids():
            self.submit(tid)

    def _run(self, track_id: str) -> None:
        try:
            out = audio_path(track_id)
            if out.exists():
                db.set_status(track_id, "ready")
                return
            db.set_status(track_id, "downloading")
            with self._download_lock:
                raw = ytdl.download(track_id)
            db.set_status(track_id, "separating")
            result = _separate_remote(raw.read_bytes())
            tmp = out.with_suffix(".part")
            tmp.write_bytes(result)
            tmp.rename(out)  # atomic: a half-written file is never served
            raw.unlink(missing_ok=True)
            db.set_status(track_id, "ready")
            log.info("ready: %s", track_id)
        except Exception as exc:
            log.exception("failed: %s", track_id)
            db.set_status(track_id, "failed", str(exc)[:500])
        finally:
            with self._lock:
                self._inflight.discard(track_id)
