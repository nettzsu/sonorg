import re

from .segments import Chapter

_CLOCK_HEADING = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")


def clock(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def one_line(value: str) -> str:
    return " ".join(value.split())


def _body(text: str) -> str:
    lines = []
    for line in text.splitlines() or [""]:
        # A line that starts with '*' or '#+' would become an org heading or keyword.
        if line.startswith(("*", "#+")):
            line = " " + line
        lines.append(line)
    # rstrip only. A leading space is what keeps a line from becoming a heading.
    return "\n".join(lines).rstrip()


def _heading(text: str) -> str:
    cleaned = one_line(text).lstrip("*").strip() or "Section"
    if _CLOCK_HEADING.match(cleaned):
        cleaned = "Section"
    if len(cleaned) > 120:
        cleaned = cleaned[:117].rstrip() + "..."
    return cleaned


def render_org(
    *,
    title: str,
    source: str,
    duration: float,
    transcript: str,
    overview: str = "",
    chapters: list[Chapter],
    tasks: list[str] | None = None,
) -> str:
    """Build speech notes. The model never writes the org syntax."""
    lines = [
        f"#+TITLE: {one_line(title) or 'Untitled'}",
        "#+FILETAGS: :video:",
        ":PROPERTIES:",
        f":SOURCE: {one_line(source) or 'upload'}",
        f":DURATION: {clock(duration)}",
        f":TRANSCRIPT: {one_line(transcript) or 'unknown'}",
        ":END:",
        "",
    ]
    lead = _body(overview)
    if lead:
        lines.append(lead)
        lines.append("")
    for chapter in chapters:
        lines.append(f"* {_heading(chapter.heading)}")
        paragraph = _body(chapter.paragraph)
        if paragraph:
            lines.append(paragraph)
        lines.append("")
    todo = [one_line(task) for task in tasks or [] if one_line(task)]
    if todo:
        lines.append("* Tasks")
        for item in todo:
            lines.append(f"** TODO {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
