from collections.abc import Callable
from pathlib import Path

from .segments import Segment

# int8 with all 8 threads on this class of CPU can drop stretches of speech
# without an error. Four threads stays inside the safe side of that report.
_CPU_THREADS = 4
_model = None


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
            cpu_threads=_CPU_THREADS,
            num_workers=1,
        )
    return _model


def transcribe(path: Path, progress: Callable[[str], None] | None = None) -> list[Segment]:
    if progress:
        progress("Loading Whisper. The first run downloads the small model.")
    model = get_model()
    if progress:
        progress("Transcribing")
    segments, _info = model.transcribe(
        str(path),
        beam_size=5,
        vad_filter=True,
    )
    found: list[Segment] = []
    for segment in segments:
        text = " ".join(segment.text.split())
        if not text:
            continue
        found.append(Segment(float(segment.start), float(segment.end), text))
        if progress:
            progress(f"Transcribing {int(segment.end)}s")
    if not found:
        raise RuntimeError("Whisper returned an empty transcript.")
    return found
