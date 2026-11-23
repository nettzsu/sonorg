import json
import os

from .segments import Chapter, Segment, Summary

_MODEL = "gemini-4-hydrogen"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# One speech stays in a single call. The free tier covers this model.
_TRANSCRIPT_LIMIT = 80_000
# Low effort still writes the notes. The default thinks longer, for nothing
# this task needs, and that thinking counts against the output cap.
_MAX_OUTPUT_TOKENS = 8_000

_INSTRUCTIONS = """You turn spoken recordings into clean, durable knowledge.
The source is automatic captions or speech-to-text of any kind of speech: a lecture, talk, interview, podcast, discussion, meeting, or monologue. It is messy: repeated lines, broken sentences, filler, misheard words. It is not the notes.
Extract what the speech actually conveyed and write it as a reader would want to find it later, without needing the recording.
- title is a short, specific name for the content, as you would put at the top of a page.
- overview is the whole recording in a few plain sentences: what it is about and what it concludes.
- a section is one idea or topic. heading is a short, plain label with no timestamp. body explains the idea in complete sentences, as many as it needs, with a blank line between paragraphs.
- follow the order of the recording. A short recording gets a few sections. A long one gets more, and never one section per caption line.
- keep substance: claims, reasoning, definitions, facts, numbers, names, decisions, and conclusions. Keep an example or story only when it carries the idea.
- drop greetings, introductions, sponsor reads, pleas to subscribe, small talk, filler, and repetition.
- when the speech defines a term, state the definition clearly.
- when there are several speakers, attribute a position to a person only if the transcript makes it clear who said it. Otherwise state the point without attribution.
- fix obvious transcription errors when the correct term is clear from context. Do not guess when it is not.
- do not invent or embellish. Add no outside knowledge and no opinions of your own. If a point was unclear or left unfinished, say so in one sentence.
- do not quote the transcript, and do not mention captions, transcription, or timestamps in the prose.
- write in the language of the recording.
- start is the second, taken from the transcript markers, where that idea begins.
- tasks are concrete actions the speech calls for or that clearly follow from it: next steps, recommendations to try, things to look up. Leave the list empty when there are none.
- if the transcript ends with [truncated], the recording went on. Do not invent that part. Say in the overview that the notes stop before the end.
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "overview": {"type": "string"},
        "sections": {
            "type": "array",
            "maxItems": 16,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "start": {"type": "number"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "start", "body"],
            },
        },
        "tasks": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
    },
    "required": ["title", "overview", "sections", "tasks"],
}


class NotesError(RuntimeError):
    """The speech notes could not be written."""


def speech_transcript(segments: list[Segment]) -> str:
    """Join cues into blocks. One timestamp per block, so the notes can still seek."""
    blocks: list[str] = []
    words: list[str] = []
    start = 0.0
    last_end = 0.0

    def flush() -> None:
        nonlocal words
        if words:
            blocks.append(f"[{start:.0f}] " + " ".join(words))
        words = []

    for segment in segments:
        text = " ".join(segment.text.split())
        if not text:
            continue
        if words and (segment.start - last_end > 1.5 or segment.start - start > 40):
            flush()
        if not words:
            start = segment.start
        words.append(text)
        last_end = segment.end
    flush()
    text = "\n".join(blocks)
    if len(text) <= _TRANSCRIPT_LIMIT:
        return text
    cut = text[:_TRANSCRIPT_LIMIT]
    line_end = cut.rfind("\n")
    if line_end > 0:
        cut = cut[:line_end]
    return cut + "\n[truncated]"


def parse_summary(raw: str) -> Summary:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the model did not return JSON")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("the model did not return an object")  # noqa: TRY004  # bad JSON, not a bad call signature
    chapters: list[Chapter] = []
    items = data.get("sections")
    if not isinstance(items, list):
        items = data.get("chapters") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            stamp = float(item.get("start", 0))
        except (TypeError, ValueError):
            stamp = 0.0
        heading = str(item.get("heading") or "").strip()
        paragraph = str(item.get("body") or item.get("paragraph") or "").strip()
        if heading or paragraph:
            chapters.append(Chapter(stamp, heading or "Section", paragraph))
    if not chapters:
        raise ValueError("the model returned no sections")
    tasks = [str(task).strip() for task in data.get("tasks") or [] if str(task).strip()]
    title = str(data.get("title") or "").strip() or "Untitled"
    overview = str(data.get("overview") or "").strip()
    return Summary(title=title, overview=overview, chapters=chapters[:16], tasks=tasks[:8])


def _failure(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    text = f"Could not write the notes: {message[:300]}"
    lowered = message.lower()
    if any(word in lowered for word in ("credit", "billing", "quota", "insufficient", "free tier")):
        text += ". Leave billing off in Google AI Studio."
    return text


def summarize(segments: list[Segment]) -> Summary:
    """One API call. Raises NotesError instead of filing the raw subtitles."""
    transcript = speech_transcript(segments)
    if not transcript:
        raise NotesError("There is nothing in the recording to take notes from.")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise NotesError(
            "Set GEMINI_API_KEY to write the notes. "
            "Create it in Google AI Studio and leave billing off. "
            "The raw subtitles are not the file."
        )
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=_BASE_URL)
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _INSTRUCTIONS},
                {"role": "user", "content": transcript},
            ],
            reasoning_effort="low",
            max_completion_tokens=_MAX_OUTPUT_TOKENS,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "speech_notes",
                    "strict": True,
                    "schema": _SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content or ""
        return parse_summary(content)
    except NotesError:
        raise
    except Exception as exc:  # the job should say why the notes were not written
        raise NotesError(_failure(exc)) from exc
