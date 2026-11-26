<img width="111" height="111" alt="image" src="assets/sonorg.png" />

# sonorg

sonorg writes a speech up as an org file. The name is *sonus* + *org*: sound in, org out.

Paste a YouTube URL or drop an audio file. Captions are the source when the video has them. Otherwise Whisper (`small`, CPU, int8, 4 threads) transcribes it on this machine. The result is clean notes in org format: a title, a short overview of what was said, and sections of rewritten prose. The raw subtitles stay off the page.

The writing is one call to `gemini-4-hydrogen` on the free tier, with reasoning effort `low` and no tools. Create a key at [Google AI Studio](https://aistudio.google.com/apikey) and leave billing off, then put it in `.env`. On the free tier Google may use that transcript to improve its products, so keep private recordings off it.

## Run with Nix

```bash
nix develop          # or: direnv allow
cp .env.example .env # put GEMINI_API_KEY in .env; that call writes the notes
sonorg serve
```

Open http://127.0.0.1:8000. `nix run . -- serve` does the same outside the shell.

## Run with Python

Requires Python 3.12 or newer. Create and activate a virtual environment, then install sonorg:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install .
```

Copy `.env.example` to `.env`, add your `GEMINI_API_KEY`, then start the app:

```bash
cp .env.example .env
sonorg serve
```

On Windows, copy `.env.example` to `.env` using File Explorer or PowerShell. Install FFmpeg separately and make sure `ffmpeg` and `ffprobe` are on `PATH` for yt-dlp post-processing. The Python dependencies include yt-dlp and its Deno runtime.

## Run with Docker

Install Docker, copy `.env.example` to `.env`, and add your `GEMINI_API_KEY`. Build and start the app:

```bash
docker build -t sonorg .
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -v sonorg-models:/models \
  sonorg
```

Open <http://127.0.0.1:8000>. The image includes FFmpeg and the Python dependencies. The named volume keeps Whisper's downloaded model between container runs. The server has no authentication; keep the port bound to localhost unless you add access controls.

The first Whisper run downloads the `small` model. A 10 minute file on a low-power laptop takes several minutes; videos with captions usually process much faster.
