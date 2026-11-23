import typer
import uvicorn

from .env import load_env

load_env()

# A single command is promoted to the root in Typer 0.29, which rejects
# `sonorg serve`. A callback keeps `serve` as a subcommand.
app = typer.Typer(
    help="Write a speech up as an org file.",
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Write a speech up as an org file."""


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Open the page on this machine."""
    uvicorn.run("sonorg.api:app", host=host, port=port)
