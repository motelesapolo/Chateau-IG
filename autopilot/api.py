"""Cliente mínimo de la API oficial de Instagram (Instagram API with Unified Login).

Las apps de Meta creadas desde fines de 2026 solo ofrecen "Unified login": Facebook Login for
Business con una configuración que entrega un token de usuario del sistema del negocio
(no vence si la configuración dice "Nunca"). No requiere página de Facebook.
Host: graph.facebook.com. Las llamadas van a /{id-de-la-cuenta-de-instagram}/...
Permisos: instagram_basic, instagram_content_publish, instagram_manage_comments,
instagram_manage_messages, instagram_manage_insights.

También funciona con el modo antiguo "Instagram Login" usando host=graph.instagram.com.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

HOST = "https://graph.facebook.com"


class InstagramError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, code: int | None = None,
                 subcode: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.subcode = subcode
        self.payload = payload

    @property
    def is_rate_limit(self) -> bool:
        return self.code in {4, 17, 32, 613} or self.subcode == 2207042 or self.status == 429


class InstagramClient:
    def __init__(self, access_token: str, api_version: str = "v26.0", ig_user_id: str | None = None,
                 host: str = HOST, session: requests.Session | None = None, sleep=time.sleep):
        self.token = access_token
        self.version = api_version
        self.host = host.rstrip("/")
        self.http = session or requests.Session()
        self.sleep = sleep
        self._ig_id = str(ig_user_id) if ig_user_id else None
        self._me: dict | None = None

    # ------------------------------------------------------------------ base
    def _url(self, path: str) -> str:
        return f"{self.host}/{self.version}/{path.lstrip('/')}"

    def request(self, method: str, path: str, params: dict | None = None,
                json_body: dict | None = None, retries: int = 3) -> dict:
        params = dict(params or {})
        params["access_token"] = self.token
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self.http.request(method, self._url(path), params=params,
                                         json=json_body, timeout=60)
            except requests.RequestException as exc:  # red caída, timeout
                last_exc = exc
                self.sleep(2 ** attempt * 3)
                continue
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text[:500]}
            if resp.status_code < 400 and not (isinstance(data, dict) and "error" in data):
                return data
            err = data.get("error", {}) if isinstance(data, dict) else {}
            exc = InstagramError(
                err.get("error_user_msg") or err.get("message") or f"HTTP {resp.status_code}",
                status=resp.status_code, code=err.get("code"),
                subcode=err.get("error_subcode"), payload=data,
            )
            transient = resp.status_code >= 500 or err.get("is_transient") or err.get("code") in {1, 2}
            if transient and attempt < retries - 1:
                last_exc = exc
                self.sleep(2 ** attempt * 5)
                continue
            raise exc
        raise InstagramError(f"Sin respuesta de Instagram: {last_exc}")

    def get(self, path: str, **params) -> dict:
        return self.request("GET", path, params=params)

    def post(self, path: str, params: dict | None = None, json_body: dict | None = None) -> dict:
        return self.request("POST", path, params=params, json_body=json_body)

    # --------------------------------------------------------------- cuenta
    def discover_ig_id(self) -> str:
        """Busca el ID de la cuenta de Instagram a la que el token tiene acceso."""
        if "graph.instagram.com" in self.host:  # modo antiguo: /me es la cuenta
            me = self.get("me", fields="user_id,username")
            return str(me.get("user_id") or me["id"])
        errors = []
        for path in ("me/assigned_instagram_accounts", "me/instagram_accounts"):
            try:
                data = self.get(path, fields="id,username").get("data", [])
            except InstagramError as exc:
                errors.append(f"{path}: {exc}")
                continue
            if data:
                wanted = (os.environ.get("IG_USERNAME") or "").lower().lstrip("@")
                for acc in data:
                    if not wanted or acc.get("username", "").lower() == wanted:
                        return str(acc["id"])
                return str(data[0]["id"])
        raise InstagramError("No se encontró la cuenta de Instagram con este token. Agrega la variable "
                             "IG_USER_ID con el ID de la cuenta (ver SETUP.md). " + " | ".join(errors))

    @property
    def ig_id(self) -> str:
        if not self._ig_id:
            self._ig_id = self.discover_ig_id()
        return self._ig_id

    def me(self) -> dict:
        if self._me is None:
            self._me = self.get(self.ig_id, fields="id,username,name,media_count,followers_count")
        return self._me

    @property
    def username(self) -> str:
        return self.me().get("username", "")

    def publishing_limit(self) -> dict:
        data = self.get(f"{self.ig_id}/content_publishing_limit", fields="quota_usage,config")
        return (data.get("data") or [{}])[0]

    # ------------------------------------------------------------ publicar
    OPTIONAL_PARAMS = ("is_ai_generated", "location_id", "collaborators", "alt_text", "audio_configuration")

    def search_audio(self, query: str = "", audio_type: str = "music") -> list[dict]:
        """Música de la biblioteca de Instagram autorizada para publicar por API (Audio API)."""
        params = {"audio_type": audio_type, "user_id": self.ig_id}
        if query:
            params["search_query"] = query
        return self.request("GET", "ig_audio", params=params).get("data", [])

    def _create_container(self, params: dict, ai_generated: bool, extra: dict | None = None) -> str:
        """Crea el contenedor. Los parámetros opcionales que la API rechace se quitan y se reintenta."""
        params = {k: v for k, v in params.items() if v is not None}
        if ai_generated:
            params["is_ai_generated"] = "true"
        for k, v in (extra or {}).items():
            if v:
                params[k] = v
        for _ in range(len(self.OPTIONAL_PARAMS) + 1):
            try:
                return self.post(f"{self.ig_id}/media", params=params)["id"]
            except InstagramError as exc:
                text = str(exc.payload or exc)
                bad = [k for k in self.OPTIONAL_PARAMS if k in params and k in text]
                if not bad:
                    raise
                for k in bad:
                    log.warning("La API no aceptó %s; se publica sin ese dato: %s", k, exc)
                    params.pop(k)
        raise InstagramError("No se pudo crear el contenedor")

    def wait_until_ready(self, container_id: str, timeout: int = 900, every: int = 10) -> None:
        waited = 0
        while True:
            info = self.get(container_id, fields="status_code,status")
            code = info.get("status_code")
            if code in {"FINISHED", "PUBLISHED"}:
                return
            if code in {"ERROR", "EXPIRED"}:
                raise InstagramError(f"Instagram rechazó el archivo ({code}): {info.get('status')}",
                                     payload=info)
            if waited >= timeout:
                raise InstagramError(f"Instagram tardó demasiado en procesar {container_id}", payload=info)
            self.sleep(every)
            waited += every

    def _publish(self, container_id: str) -> dict:
        media_id = self.post(f"{self.ig_id}/media_publish", params={"creation_id": container_id})["id"]
        try:
            info = self.get(media_id, fields="id,permalink,media_type,timestamp")
        except InstagramError:
            info = {"id": media_id}
        return info

    def publish_image(self, image_url: str, caption: str, ai_generated: bool = True, extra: dict | None = None) -> dict:
        cid = self._create_container({"image_url": image_url, "caption": caption}, ai_generated, extra)
        self.wait_until_ready(cid, timeout=120, every=3)
        return self._publish(cid)

    def publish_carousel(self, image_urls: list[str], caption: str, ai_generated: bool = True,
                         extra: dict | None = None) -> dict:
        if not 2 <= len(image_urls) <= 10:
            raise ValueError("Un carrusel necesita entre 2 y 10 imágenes")
        children = []
        for url in image_urls:
            cid = self.post(f"{self.ig_id}/media",
                            params={"image_url": url, "is_carousel_item": "true"})["id"]
            children.append(cid)
        for cid in children:
            self.wait_until_ready(cid, timeout=180, every=3)
        # La etiqueta de IA va solo en el contenedor del carrusel.
        parent = self._create_container({"media_type": "CAROUSEL", "children": ",".join(children),
                                         "caption": caption}, ai_generated, extra)
        self.wait_until_ready(parent, timeout=180, every=3)
        return self._publish(parent)

    def publish_reel(self, video_url: str, caption: str, ai_generated: bool = True,
                     share_to_feed: bool = True, cover_url: str | None = None, extra: dict | None = None) -> dict:
        extra = {k: v for k, v in (extra or {}).items() if k != "alt_text"}
        cid = self._create_container({
            "media_type": "REELS", "video_url": video_url, "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false", "cover_url": cover_url,
        }, ai_generated, extra)
        self.wait_until_ready(cid)
        return self._publish(cid)

    def publish_story(self, image_url: str | None = None, video_url: str | None = None,
                      ai_generated: bool = True) -> dict:
        if bool(image_url) == bool(video_url):
            raise ValueError("Una historia lleva imagen o video (uno de los dos)")
        cid = self._create_container({"media_type": "STORIES", "image_url": image_url,
                                      "video_url": video_url}, ai_generated)
        self.wait_until_ready(cid, timeout=900 if video_url else 120)
        return self._publish(cid)

    # ----------------------------------------------------- media y métricas
    def list_media(self, limit: int = 12,
                   fields: str = "id,caption,timestamp,media_type,media_product_type,permalink,"
                                 "like_count,comments_count") -> list[dict]:
        return self.get(f"{self.ig_id}/media", fields=fields, limit=limit).get("data", [])

    def media_insights(self, media_id: str, metrics: str = "reach,views,saved,shares") -> dict:
        try:
            data = self.get(f"{media_id}/insights", metric=metrics).get("data", [])
        except InstagramError as exc:
            log.info("Sin métricas para %s: %s", media_id, exc)
            return {}
        out = {}
        for row in data:
            values = row.get("values") or [{}]
            out[row.get("name")] = row.get("total_value", {}).get("value", values[0].get("value"))
        return out

    # ---------------------------------------------------------- comentarios
    def list_comments(self, media_id: str, limit: int = 50) -> list[dict]:
        fields = ("id,text,timestamp,hidden,from,username,"
                  "replies{id,text,timestamp,from,username}")
        return self.get(f"{media_id}/comments", fields=fields, limit=limit).get("data", [])

    def reply_comment(self, comment_id: str, message: str) -> dict:
        return self.post(f"{comment_id}/replies", params={"message": message})

    def hide_comment(self, comment_id: str, hide: bool = True) -> dict:
        return self.post(comment_id, params={"hide": "true" if hide else "false"})

    # ------------------------------------------------------------- mensajes
    def list_conversations(self, limit: int = 20) -> list[dict]:
        return self.get(f"{self.ig_id}/conversations", platform="instagram",
                        fields="id,updated_time", limit=limit).get("data", [])

    def conversation_messages(self, conversation_id: str, limit: int = 10) -> list[dict]:
        """Mensajes más recientes primero."""
        data = self.get(conversation_id,
                        fields=f"messages.limit({limit}){{id,created_time,from,to,message}}")
        return (data.get("messages") or {}).get("data", [])

    def send_message(self, recipient_id: str, text: str) -> dict:
        encoded = text.encode("utf-8")
        if len(encoded) > 1000:  # límite de la API: 1000 bytes
            text = encoded[:990].decode("utf-8", errors="ignore").rsplit(" ", 1)[0] + "…"
        return self.post(f"{self.ig_id}/messages",
                         json_body={"recipient": {"id": recipient_id}, "message": {"text": text}})


def client_from_env(settings: dict) -> InstagramClient:
    """Crea el cliente con los secretos de GitHub Actions."""
    from . import config
    return InstagramClient(
        config.env("IG_ACCESS_TOKEN"),
        api_version=settings.get("api_version", "v26.0"),
        ig_user_id=os.environ.get("IG_USER_ID") or None,
        host=settings.get("api_host", HOST),
    )
