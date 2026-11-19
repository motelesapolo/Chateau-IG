import json
import shutil
import subprocess

import pytest
from PIL import Image

from autopilot import config, material

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")


@pytest.fixture
def mat(project):
    d = project / "material" / "habitaciones" / "jacuzzi"
    d.mkdir(parents=True)
    return d


def gps_exif():
    img = Image.new("RGB", (10, 10))
    exif = img.getexif()
    exif[0x010F] = "Apple"           # Make
    exif[0x0110] = "iPhone 17 Pro"   # Model
    gps = exif.get_ifd(0x8825)
    gps[2] = (33.0, 26.0, 0.0)       # latitud
    return exif


def test_photo_is_converted_resized_and_stripped(mat, project):
    src = mat / "IMG 0042.PNG"
    Image.new("RGB", (4000, 3000), (120, 80, 40)).save(src, exif=gps_exif())
    res = material.optimize()
    out = project / "material/habitaciones/jacuzzi/img-0042.jpg"
    assert res["ok"] == ["material/habitaciones/jacuzzi/img-0042.jpg"] and not res["errores"]
    assert out.exists() and not src.exists()
    with Image.open(out) as im:
        assert max(im.size) == 2160
        assert len(im.getexif()) == 0
    # segunda vuelta: ya procesado, no hace nada
    assert material.optimize()["ok"] == []


def test_heic_from_iphone(mat, project):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    src = mat / "IMG_1001.HEIC"
    Image.new("RGB", (1200, 1600), (10, 120, 200)).save(src, format="HEIF")
    res = material.optimize()
    assert res["ok"] == ["material/habitaciones/jacuzzi/img-1001.jpg"]
    with Image.open(project / res["ok"][0]) as im:
        assert im.format == "JPEG" and im.size == (1200, 1600)


def test_video_is_downscaled_and_metadata_removed(mat, project):
    src = mat / "Recorrido.MOV"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1440x2560:rate=30:duration=2",
                    "-f", "lavfi", "-i", "sine=duration=2", "-shortest", "-c:v", "libx264", "-c:a", "aac",
                    "-metadata", "location=+33.4372-070.6506/", "-metadata", "title=privado", str(src)], check=True)
    res = material.optimize()
    out = project / "material/habitaciones/jacuzzi/recorrido.mp4"
    assert res["ok"] == ["material/habitaciones/jacuzzi/recorrido.mp4"] and out.exists()
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                       "stream=width,height:format_tags", "-of", "json", str(out)],
                                      capture_output=True, text=True).stdout)
    v = probe["streams"][0]
    assert (v["width"], v["height"]) == (1080, 1920)
    tags = probe["format"].get("tags", {})
    assert "location" not in tags and "title" not in tags


def test_unsupported_file_is_reported(mat):
    (mat / "notas.txt").write_text("hola")
    res = material.optimize()
    assert res["errores"] and "no soportado" in res["errores"][0]


def test_inventory_counts_usage(mat, project):
    Image.new("RGB", (1080, 1920)).save(mat / "a.jpg")
    Image.new("RGB", (1920, 1080)).save(mat / "b.jpg")
    material.optimize()
    item = {"id": "2026-11-24-reel-x", "scenes": [{"visual": {"source": "file",
                                                                "path": "material/habitaciones/jacuzzi/a.jpg"}}]}
    (config.PUBLISHED_DIR / "2026-11-24-reel-x.json").write_text(json.dumps(item))
    rows = {r["path"]: r for r in material.inventory()}
    a, b = rows["material/habitaciones/jacuzzi/a.jpg"], rows["material/habitaciones/jacuzzi/b.jpg"]
    assert a["usos"] == 1 and a["orientacion"] == "vertical" and a["categoria"] == "habitaciones/jacuzzi"
    assert b["usos"] == 0 and b["orientacion"] == "horizontal"
