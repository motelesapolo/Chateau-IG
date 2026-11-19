import json

import pytest

from autopilot.api import InstagramClient, InstagramError


class Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    """Responde según (método, sufijo de ruta) y guarda las llamadas."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, url, params=None, json=None, timeout=None):
        path = url.split("/v25.0/")[1]
        self.calls.append((method, path, dict(params or {}), json))
        for (m, suffix), handler in self.routes.items():
            if m == method and path == suffix:
                out = handler(params or {}, json) if callable(handler) else handler
                return out if isinstance(out, Resp) else Resp(out)
        return Resp({"error": {"message": f"ruta no simulada {method} {path}", "code": 100}}, 400)


ME = {("GET", "me"): {"id": "app1", "user_id": "178", "username": "micuenta"}}


def client(routes):
    sess = FakeSession({**ME, **routes})
    return InstagramClient("TOKEN", "v25.0", session=sess, sleep=lambda s: None), sess


def test_publish_image_with_ai_label():
    c, s = client({
        ("POST", "178/media"): {"id": "C1"},
        ("GET", "C1"): {"status_code": "FINISHED"},
        ("POST", "178/media_publish"): {"id": "M1"},
        ("GET", "M1"): {"id": "M1", "permalink": "https://instagram.com/p/x"},
    })
    info = c.publish_image("https://cdn/x.jpg", "hola", ai_generated=True)
    assert info["permalink"].endswith("/p/x")
    create = [call for call in s.calls if call[1] == "178/media"][0]
    assert create[2]["is_ai_generated"] == "true"
    assert create[2]["access_token"] == "TOKEN"


def test_ai_label_fallback_when_unsupported():
    attempts = []

    def create(params, _):
        attempts.append(params)
        if "is_ai_generated" in params:
            return Resp({"error": {"message": "(#100) Param is_ai_generated is not supported", "code": 100}}, 400)
        return {"id": "C1"}

    c, _ = client({
        ("POST", "178/media"): create,
        ("GET", "C1"): {"status_code": "FINISHED"},
        ("POST", "178/media_publish"): {"id": "M1"},
        ("GET", "M1"): {"id": "M1"},
    })
    c.publish_image("https://cdn/x.jpg", "hola", ai_generated=True)
    assert len(attempts) == 2 and "is_ai_generated" not in attempts[1]


def test_reel_waits_until_finished():
    states = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
    c, s = client({
        ("POST", "178/media"): {"id": "R1"},
        ("GET", "R1"): lambda p, j: {"status_code": next(states)},
        ("POST", "178/media_publish"): {"id": "M2"},
        ("GET", "M2"): {"id": "M2"},
    })
    c.publish_reel("https://cdn/r.mp4", "cap", cover_url="https://cdn/c.jpg")
    create = [call for call in s.calls if call[1] == "178/media"][0][2]
    assert create["media_type"] == "REELS" and create["share_to_feed"] == "true"
    assert create["cover_url"] == "https://cdn/c.jpg"
    assert sum(1 for call in s.calls if call[1] == "R1") == 3


def test_container_error_raises():
    c, _ = client({
        ("POST", "178/media"): {"id": "R1"},
        ("GET", "R1"): {"status_code": "ERROR", "status": "Error: formato de video"},
    })
    with pytest.raises(InstagramError, match="rechazó"):
        c.publish_reel("https://cdn/r.mp4", "cap", ai_generated=False)


def test_carousel_children_then_parent():
    ids = iter(["K1", "K2", "P1"])
    c, s = client({
        ("POST", "178/media"): lambda p, j: {"id": next(ids)},
        ("GET", "K1"): {"status_code": "FINISHED"},
        ("GET", "K2"): {"status_code": "FINISHED"},
        ("GET", "P1"): {"status_code": "FINISHED"},
        ("POST", "178/media_publish"): {"id": "M3"},
        ("GET", "M3"): {"id": "M3"},
    })
    c.publish_carousel(["https://a.jpg", "https://b.jpg"], "cap", ai_generated=True)
    creates = [call[2] for call in s.calls if call[1] == "178/media"]
    assert creates[0]["is_carousel_item"] == "true" and "is_ai_generated" not in creates[0]
    assert creates[2]["media_type"] == "CAROUSEL" and creates[2]["children"] == "K1,K2"
    assert creates[2]["is_ai_generated"] == "true"


def test_story_requires_one_media():
    c, _ = client({})
    with pytest.raises(ValueError):
        c.publish_story()


def test_send_message_truncates_to_1000_bytes():
    c, s = client({("POST", "178/messages"): {"recipient_id": "U1", "message_id": "m"}})
    c.send_message("U1", "ñ" * 800)
    body = [call for call in s.calls if call[1] == "178/messages"][0][3]
    assert body["recipient"] == {"id": "U1"}
    assert len(body["message"]["text"].encode()) <= 1000


def test_rate_limit_detection():
    c, _ = client({("GET", "178/content_publishing_limit"):
                   Resp({"error": {"message": "limit", "code": 9, "error_subcode": 2207042}}, 400)})
    with pytest.raises(InstagramError) as exc:
        c.publishing_limit()
    assert exc.value.is_rate_limit
