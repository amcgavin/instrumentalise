"""Vocal removal: wraps audio-separator with the chosen model, with a disk cache."""
from pathlib import Path

from . import config
from .ffmpeg import FFMPEG  # noqa: F401  (ensures ffmpeg is on PATH first)


class InstrumentalSeparator:
    def __init__(self, model: str = config.MODEL):
        from audio_separator.separator import Separator

        config.INSTRUMENTAL_DIR.mkdir(parents=True, exist_ok=True)
        config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self._sep = Separator(
            output_dir=str(config.INSTRUMENTAL_DIR),
            model_file_dir=str(config.MODEL_DIR),
            output_format="FLAC",
            output_single_stem="Instrumental",
            log_level=40,
        )
        self._sep.load_model(model_filename=model)

    def instrumental(self, track_id: str, source: Path) -> Path:
        out = config.INSTRUMENTAL_DIR / f"{track_id}.flac"
        if out.exists():
            return out
        self._sep.separate(str(source), custom_output_names={"Instrumental": track_id})
        if not out.exists():
            raise RuntimeError(f"separation produced no file for {track_id}")
        return out
