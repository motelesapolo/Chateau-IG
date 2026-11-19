"""Render real con ffmpeg (sin internet: usa fondos 'card' y archivos locales)."""
import json
import subprocess

import pytest
from PIL import Image

from autopilot import render

pytestmark = pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0,
                                reason="ffmpeg no instalado")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.fixture
def photo(project):
    p = project / "assets/images/foto.jpg"
    Image.new("RGB", (1600, 1000), (180, 120, 60)).save(p)
    return "assets/images/foto.jpg"


def test_image_post(project):
    item = {"id": "t-img", "type": "image", "scenes": [
        {"visual": {"source": "card", "bg": "#0f2027", "bg2": "#2c5364"},
         "text": "3 errores que arruinan tu pan casero"}]}
    media = render.render_item(item)
    img = Image.open(project / media["files"][0])
    assert img.size == (1080, 1350) and media["kind"] == "image"
    assert (project / media["preview"]).exists()


def test_carousel(project, photo):
    item = {"id": "t-car", "type": "carousel", "scenes": [
        {"visual": {"source": "file", "path": photo}, "text": "Pan en 5 pasos"},
        {"visual": {"source": "card"}, "text": "1. Activa la levadura con agua tibia"},
        {"visual": {"source": "card"}, "text": "2. Amasa 10 minutos"}]}
    media = render.render_item(item)
    assert media["kind"] == "carousel" and len(media["files"]) == 3
    assert all(Image.open(project / f).size == (1080, 1350) for f in media["files"])


def test_story_image(project, photo):
    item = {"id": "t-story", "type": "story",
            "scenes": [{"visual": {"source": "file", "path": photo}, "text": "Hoy a las 19:30 🍞"}]}
    media = render.render_item(item)
    assert Image.open(project / media["files"][0]).size == (1080, 1920)


def test_reel_video(project, photo):
    item = {"id": "t-reel", "type": "reel", "scenes": [
        {"visual": {"source": "card"}, "text": "¿Tu pan sale duro?", "duration": 2},
        {"visual": {"source": "file", "path": photo}, "text": "Prueba esto", "duration": 2.5},
        {"visual": {"source": "card", "bg": "#222222"}, "text": "Guárdalo 📌", "duration": 2}]}
    media = render.render_item(item)
    info = probe(project / media["files"][0])
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"][0]
    assert (v["width"], v["height"], v["codec_name"]) == (1080, 1920, "h264")
    assert a["codec_name"] == "aac"
    assert 6.0 <= float(info["format"]["duration"]) <= 7.2
    assert media["size_mb"] < 19
    assert (project / media["cover"]).exists() and (project / media["preview"]).exists()


def test_text_overlay_wraps_long_text(project):
    layer = render.text_overlay("Este es un texto bastante largo que debería ocupar varias líneas "
                                "sin salirse de los bordes de la imagen", render.VERTICAL)
    box = layer.getbbox()
    assert box[0] > 40 and box[2] < 1040


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload, text or str(payload)

    def json(self):
        return self._p


def _jpeg_b64(w=1024, h=1536):
    import base64
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (w, h), (200, 120, 60)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def test_openai_falls_back_to_next_model_and_fits_size(tmp_path, monkeypatch):
    from autopilot import render
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(render, "_openai_count", 0)
    calls = []

    class S:
        def post(self, url, headers, json, timeout):
            calls.append(json["model"])
            if json["model"] == "gpt-image-1.5":
                return _Resp(404, text="The model gpt-image-1.5 does not exist")
            return _Resp(200, {"data": [{"b64_json": _jpeg_b64()}]})

    out = render._openai({"prompt": "warm cozy light"}, render.VERTICAL, tmp_path / "a.jpg", session=S())
    from PIL import Image
    assert calls == ["gpt-image-1.5", "gpt-image-1"]
    assert Image.open(out).size == render.VERTICAL


def test_ai_image_uses_pollinations_when_openai_fails(tmp_path, monkeypatch):
    from autopilot import render
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(render, "_openai", lambda *a, **k: (_ for _ in ()).throw(render.RenderError("sin saldo")))
    monkeypatch.setattr(render, "_pollinations", lambda vis, size, dest, seed: dest)
    assert render.ai_image({"prompt": "p"}, render.FEED, tmp_path / "b.jpg", 1) == tmp_path / "b.jpg"
