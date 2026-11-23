import re
import subprocess
from pathlib import Path

from .segments import Segment

_TIMESTAMP = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.](\d{1,3})\s+-->\s+(?:(\d+):)?(\d{1,2}):(\d{2})[.](\d{1,3})"
)
_TAG = re.compile(r"<[^>]+>")
_YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def video_id(url: str) -> str | None:
    match = _YOUTUBE_ID.search(url)
    return match.group(1) if match else None


def _seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, "0")) / 1000


def _clean(text: str) -> str:
    text = _TAG.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split())


def parse_vtt(raw: str) -> list[Segment]:
    """Turn a WebVTT track into segments, collapsing YouTube's rolling repeats."""
    cues: list[Segment] = []
    start: float | None = None
    end: float | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal start, end, buf
        text = _clean(" ".join(buf))
        if start is not None and end is not None and text:
            cues.append(Segment(start, end, text))
        start = end = None
        buf = []

    for line in raw.splitlines():
        stamp = _TIMESTAMP.search(line)
        if stamp:
            flush()
            start = _seconds(*stamp.group(1, 2, 3, 4))
            end = _seconds(*stamp.group(5, 6, 7, 8))
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            flush()
            continue
        if stripped.isdigit() and start is None:
            continue
        if start is not None:
            buf.append(stripped)
    flush()
    return _dedupe(cues)


def _dedupe(cues: list[Segment]) -> list[Segment]:
    kept: list[Segment] = []
    for cue in cues:
        if not kept:
            kept.append(cue)
            continue
        prev = kept[-1]
        if cue.text == prev.text:
            continue
        # Auto-captions repeat a growing line. Keep the longest version of that run.
        if cue.text.startswith(prev.text) or prev.text.startswith(cue.text):
            if len(cue.text) >= len(prev.text):
                kept[-1] = cue
            continue
        kept.append(cue)
    return kept


def fetch_captions(url: str, workdir: Path) -> list[Segment] | None:
    """Download a timed text track. None means the video has no captions."""
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "en.*,en",
        "--convert-subs", "vtt",
        "-o", str(workdir / "media"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    tracks = sorted(workdir.glob("*.vtt"))
    if not tracks:
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "yt-dlp failed").strip()
            raise RuntimeError(detail[-500:])
        return None
    # A manual track is named like media.en.vtt; auto-subs include ".auto" or a generated name.
    manual = [path for path in tracks if ".auto" not in path.name]
    chosen = manual[0] if manual else tracks[0]
    segments = parse_vtt(chosen.read_text(encoding="utf-8", errors="replace"))
    return segments or None


def download_audio(url: str, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "ba/b",
        "-o", str(workdir / "audio.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    files = [path for path in workdir.glob("audio.*") if path.is_file()]
    if not files:
        detail = (result.stderr or result.stdout or "yt-dlp downloaded nothing").strip()
        raise RuntimeError(detail[-500:])
    return files[0]
