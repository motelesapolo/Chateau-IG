import json

import pytest

from autopilot.inbox import redact
from autopilot.llm import ChatLLM, llm_from_env, parse_json


class Resp:
    def __init__(self, status, data=None, text=None, headers=None):
        self.status_code = status
        self._data = data
        self.text = text if text is not None else json.dumps(data or {})
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.bodies.append((url, json))
        return self.responses.pop(0)


def ok(content):
    return Resp(200, {"choices": [{"message": {"content": content}}]})


def test_picks_gemini_when_only_gemini_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    llm = llm_from_env({"gemini_models": ["gemini-3.5-flash"]})
    assert llm.provider == "gemini" and "generativelanguage.googleapis.com" in llm.url
    assert llm.models == ["gemini-3.5-flash"]


def test_missing_key_explains(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        llm_from_env({})


def test_json_mode_fallback_and_fenced_json():
    sess = Session([Resp(400, text='{"error": "response_format not supported"}'),
                    ok('```json\n{"action": "reply", "text": "Hola"}\n```')])
    llm = ChatLLM("gemini", "k", ["m1"], session=sess, sleep=lambda s: None)
    assert llm.json_chat("s", "u") == {"action": "reply", "text": "Hola"}
    assert "response_format" in sess.bodies[0][1] and "response_format" not in sess.bodies[1][1]


def test_unavailable_model_falls_to_next():
    sess = Session([Resp(404, text="not found"), ok('{"action": "skip"}')])
    llm = ChatLLM("gemini", "k", ["viejo", "nuevo"], session=sess, sleep=lambda s: None)
    assert llm.json_chat("s", "u") == {"action": "skip"}
    assert sess.bodies[1][1]["model"] == "nuevo"


def test_parse_json_with_text_around():
    assert parse_json('Claro: {"action": "flag"} listo') == {"action": "flag"}


def test_redact_removes_personal_data():
    text = ("Hola soy @juanito.perez, mi cel es +56 9 1234 5678 y mi correo juan@gmail.com, "
            "mira www.algo.cl o https://x.com/abc ¿tienen jacuzzi?")
    out = redact(text)
    for leaked in ("juanito", "1234", "juan@gmail", "algo.cl", "x.com"):
        assert leaked not in out
    assert "¿tienen jacuzzi?" in out
