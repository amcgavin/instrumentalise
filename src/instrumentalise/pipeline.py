"""Producer thread prepares tracks ahead of the player; main thread plays in order."""
import queue
import threading
from pathlib import Path

from . import config, player
from .playlist import Track, download, resolve

_DONE = object()


def run(url: str, shuffle: bool = False) -> None:
    from .separate import InstrumentalSeparator

    tracks = resolve(url)
    if shuffle:
        import random

        random.shuffle(tracks)
    print(f"{len(tracks)} track(s). Loading model...", flush=True)
    separator = InstrumentalSeparator()

    ready: queue.Queue = queue.Queue(maxsize=config.LOOKAHEAD)
    stop = threading.Event()

    def produce() -> None:
        for track in tracks:
            if stop.is_set():
                return
            try:
                item: tuple[Track, Path] | Exception = (
                    track,
                    separator.instrumental(track.id, download(track)),
                )
            except Exception as exc:  # skip unavailable/failed tracks
                item = exc
                print(f"  ! skipping {track.title}: {exc}", flush=True)
                continue
            while not stop.is_set():
                try:
                    ready.put(item, timeout=0.5)
                    break
                except queue.Full:
                    pass
        ready.put(_DONE)

    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    try:
        n = 0
        while (item := ready.get()) is not _DONE:
            track, path = item
            n += 1
            print(f"[{n}/{len(tracks)}] {track.title}", flush=True)
            player.play(path)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
