# sonorg

sonorg writes a speech up as an org file. The name is *sonus* + *org*: sound in, org out.

Paste a YouTube URL or drop an audio file. Captions are the source when the video has them. Otherwise Whisper (`small`, CPU, int8, 4 threads) transcribes it on this machine. The result is clean notes in org format: a title, a short overview of what was said, and sections of rewritten prose. The raw subtitles stay off the page.

The writing is one call to `gemini-4-hydrogen` on the free tier, with reasoning effort `low` and no tools. Create a key at [Google AI Studio](https://aistudio.google.com/apikey) and leave billing off, then put it in `.env`. On the free tier Google may use that transcript to improve its products, so keep private recordings off it.

## Run

```bash
nix develop          # or: direnv allow
cp .env.example .env # put GEMINI_API_KEY in .env; that call writes the notes
sonorg serve
```

Open http://127.0.0.1:8000. `nix run . -- serve` does the same outside the shell.

The first Whisper run downloads the `small` model. A 10 minute file on a low-power laptop takes several minutes; captions return in seconds and are the path to record.

The Python dependency provides `yt-dlp` and its Deno runtime. Outside Nix or Docker, install the FFmpeg system tools and make sure `ffmpeg` and `ffprobe` are on `PATH` for yt-dlp post-processing. Nix and Docker provide FFmpeg for you.
