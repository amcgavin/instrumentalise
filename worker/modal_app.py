"""Modal GPU worker: audio in -> vocal-free instrumental (AAC/m4a) out.

Deploy:  uv run modal deploy worker/modal_app.py
Try it:  uv run modal run worker/modal_app.py --path bench/clip30.flac
"""
import modal

APP_NAME = "instrumentalise"
MODEL = "mel_band_roformer_instrumental_becruily.ckpt"
MODEL_DIR = "/models"


def _download_model() -> None:
    """Runs at image build time so cold starts don't download the weights."""
    from audio_separator.separator import Separator

    Separator(model_file_dir=MODEL_DIR, log_level=40).load_model(model_filename=MODEL)


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    # cu126 build: works on every GPU Modal offers, including the cheap T4
    .pip_install("torch", index_url="https://download.pytorch.org/whl/cu126")
    .pip_install("audio-separator", "onnxruntime", "audioread", "soundfile")
    .run_function(_download_model)
)

app = modal.App(APP_NAME, image=image)


@app.cls(gpu="T4", timeout=900, scaledown_window=120)
class Separator:
    @modal.enter()
    def load(self) -> None:
        from audio_separator.separator import Separator as AudioSeparator

        self.workdir = "/tmp/work"
        self.sep = AudioSeparator(
            model_file_dir=MODEL_DIR,
            output_dir=self.workdir,
            output_format="FLAC",
            output_single_stem="Instrumental",
            log_level=40,
        )
        self.sep.load_model(model_filename=MODEL)

    @modal.method()
    def separate(self, audio: bytes) -> bytes:
        """Return the instrumental as AAC-in-m4a bytes (plays on every phone)."""
        import pathlib
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "in.audio"
            src.write_bytes(audio)
            self.sep.output_dir = tmp
            self.sep.model_instance.output_dir = tmp
            self.sep.separate(str(src), custom_output_names={"Instrumental": "inst"})
            out = pathlib.Path(tmp) / "out.m4a"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(pathlib.Path(tmp) / "inst.flac"),
                 "-c:a", "aac", "-b:a", "256k", str(out)],
                check=True,
            )
            return out.read_bytes()


@app.local_entrypoint()
def main(path: str, out: str = "worker_out.m4a") -> None:
    import pathlib
    import time

    data = pathlib.Path(path).read_bytes()
    t0 = time.perf_counter()
    result = Separator().separate.remote(data)
    pathlib.Path(out).write_bytes(result)
    print(f"{len(data) / 1e6:.1f}MB in -> {len(result) / 1e6:.1f}MB out in {time.perf_counter() - t0:.1f}s -> {out}")
