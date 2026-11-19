import logging
from datetime import datetime, timezone

from autopilot import config
from autopilot.inbox import Inbox, State, crisis_message

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
SETTINGS = {"inbox": {"posts_to_scan": 5, "comment_max_age_days": 7, "max_comment_replies_per_run": 10,
                      "max_dm_replies_per_run": 10}}
PERSONA = """# Persona
## Mensaje para situaciones de crisis (se envía tal cual)
Mensaje de ayuda con *4141.

## Enlaces permitidos
"""


class FakeClient:
    username = "micuenta"
    ig_id = "178"

    def __init__(self):
        self.replies, self.hidden, self.sent, self.posts = [], [], [], []
        self.media = [{"id": "M1", "caption": "Receta de pan", "comments_count": 5}]
        self.comments = {"M1": [
            {"id": "c1", "text": "¿Cuánta harina lleva?", "timestamp": "2026-11-24T12:00:00+0000",
             "from": {"id": "u1", "username": "ana"}},
            {"id": "c2", "text": "Gracias!", "timestamp": "2026-11-24T12:05:00+0000",
             "from": {"id": "178", "username": "micuenta"}},                       # mío
            {"id": "c3", "text": "Ya respondido", "timestamp": "2026-11-24T12:06:00+0000",
             "from": {"id": "u2", "username": "beto"},
             "replies": {"data": [{"id": "r1", "from": {"username": "micuenta"}}]}},
            {"id": "c4", "text": "compra seguidores en mi link", "timestamp": "2026-11-24T12:07:00+0000",
             "from": {"id": "u3", "username": "spam"}},
            {"id": "c5", "text": "viejo", "timestamp": "2026-11-01T12:00:00+0000",
             "from": {"id": "u4", "username": "old"}},
            {"id": "c6", "text": "a veces quiero morir", "timestamp": "2026-11-24T12:09:00+0000",
             "from": {"id": "u5", "username": "triste"}},
        ]}
        self.convs = [{"id": "T1", "updated_time": "2026-11-24T14:00:00+0000"},
                      {"id": "T2", "updated_time": "2026-11-24T14:10:00+0000"},
                      {"id": "T3", "updated_time": "2026-11-20T10:00:00+0000"}]
        self.msgs = {
            "T1": [{"id": "m2", "created_time": "2026-11-24T14:00:00+0000", "message": "hola! hacen envíos?",
                    "from": {"id": "u7", "username": "carla"}},
                   {"id": "m1", "created_time": "2026-11-24T13:00:00+0000", "message": "buenas",
                    "from": {"id": "u7", "username": "carla"}}],
            "T2": [{"id": "m9", "created_time": "2026-11-24T14:10:00+0000", "message": "¡Gracias a ti!",
                    "from": {"id": "178", "username": "micuenta"}}],
            "T3": [{"id": "m5", "created_time": "2026-11-20T10:00:00+0000", "message": "hola?",
                    "from": {"id": "u8", "username": "lento"}}],
        }

    def list_media(self, limit):
        return self.media

    def list_comments(self, media_id):
        return self.comments[media_id]

    def reply_comment(self, cid, msg):
        self.replies.append((cid, msg))

    def hide_comment(self, cid):
        self.hidden.append(cid)

    def list_conversations(self, limit):
        return self.convs

    def conversation_messages(self, cid, limit):
        return self.msgs[cid]

    def send_message(self, uid, text):
        self.sent.append((uid, text))

    def post(self, path, params=None, json_body=None):
        self.posts.append((path, json_body))


class FakeLLM:
    def __init__(self):
        self.prompts = []

    def json_chat(self, system, user, temperature=0.6):
        self.prompts.append(user)
        if "compra seguidores" in user:
            return {"action": "hide"}
        if "harina" in user:
            return {"action": "reply", "text": "¡500 g! 🍞"}
        if "envíos" in user:
            return {"action": "reply", "text": "¡Hola Carla! Por ahora no hacemos envíos."}
        return {"action": "skip"}


def make(project, client=None, llm=None):
    state = State(config.STATE_DIR / "inbox.json")
    return Inbox(client or FakeClient(), llm or FakeLLM(), PERSONA, SETTINGS, state,
                 now=NOW, sleep=lambda s: None)


def test_comments_and_dms(project, caplog):
    caplog.set_level(logging.DEBUG)
    inbox = make(project)
    stats = inbox.run()
    c = inbox.c
    assert c.replies == [("c1", "¡500 g! 🍞")]
    assert c.hidden == ["c4"]
    assert stats.crisis == 1 and stats.flagged == 1
    crisis_post = [p for p in c.posts if p[1]["recipient"] == {"comment_id": "c6"}]
    assert crisis_post and "*4141" in crisis_post[0][1]["message"]["text"]
    assert c.sent == [("u7", "¡Hola Carla! Por ahora no hacemos envíos.")]   # T2 es mío, T3 vencido
    # el mensaje de crisis no pasa por el modelo
    assert not any("quiero morir" in p for p in inbox.llm.prompts)
    # privacidad: ningún texto de usuarios en los logs
    for secret in ("harina", "envíos", "quiero morir", "500 g"):
        assert secret not in caplog.text


def test_second_run_does_not_repeat(project):
    client = FakeClient()
    make(project, client).run()
    replies, sent = list(client.replies), list(client.sent)
    llm2 = FakeLLM()
    make(project, client, llm2).run()
    assert client.replies == replies and client.sent == sent
    assert llm2.prompts == []


def test_dm_history_order(project):
    llm = FakeLLM()
    make(project, llm=llm).run()
    dm_prompt = [p for p in llm.prompts if "Conversación" in p][0]
    assert dm_prompt.index("buenas") < dm_prompt.index("hacen envíos")


def test_model_failure_retries_next_run(project):
    class Broken:
        def json_chat(self, *a, **k):
            raise RuntimeError("caído")

    client = FakeClient()
    make(project, client, Broken()).run()
    assert client.replies == [] and client.sent == []
    make(project, client).run()          # en la siguiente vuelta sí responde
    assert ("c1", "¡500 g! 🍞") in client.replies


def test_dry_run_sends_nothing(project):
    client = FakeClient()
    inbox = make(project, client)
    inbox.dry = True
    stats = inbox.run()
    assert stats.comments_replied == 1 and client.replies == [] and client.sent == []


def test_crisis_message_from_persona():
    assert crisis_message(PERSONA) == "Mensaje de ayuda con *4141."
    assert "emergencia" in crisis_message("# sin sección")
