"""Integración: rama claude/... → ingest → render → rama media → restore (con un remoto git local)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")


def sh(*args, cwd, env=None, check=True):
    proc = subprocess.run(list(args), cwd=cwd, env=env, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{args} falló:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


@pytest.fixture
def repos(tmp_path):
    origin = tmp_path / "origin.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    work = tmp_path / "work"
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "media"))
    (work / "media").mkdir()
    (work / "media" / ".gitkeep").touch()
    sh("git", "init", "-q", "-b", "main", cwd=work)
    sh("git", "config", "user.email", "t@t", cwd=work)
    sh("git", "config", "user.name", "t", cwd=work)
    sh("git", "remote", "add", "origin", str(origin), cwd=work)
    sh("git", "add", "-A", cwd=work)
    sh("git", "commit", "-qm", "init", cwd=work)
    sh("git", "push", "-q", "origin", "main", cwd=work)
    env = {**os.environ, "AUTOPILOT_ROOT": str(work), "DISABLE_TTS": "1", "GITHUB_REPOSITORY": "yo/micuenta"}
    return origin, work, env


def item(iid, **kw):
    return {"id": iid, "type": "image", "publish_at": "2026-11-24T19:30:00-03:00",
            "caption": "Hola #prueba", "scenes": [{"visual": {"source": "card"}, "text": "Hola"}], **kw}


def test_full_flow(repos, tmp_path):
    origin, work, env = repos
    py = sys.executable

    # Claude sube su lote a una rama claude/...
    sh("git", "checkout", "-qb", "claude/lote-1", cwd=work)
    (work / "queue" / "2026-11-24-img-uno.json").write_text(json.dumps(item("2026-11-24-img-uno")))
    (work / "queue" / "2026-11-25-img-malo.json").write_text(json.dumps(item("2026-11-25-img-malo", type="gif")))
    sh("git", "add", "queue", cwd=work)
    sh("git", "commit", "-qm", "lote", cwd=work)
    sh("git", "push", "-q", "origin", "claude/lote-1", cwd=work)
    sh("git", "checkout", "-q", "main", cwd=work)
    sh("git", "fetch", "-q", "origin", "claude/lote-1", cwd=work)

    # El Action incorpora solo lo válido
    out = sh(py, "scripts/ingest_branch.py", "origin/claude/lote-1", cwd=work, env=env)
    assert "Nuevas o actualizadas: **1**" in out and "Inválidas" in out
    assert (work / "queue" / "2026-11-24-img-uno.json").exists()
    assert not (work / "queue" / "2026-11-25-img-malo.json").exists()

    # Render + rama media
    sh(py, "scripts/render_queue.py", cwd=work, env=env)
    data = json.loads((work / "queue" / "2026-11-24-img-uno.json").read_text())
    assert data["status"] == "rendered"
    files = sh("git", "ls-tree", "-r", "--name-only", "media", cwd=origin).split()
    assert "media/2026-11-24-img-uno/post.jpg" in files

    # main solo lleva la vista previa (los pesados quedan fuera por .gitignore)
    sh("git", "add", "-A", "queue", "media", cwd=work)
    staged = sh("git", "diff", "--cached", "--name-only", cwd=work).split()
    assert "media/2026-11-24-img-uno/preview.jpg" in staged
    assert "media/2026-11-24-img-uno/post.jpg" not in staged

    # Un clon nuevo (como el runner de publicar) recupera los archivos desde la rama media
    clone = tmp_path / "clone"
    sh("git", "clone", "-q", str(origin), str(clone), cwd=tmp_path)
    env2 = {**env, "AUTOPILOT_ROOT": str(clone)}
    sh(py, "-c", "import sys; sys.path.insert(0,'.'); from autopilot import hosting; print(hosting.restore())",
       cwd=clone, env=env2)
    assert (clone / "media/2026-11-24-img-uno/post.jpg").exists()
    sha = sh(py, "-c", "import sys; sys.path.insert(0,'.'); from autopilot import hosting; "
                       "print(hosting.public_url('media/x.jpg', hosting.media_sha()))", cwd=clone, env=env2)
    assert sha.startswith("https://cdn.jsdelivr.net/gh/yo/micuenta@")

    # Ya publicado → un lote posterior con el mismo id se ignora
    shutil.move(work / "queue" / "2026-11-24-img-uno.json", work / "published" / "2026-11-24-img-uno.json")
    out = sh(py, "scripts/ingest_branch.py", "origin/claude/lote-1", cwd=work, env=env)
    assert "ya publicado" in out

    # La rama media se reescribe y deja de guardar lo publicado
    sh(py, "scripts/render_queue.py", cwd=work, env=env)
    files = sh("git", "ls-tree", "-r", "--name-only", "media", cwd=origin).split()
    assert files == ["README.md"]
    assert sh("git", "rev-list", "--count", "media", cwd=origin).strip() == "1"
