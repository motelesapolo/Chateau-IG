from datetime import datetime, timezone

from autopilot import review


def test_parse_decisions():
    body = "- [x] `2026-11-24-reel-a` · Mar\n- [ ] `2026-11-25-story-b` · Mié\n- [X] `c-1` · x"
    assert review.parse_decisions(body) == {"2026-11-24-reel-a": True, "2026-11-25-story-b": False, "c-1": True}


def test_build_body_keeps_previous_choices():
    from datetime import date
    items = [{"id": "a-1", "type": "reel", "publish_at": "2026-11-23T20:30:00-03:00", "caption": "Hola\nmás",
              "status": "rendered", "media": {"preview": "media/a-1/preview.jpg"}},
             {"id": "b-2", "type": "story", "publish_at": "2026-11-24T11:00:00-03:00", "status": "rendered",
              "scenes": [{"text": "Promo"}]}]
    body = review.build_body(date(2026, 11, 23), items, {"a-1": False}, "dueno/repo", "approve")
    assert "- [ ] `a-1` · **Lun 23 20:30** · Reel" in body
    assert "- [x] `b-2`" in body and "raw.githubusercontent.com/dueno/repo/main/media/a-1/preview.jpg" in body
    assert review.MARK_RE.search(body).group(1) == "2026-11-23"


def test_week_monday_uses_chile_time():
    # domingo 23:30 en Chile = lunes 02:30 UTC: sigue siendo la semana anterior
    assert str(review.week_monday(datetime(2026, 11, 30, 2, 30, tzinfo=timezone.utc))) == "2026-11-23"
