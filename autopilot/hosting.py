"""Dónde viven los archivos que Instagram descarga.

La API de Instagram (con Instagram Login) descarga imágenes y videos desde una URL pública.
Usamos la rama `media` de este mismo repo público, servida por la CDN gratuita jsDelivr,
fijada a un commit exacto (así la URL nunca cambia mientras Instagram la descarga).

La rama `media` se reescribe en cada render y solo guarda lo que falta por publicar,
para que el repo no crezca sin límite.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from . import config

BRANCH = "media"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd or config.ROOT, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falló: {proc.stderr.strip()}")
    return proc.stdout.strip()


def repo_slug() -> str:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    url = git("remote", "get-url", "origin")
    url = url.removesuffix(".git")
    return "/".join(url.replace(":", "/").split("/")[-2:])


def media_sha() -> str | None:
    out = git("ls-remote", "origin", f"refs/heads/{BRANCH}", check=False)
    return out.split()[0] if out else None


def public_url(rel_path: str, sha: str) -> str:
    return f"https://cdn.jsdelivr.net/gh/{repo_slug()}@{sha}/{rel_path}"


def raw_url(rel_path: str, sha: str) -> str:
    return f"https://raw.githubusercontent.com/{repo_slug()}/{sha}/{rel_path}"


def reachable_url(rel_path: str, sha: str) -> str:
    """Prefiere jsDelivr (tipo de archivo correcto); si no responde, usa raw.githubusercontent."""
    for url in (public_url(rel_path, sha), raw_url(rel_path, sha)):
        try:
            r = requests.get(url, stream=True, timeout=60)
            ok = r.status_code == 200
            r.close()
            if ok:
                return url
        except requests.RequestException:
            continue
    raise RuntimeError(f"El archivo {rel_path} no es accesible públicamente (¿el repo es público?)")


def restore() -> int:
    """Trae a media/ los archivos ya renderizados que están en la rama media."""
    if git("ls-remote", "origin", f"refs/heads/{BRANCH}", check=False) == "":
        return 0
    git("fetch", "--depth", "1", "origin", BRANCH)
    files = git("ls-tree", "-r", "--name-only", "FETCH_HEAD", "--", "media").splitlines()
    for name in files:
        dest = config.ROOT / name
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob = subprocess.run(["git", "show", f"FETCH_HEAD:{name}"], cwd=config.ROOT,
                              capture_output=True, check=True).stdout
        dest.write_bytes(blob)
    return len(files)


def sync(keep_ids: set[str]) -> str | None:
    """Reescribe la rama media con solo los archivos de `keep_ids`. Devuelve el nuevo sha."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "wt"
        git("worktree", "add", "--detach", str(wt), "HEAD")
        try:
            git("checkout", "--orphan", "media-sync-tmp", cwd=wt)
            git("rm", "-rfq", "--ignore-unmatch", ".", cwd=wt)
            for leftover in wt.iterdir():
                if leftover.name != ".git":
                    shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()
            (wt / "README.md").write_text(
                "Rama automática: archivos pendientes de publicar. No editar a mano.\n")
            for iid in sorted(keep_ids):
                src = config.MEDIA_DIR / iid
                if src.is_dir():
                    shutil.copytree(src, wt / "media" / iid)
            git("add", "-A", cwd=wt)
            git("-c", "user.name=ig-autopilot", "-c", "user.email=ig-autopilot@users.noreply.github.com",
                "commit", "-qm", f"media: {len(keep_ids)} publicaciones pendientes", cwd=wt)
            git("push", "-f", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=wt)
            return git("rev-parse", "HEAD", cwd=wt)
        finally:
            git("worktree", "remove", "--force", str(wt), check=False)
            git("branch", "-D", "media-sync-tmp", check=False)
