"""Runtime config: HA add-on options (/data/options.json) with env-var overrides for dev."""
import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
# Finished instrumentals live in /media (not /data) so they stay out of HA backups
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "/media"))
AUDIO_DIR = MEDIA_DIR / "instrumentalise"
LEGACY_AUDIO_DIR = DATA_DIR / "audio"  # v0.2.0 location, migrated on startup
TMP_DIR = DATA_DIR / "tmp"
DB_PATH = DATA_DIR / "library.db"
OPTIONS_FILE = DATA_DIR / "options.json"

MODAL_APP = "instrumentalise"
MODAL_CLS = "Separator"
WORKERS = int(os.environ.get("WORKERS", "3"))  # tracks processed in parallel
RADIO_REFILL_BELOW = 15  # fetch more radio tracks when fewer than this remain after the playing one


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except FileNotFoundError:
        return {}


def setup() -> None:
    """Create dirs and export Modal credentials from add-on options (env wins)."""
    for d in (AUDIO_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
    migrate_legacy_audio()
    opts = load_options()
    for env, key in (("MODAL_TOKEN_ID", "modal_token_id"), ("MODAL_TOKEN_SECRET", "modal_token_secret")):
        if opts.get(key) and not os.environ.get(env):
            os.environ[env] = opts[key]


def lookahead() -> int:
    """Songs prepared beyond the one playing (cost vs. skip-tolerance)."""
    return int(load_options().get("lookahead", os.environ.get("LOOKAHEAD", 3)))


def migrate_legacy_audio() -> int:
    """Move songs cached by v0.2.0 (/data/audio) into the media folder. Returns files moved."""
    import shutil

    if not LEGACY_AUDIO_DIR.is_dir():
        return 0
    moved = 0
    for f in LEGACY_AUDIO_DIR.glob("*.m4a"):
        dest = AUDIO_DIR / f.name
        if dest.exists():
            f.unlink()
        else:
            shutil.move(str(f), str(dest))
            moved += 1
    for leftover in LEGACY_AUDIO_DIR.glob("*.part"):
        leftover.unlink()
    try:
        LEGACY_AUDIO_DIR.rmdir()
    except OSError:
        pass  # not empty; leave it
    return moved
