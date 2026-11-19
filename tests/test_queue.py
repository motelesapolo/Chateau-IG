from datetime import datetime, timezone

from autopilot import queue as q


def item(**kw):
    base = {
        "id": "2026-11-24-reel-prueba",
        "type": "reel",
        "publish_at": "2026-11-24T19:30:00-03:00",
        "caption": "Hola #prueba",
        "scenes": [
            {"visual": {"source": "card", "bg": "#111111"}, "text": "Gancho", "duration": 3},
            {"visual": {"source": "pollinations", "prompt": "a cat"}, "narration": "Hola", "duration": 4},
        ],
    }
    base.update(kw)
    return base


def test_valid_reel(project):
    assert q.validate(item()) == []


def test_errors(project):
    bad = item(id="Mal ID", type="video", caption="", publish_at="mañana")
    errs = " ".join(q.validate(bad))
    assert "id inválido" in errs and "type debe" in errs and "publish_at" in errs


def test_carousel_rules(project):
    one = item(type="carousel", scenes=[{"visual": {"source": "card"}}])
    assert any("2–10" in e for e in q.validate(one))
    vid = item(type="carousel", scenes=[{"visual": {"source": "pixabay_video", "query": "x"}}] * 2)
    assert any("no puede usar video" in e for e in q.validate(vid))


def test_reel_duration(project):
    long = item(scenes=[{"visual": {"source": "card"}, "duration": 30}] * 4)
    assert any("3–90" in e for e in q.validate(long))


def test_missing_file(project):
    it = item(type="image", scenes=[{"visual": {"source": "file", "path": "assets/images/no.jpg"}}])
    assert any("no existe" in e for e in q.validate(it))


def test_is_video(project):
    assert q.is_video(item())
    story = item(type="story", scenes=[{"visual": {"source": "card"}, "text": "hoy"}])
    assert not q.is_video(story)
    story["scenes"][0]["narration"] = "hola"
    assert q.is_video(story)


def test_due_items(project):
    a = item(id="2026-11-24-a", status="rendered", publish_at="2026-11-24T10:00:00-03:00")
    b = item(id="2026-11-24-b", status="rendered", publish_at="2026-11-26T10:00:00-03:00")
    c = item(id="2026-11-24-c", status="planned", publish_at="2026-11-20T10:00:00-03:00")
    for it in (a, b, c):
        q.save(it)
    now = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)
    due = q.due_items(now, max_late_hours=20)
    assert [d[1]["id"] for d in due] == ["2026-11-24-a"]
    assert due[0][2] is False
    late = q.due_items(datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc), max_late_hours=5)
    assert late[0][2] is True
