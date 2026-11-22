# Instrumentalise

Play YouTube Music playlists with the vocals removed.

```
phone ──► HA add-on (FastAPI, yt-dlp on home IP, library cache)
                 └──► Modal GPU worker (Mel-Band Roformer, T4) ──► instrumental (m4a)
```

## Parts

- `addon/` – the Home Assistant add-on (server + UI). Debian-based image.
- `worker/modal_app.py` – GPU separation worker. Deploy: `uv run modal deploy worker/modal_app.py`
- `src/instrumentalise/` – original local CLI (desktop GPU, plays through PipeWire).
- `bench/` – model benchmarks (GPU and CPU).

## Install the add-on

1. Deploy the worker once (above); it runs under your Modal account.
2. In Home Assistant: Settings → Add-ons → Add-on store → ⋮ → Repositories → add this repo's URL.
3. Install **Instrumentalise**, set `modal_token_id` / `modal_token_secret`
   (create a token at modal.com → Settings → API Tokens), and start it.
4. Open from the sidebar, or directly at `http://<ha-host>:8099` (e.g. over WireGuard).

## Storage

Finished instrumentals are cached by YouTube video ID in `/media/instrumentalise/<id>.m4a`
(about 5 MB each, no size cap). They live in `/media`, not `/data`, so they stay out of HA backups.
The library database and temporary downloads are in `/data`.

## Develop locally

```
DATA_DIR=./data-dev MEDIA_DIR=./data-dev/media uv run --project .. uvicorn app.main:app --port 8099   # from addon/
```
