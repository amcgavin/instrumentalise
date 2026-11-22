# Debian (glibc) base rather than the HA Alpine one: modal's native deps need glibc wheels.
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# yt-dlp needs a recent JS runtime to solve YouTube's challenges (bookworm's node is too old)
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN uv venv $VIRTUAL_ENV && uv pip install --no-cache -r requirements.txt

COPY app ./app

EXPOSE 8099
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099"]
