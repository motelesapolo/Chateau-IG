import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import publish_due  # noqa: E402

from autopilot import config  # noqa: E402
from autopilot import queue as q  # noqa: E402
from autopilot.api import InstagramError  # noqa: E402


class FakeIG:
    fail = None
    calls = []
    extras = []

    def __init__(self, *a, **k):
        pass

    def publish_image(self, url, caption, ai, extra=None):
        FakeIG.extras.append(extra)
        if FakeIG.fail:
            raise FakeIG.fail
        FakeIG.calls.append(("image", url, caption, ai))
        return {"id": "M1", "permalink": "https://www.instagram.com/p/abc/"}

    def publish_reel(self, url, caption, ai, share_to_feed=True, cover_url=None, extra=None):
        FakeIG.calls.append(("reel", url, cover_url))
        return {"id": "M2", "permalink": "https://www.instagram.com/reel/xyz/"}


DECISIONS: dict = {}


@pytest.fixture
def env(project, monkeypatch):
    FakeIG.fail, FakeIG.calls, FakeIG.extras = None, [], []
    monkeypatch.setenv("IG_ACCESS_TOKEN", "x")
    monkeypatch.setattr(publish_due, "client_from_env", lambda settings: FakeIG())
    monkeypatch.setattr(publish_due.hosting, "media_sha", lambda: "abc123")
    monkeypatch.setattr(publish_due.review, "decisions", lambda: dict(DECISIONS))
    monkeypatch.setattr(publish_due.hosting, "reachable_url", lambda f, sha: f"https://cdn/{sha}/{f}")
    return project


def rendered(iid, when, t="image"):
    media = ({"kind": "image", "files": [f"media/{iid}/post.jpg"]} if t == "image" else
             {"kind": "video", "files": [f"media/{iid}/reel.mp4"], "cover": f"media/{iid}/cover.jpg"})
    q.save({"id": iid, "type": t, "publish_at": when.isoformat(), "caption": "hola",
            "scenes": [{"visual": {"source": "card"}}], "status": "rendered", "media": media})


def test_publishes_due_and_moves_file(env):
    now = datetime.now(timezone.utc)
    rendered("2026-01-01-ya", now - timedelta(minutes=5))
    rendered("2026-01-02-reel", now - timedelta(minutes=3), t="reel")
    rendered("2026-01-03-futuro", now + timedelta(days=1))
    publish_due.main()
    # tarjeta de marca, sin imágenes creadas por IA: sin etiqueta "Hecho con IA"
    assert FakeIG.calls[0] == ("image", "https://cdn/abc123/media/2026-01-01-ya/post.jpg", "hola", False)
    assert FakeIG.calls[1][2] == "https://cdn/abc123/media/2026-01-02-reel/cover.jpg"
    done = q.load(config.PUBLISHED_DIR / "2026-01-01-ya.json")
    assert done["status"] == "published" and done["result"]["permalink"].endswith("/p/abc/")
    assert not (config.QUEUE_DIR / "2026-01-01-ya.json").exists()
    assert (config.QUEUE_DIR / "2026-01-03-futuro.json").exists()


def test_too_late_is_marked_missed(env):
    rendered("2026-01-01-tarde", datetime.now(timezone.utc) - timedelta(hours=30))
    publish_due.main()
    assert FakeIG.calls == []
    assert q.load(config.QUEUE_DIR / "2026-01-01-tarde.json")["status"] == "missed"


def test_failure_retries_then_gives_up(env):
    rendered("2026-01-01-falla", datetime.now(timezone.utc) - timedelta(minutes=1))
    FakeIG.fail = InstagramError("formato no soportado", status=400, code=36003)
    path = config.QUEUE_DIR / "2026-01-01-falla.json"
    publish_due.main()
    assert q.load(path)["status"] == "rendered" and q.load(path)["attempts"] == 1
    publish_due.main()
    publish_due.main()
    assert q.load(path)["status"] == "publish_failed"


def test_rate_limit_keeps_item(env):
    rendered("2026-01-01-limite", datetime.now(timezone.utc) - timedelta(minutes=1))
    FakeIG.fail = InstagramError("límite", status=400, code=9, subcode=2207042)
    publish_due.main()
    item = q.load(config.QUEUE_DIR / "2026-01-01-limite.json")
    assert item["status"] == "rendered" and item.get("attempts", 0) == 0


def test_extras_location_collab_alt():
    item = {"collaborators": ["@amiga", "otra", "x", "y"], "alt_text": "Jacuzzi en Providencia"}
    assert publish_due.extras(item, {"location_id": 123}) == {
        "location_id": "123", "collaborators": "amiga,otra,x", "alt_text": "Jacuzzi en Providencia"}
    assert publish_due.extras({}, {"location_id": None}) == {}



def test_unticked_in_review_is_cancelled(env):
    DECISIONS["rechazada-1"] = False
    try:
        rendered("rechazada-1", datetime.now(timezone.utc) - timedelta(minutes=5))
        publish_due.main()
        data = q.load(config.QUEUE_DIR / "rechazada-1.json")
        assert data["status"] == "cancelled" and not FakeIG.calls
    finally:
        DECISIONS.clear()


def test_review_unavailable_publishes_nothing(env, monkeypatch):
    def boom():
        raise publish_due.review.ReviewUnavailable("sin red")
    monkeypatch.setattr(publish_due.review, "decisions", boom)
    rendered("espera-1", datetime.now(timezone.utc) - timedelta(minutes=5))
    assert publish_due.main() == 0 and not FakeIG.calls
    assert q.load(config.QUEUE_DIR / "espera-1.json")["status"] == "rendered"
