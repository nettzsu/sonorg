import tempfile
from collections.abc import Callable
from pathlib import Path

from .captions import download_audio, fetch_captions, video_id
from .org import render_org
from .segments import Segment, Summary, Written
from .summarize import summarize
from .transcribe import transcribe

Progress = Callable[[str], None]


def _duration(segments: list[Segment]) -> float:
    return max((segment.end for segment in segments), default=0.0)


def note_from_segments(
    *,
    source: str,
    transcript: str,
    segments: list[Segment],
) -> Written:
    summary = summarize(segments)
    return _written(source=source, transcript=transcript, segments=segments, summary=summary)


def _written(
    *,
    source: str,
    transcript: str,
    segments: list[Segment],
    summary: Summary,
) -> Written:
    org = render_org(
        title=summary.title,
        source=source,
        duration=_duration(segments),
        transcript=transcript,
        overview=summary.overview,
        chapters=summary.chapters,
        tasks=summary.tasks,
    )
    return Written(org=org, summary=summary)


def from_url(url: str, progress: Progress | None = None) -> tuple[Written, str | None]:
    def report(stage: str) -> None:
        if progress:
            progress(stage)

    with tempfile.TemporaryDirectory(prefix="sonorg-") as directory:
        work = Path(directory)
        report("Fetching captions")
        segments = fetch_captions(url, work)
        kind = "captions"
        if not segments:
            report("No captions. Downloading audio")
            audio = download_audio(url, work)
            segments = transcribe(audio, report)
            kind = "whisper"
        report("Writing notes")
        return note_from_segments(source=url, transcript=kind, segments=segments), video_id(url)


def from_file(path: Path, progress: Progress | None = None) -> tuple[Written, str | None]:
    def report(stage: str) -> None:
        if progress:
            progress(stage)

    segments = transcribe(path, report)
    report("Writing notes")
    return note_from_segments(source=path.name, transcript="whisper", segments=segments), None
