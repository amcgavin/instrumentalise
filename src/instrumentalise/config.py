from pathlib import Path

MODEL = "mel_band_roformer_instrumental_becruily.ckpt"
SAMPLE_RATE = 44100
CHANNELS = 2
LOOKAHEAD = 2  # tracks to prepare ahead of the one playing

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "cache"
RAW_DIR = CACHE_DIR / "raw"
INSTRUMENTAL_DIR = CACHE_DIR / "instrumental"
MODEL_DIR = CACHE_DIR / "models"
