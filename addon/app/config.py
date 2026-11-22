"""Runtime config: HA add-on options (/data/options.json) with env-var overrides for dev."""
import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
AUDIO_DIR = DATA_DIR / "audio"
TMP_DIR = DATA_DIR / "tmp"
DB_PATH = DATA_DIR / "library.db"
OPTIONS_FILE = DATA_DIR / "options.json"

MODAL_APP = "instrumentalise"
MODAL_CLS = "Separator"
WORKERS = int(os.environ.get("WORKERS", "3"))  # tracks processed in parallel


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except FileNotFoundError:
        return {}


def setup() -> None:
    """Create dirs and export Modal credentials from add-on options (env wins)."""
    for d in (AUDIO_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
    opts = load_options()
    for env, key in (("MODAL_TOKEN_ID", "modal_token_id"), ("MODAL_TOKEN_SECRET", "modal_token_secret")):
        if opts.get(key) and not os.environ.get(env):
            os.environ[env] = opts[key]
