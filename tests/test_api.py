from fastapi.testclient import TestClient

from sonorg.api import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
