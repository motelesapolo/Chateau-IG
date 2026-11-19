import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from autopilot import config  # noqa: E402


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Copia mínima del proyecto en una carpeta temporal."""
    shutil.copytree(ROOT / "config", tmp_path / "config")
    for d in ("queue", "published", "media", "assets/images", "assets/music", "reports"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(config, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(config, "PUBLISHED_DIR", tmp_path / "published")
    monkeypatch.setattr(config, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(config, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / ".state")
    monkeypatch.setenv("DISABLE_TTS", "1")
    return tmp_path
