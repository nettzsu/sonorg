import os
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .env import load_env
from .org import clock
from .page import PAGE
from .pipeline import from_file, from_url

load_env()

app = FastAPI(title="sonorg")
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).with_name("static")),
    name="static",
)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_LIMIT = 100 * 1024 * 1024


def _update(job_id: str, **fields: object) -> None:
    with _lock:
        _jobs[job_id].update(fields)


def _view(job: dict) -> dict:
    chapters = []
    for chapter in job.get("chapters") or []:
        chapters.append(
            {
                "start": chapter.start,
                "stamp": clock(chapter.start),
                "heading": chapter.heading,
                "paragraph": chapter.paragraph,
            }
        )
    return {
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "error": job.get("error"),
        "org": job.get("org"),
        "video_id": job.get("video_id"),
        "title": job.get("title") or "",
        "overview": job.get("overview") or "",
        "chapters": chapters,
    }


def _run(job_id: str, url: str | None, upload: Path | None) -> None:
    def progress(stage: str) -> None:
        _update(job_id, stage=stage)

    try:
        if url:
            written, video = from_url(url, progress)
        elif upload:
            written, video = from_file(upload, progress)
        else:
            raise RuntimeError("Give a YouTube URL or an audio file.")
        summary = written.summary
        _update(
            job_id,
            status="done",
            stage="Done",
            org=written.org,
            video_id=video,
            title=summary.title,
            overview=summary.overview,
            chapters=summary.chapters,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001  # a job reports the failure instead of dying quietly
        message = str(exc).strip() or exc.__class__.__name__
        _update(job_id, status="error", stage="Failed", error=message[:500])
    finally:
        if upload:
            upload.unlink(missing_ok=True)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/job")
async def create_job(
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),  # noqa: B008  # FastAPI reads the default as a dependency marker
) -> dict[str, str]:
    cleaned = (url or "").strip()
    payload = b""
    filename = ""
    if file is not None and file.filename:
        payload = await file.read(_LIMIT + 1)
        filename = Path(file.filename).name
        if len(payload) > _LIMIT:
            raise HTTPException(413, "File is larger than 100 MB.")
    if not cleaned and not payload:
        raise HTTPException(400, "Give a YouTube URL or an audio file.")
    if cleaned and not cleaned.startswith(("https://", "http://")):
        raise HTTPException(400, "The URL has to start with http:// or https://.")

    upload: Path | None = None
    if payload:
        descriptor, name = tempfile.mkstemp(prefix="sonorg-", suffix=Path(filename).suffix)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        upload = Path(name)
        cleaned = None

    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "stage": "Starting",
            "error": None,
            "org": None,
            "video_id": None,
            "title": "",
            "overview": "",
            "chapters": [],
        }
    threading.Thread(target=_run, args=(job_id, cleaned or None, upload), daemon=True).start()
    return {"id": job_id}


@app.get("/job/{job_id}")
def read_job(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "No such job.")
        snapshot = dict(job)
    return _view(snapshot)


@app.get("/job/{job_id}/note.org", response_class=PlainTextResponse)
def download(job_id: str) -> PlainTextResponse:
    with _lock:
        job = _jobs.get(job_id)
        if job is None or not job.get("org"):
            raise HTTPException(404, "Notes are not ready.")
        text = job["org"]
    return PlainTextResponse(
        text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sonorg.org"'},
    )
