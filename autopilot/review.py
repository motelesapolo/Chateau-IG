"""Revisión semanal del dueño en un issue de GitHub.

- Después de renderizar, `scripts/review_issue.py` crea (o actualiza) el issue "Revisión · semana del <lunes>"
  con una casilla por publicación y su vista previa.
- Casilla marcada = se publica. Desmarcada = no se publica (queda "cancelled").
  Con `review.default` = "require", las casillas parten desmarcadas y solo se publica lo que el dueño marque.
- Los cambios se piden en comentarios del issue; el lunes los aplica Claude (solo comentarios del dueño
  o colaboradores del repo).
- `scripts/publish_due.py` consulta el issue antes de publicar. Si GitHub no responde, espera a la siguiente vuelta.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

import requests

from . import config
from . import queue as q

LABEL = "revision"
MARK_RE = re.compile(r"<!-- review:(\d{4}-\d{2}-\d{2}) -->")
BOX_RE = re.compile(r"^- \[( |x|X)\] `([a-z0-9-]+)`", re.M)
DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
TYPES = {"reel": "Reel", "image": "Imagen", "carousel": "Carrusel", "story": "Historia"}


class ReviewUnavailable(RuntimeError):
    pass


def settings() -> dict:
    return {"enabled": True, "default": "approve", **(config.load_settings().get("review") or {})}


def week_monday(when: datetime) -> date:
    local = when.astimezone(config.timezone())
    return (local - timedelta(days=local.weekday())).date()


def parse_decisions(body: str) -> dict[str, bool]:
    return {m.group(2): m.group(1).lower() == "x" for m in BOX_RE.finditer(body or "")}


def _first_line(item: dict) -> str:
    text = (item.get("caption") or "").strip().splitlines()
    if text:
        return text[0][:90]
    scene = (item.get("scenes") or [{}])[0]
    return (scene.get("text") or "")[:90]


def build_body(monday: date, items: list[dict], previous: dict[str, bool], repo: str, default: str) -> str:
    sunday = monday + timedelta(days=6)
    lines = [
        f"<!-- review:{monday.isoformat()} -->",
        f"## Contenido del {monday:%d-%m} al {sunday:%d-%m}",
        "",
        "**Cómo revisar:**",
        "- ✅ Marcada = se publica. ⬜ Desmarcada = **no** se publica.",
        "- ¿Quieres un cambio (texto, foto, horario)? Escríbelo en un **comentario** antes del lunes a las 13:30, "
        "diciendo cuál (por ejemplo: *\"Reel del martes: cambia el título por ...\"*). Claude lo aplica y te responde aquí.",
        "- Si no tocas nada, se publica todo tal cual." if default == "approve"
        else "- Solo se publica lo que **marques**.",
        "",
    ]
    for item in sorted(items, key=lambda i: i["publish_at"]):
        when = q.parse_time(item["publish_at"]).astimezone(config.timezone())
        checked = previous.get(item["id"], default == "approve")
        status = item.get("status")
        note = " · ⚠️ falló el render" if status == "render_failed" else ""
        lines.append(f"- [{'x' if checked else ' '}] `{item['id']}` · **{DAYS[when.weekday()]} {when:%d %H:%M}** · "
                     f"{TYPES.get(item['type'], item['type'])}{note}")
        first = _first_line(item)
        if first:
            lines.append(f"  > {first}")
        if (item.get("media") or {}).get("preview"):
            lines.append(f"  <img src=\"https://raw.githubusercontent.com/{repo}/main/{item['media']['preview']}\" "
                         f"width=\"640\">")
        lines.append("")
    return "\n".join(lines)


class GitHub:
    def __init__(self, token: str | None = None, repo: str | None = None, session=None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY")
        self.http = session or requests
        if not self.token or not self.repo:
            raise ReviewUnavailable("Faltan GITHUB_TOKEN o GITHUB_REPOSITORY")

    def _req(self, method: str, path: str, **kw):
        r = self.http.request(method, f"https://api.github.com/repos/{self.repo}/{path}", timeout=30,
                              headers={"Authorization": f"Bearer {self.token}",
                                       "Accept": "application/vnd.github+json"}, **kw)
        if r.status_code >= 400:
            raise ReviewUnavailable(f"GitHub respondió {r.status_code}: {r.text[:200]}")
        return r.json()

    def review_issues(self) -> list[dict]:
        issues = self._req("GET", "issues", params={"labels": LABEL, "state": "open", "per_page": 20})
        return [i for i in issues if MARK_RE.search(i.get("body") or "")]

    def create(self, title: str, body: str) -> dict:
        return self._req("POST", "issues", json={"title": title, "body": body, "labels": [LABEL]})

    def update(self, number: int, body: str) -> dict:
        return self._req("PATCH", f"issues/{number}", json={"body": body})

    def comments(self, number: int) -> list[dict]:
        return self._req("GET", f"issues/{number}/comments", params={"per_page": 100})

    def comment(self, number: int, body: str) -> dict:
        return self._req("POST", f"issues/{number}/comments", json={"body": body})

    def close(self, number: int) -> dict:
        return self._req("PATCH", f"issues/{number}", json={"state": "closed"})


def decisions(gh: GitHub | None = None) -> dict[str, bool]:
    """Todas las decisiones de los issues de revisión abiertos (id → se publica)."""
    gh = gh or GitHub()
    out: dict[str, bool] = {}
    for issue in gh.review_issues():
        out.update(parse_decisions(issue.get("body") or ""))
    return out


def sync_issues(now: datetime, gh: GitHub | None = None) -> list[str]:
    """Crea o actualiza un issue por semana con lo que falta publicar; cierra los de semanas ya terminadas."""
    cfg = settings()
    gh = gh or GitHub()
    pending = [i for _, i in q.all_items() if i.get("status") in {"planned", "rendered", "render_failed"}]
    weeks: dict[date, list[dict]] = {}
    for item in pending:
        weeks.setdefault(week_monday(q.parse_time(item["publish_at"])), []).append(item)
    existing = {date.fromisoformat(MARK_RE.search(i["body"]).group(1)): i for i in gh.review_issues()}
    done = []
    for monday, items in sorted(weeks.items()):
        issue = existing.get(monday)
        previous = parse_decisions(issue["body"]) if issue else {}
        body = build_body(monday, items, previous, gh.repo, cfg["default"])
        if issue:
            if issue["body"] != body:
                gh.update(issue["number"], body)
            done.append(f"#{issue['number']} actualizado")
        else:
            new = gh.create(f"Revisión · semana del {monday:%d-%m-%Y}", body)
            done.append(f"#{new['number']} creado")
    this_monday = week_monday(now)
    for monday, issue in existing.items():
        if monday < this_monday and monday not in weeks:
            gh.close(issue["number"])
            done.append(f"#{issue['number']} cerrado")
    return done


REPLY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-.+\.md$")


def post_replies(gh: GitHub | None = None) -> list[str]:
    """Publica en el issue de su semana los mensajes de Claude guardados en reviews/<lunes>-<nombre>.md.

    Claude no tiene permiso para comentar en GitHub: deja el texto en el repo y este paso lo publica una vez.
    """
    gh = gh or GitHub()
    folder = config.ROOT / "reviews"
    if not folder.is_dir():
        return []
    issues = {MARK_RE.search(i["body"]).group(1): i for i in gh.review_issues()}
    done = []
    for path in sorted(folder.glob("*.md")):
        m = REPLY_RE.match(path.name)
        if not m or m.group(1) not in issues:
            continue
        issue = issues[m.group(1)]
        marker = f"<!-- reply:{path.name} -->"
        if any(marker in (c.get("body") or "") for c in gh.comments(issue["number"])):
            continue
        gh.comment(issue["number"], f"{marker}\n🤖 {path.read_text(encoding='utf-8').strip()}")
        done.append(f"comentario {path.name} en #{issue['number']}")
    return done
