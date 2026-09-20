import shutil

import pytest
from fastapi.testclient import TestClient

from surfaced.render.slideshow import render_beats


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_render_slideshow(tmp_path):
    out = render_beats([{"on_screen": "Hello there", "sec": 1}, {"on_screen": "Second card", "sec": 1}], tmp_path / "v.mp4")
    assert out.exists() and out.stat().st_size > 1000


def test_server_run_and_state(tmp_path, monkeypatch):
    monkeypatch.setattr("surfaced.server.DATA", str(tmp_path))
    from surfaced.server import app
    c = TestClient(app)
    assert c.get("/api/state").status_code == 404
    r = c.post("/api/run", json={"demo": True})
    assert r.status_code == 200 and r.json()["report"]["overall"]["of"] == 5
    assert c.get("/api/state").status_code == 200
    assert c.get("/").status_code == 200
