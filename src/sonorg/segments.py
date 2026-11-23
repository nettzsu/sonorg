from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Chapter:
    start: float
    heading: str
    paragraph: str


@dataclass(frozen=True)
class Summary:
    title: str
    overview: str
    chapters: list[Chapter]
    tasks: list[str]


@dataclass(frozen=True)
class Written:
    org: str
    summary: Summary
