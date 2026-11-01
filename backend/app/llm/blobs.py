"""Remove the blob files an Ollama pull created for one model."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from app.common.http import client

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_IN_TEXT = re.compile(r"sha256:[0-9a-f]{64}")


def models_dir() -> Path:
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    if configured:
        return Path(configured)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        db_path = Path(local) / "Ollama" / "db.sqlite"
        if db_path.is_file():
            try:
                uri = db_path.resolve().as_posix()
                conn = sqlite3.connect(f"file:{uri}?mode=ro", uri=True)
                try:
                    row = conn.execute("SELECT models FROM settings LIMIT 1").fetchone()
                finally:
                    conn.close()
                if row and str(row[0]).strip():
                    return Path(str(row[0]).strip())
            except (OSError, sqlite3.Error):
                pass
    return Path.home() / ".ollama" / "models"


def parse_manifest_digests(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    found: list[str] = []
    config = payload.get("config")
    if isinstance(config, dict):
        digest = config.get("digest")
        if isinstance(digest, str) and _DIGEST.fullmatch(digest):
            found.append(digest)
    layers = payload.get("layers")
    if isinstance(layers, list):
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            digest = layer.get("digest")
            if isinstance(digest, str) and _DIGEST.fullmatch(digest) and digest not in found:
                found.append(digest)
    return found


def manifest_url(model: str) -> str | None:
    text = (model or "").strip()
    if not text:
        return None
    tag = "latest"
    body = text
    slash = text.rfind("/")
    colon = text.rfind(":")
    if colon > slash:
        body, tag = text[:colon], text[colon + 1 :]
    parts = [part for part in body.split("/") if part]
    if len(parts) == 3 and parts[0] in {"hf.co", "huggingface.co"}:
        return f"https://huggingface.co/v2/{parts[1]}/{parts[2]}/manifests/{tag}"
    if len(parts) == 1:
        return f"https://registry.ollama.ai/v2/library/{parts[0]}/manifests/{tag}"
    if len(parts) == 2:
        return f"https://registry.ollama.ai/v2/{parts[0]}/{parts[1]}/manifests/{tag}"
    if len(parts) == 3:
        return f"https://{parts[0]}/v2/{parts[1]}/{parts[2]}/manifests/{tag}"
    return None


def fetch_manifest_digests(model: str) -> list[str]:
    url = manifest_url(model)
    if not url:
        return []
    try:
        with client(timeout_sec=20.0) as http:
            response = http.get(
                url,
                headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            )
        if response.status_code >= 400:
            return []
        return parse_manifest_digests(response.json())
    except Exception:
        return []


def _referenced(manifests: Path) -> set[str]:
    found: set[str] = set()
    if not manifests.is_dir():
        return found
    for path in manifests.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found.update(_DIGEST_IN_TEXT.findall(text))
    return found


def _unlink(path: Path) -> None:
    for _ in range(5):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.2)


def discard_blob_files(digests: list[str], *, root: Path | None = None) -> None:
    """Delete partial downloads and finished blobs no manifest still names."""
    base = root or models_dir()
    blobs = base / "blobs"
    if not blobs.is_dir():
        return
    referenced = _referenced(base / "manifests")
    for digest in digests:
        if not _DIGEST.fullmatch(digest):
            continue
        stem = digest.replace(":", "-")
        for path in blobs.glob(stem + "-partial*"):
            _unlink(path)
        finished = blobs / stem
        if finished.is_file() and digest not in referenced:
            _unlink(finished)


def stored_digests(raw: str | None) -> list[str]:
    try:
        loaded = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, str) and _DIGEST.fullmatch(item)]
