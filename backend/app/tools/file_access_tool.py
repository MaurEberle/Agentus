from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult

ACTIONS = frozenset({"list", "stat", "read", "write", "mkdir", "delete"})
WRITE_ACTIONS = frozenset({"write", "mkdir"})
DELETE_ACTIONS = frozenset({"delete"})
ENCODINGS = frozenset({"utf-8", "base64"})
MAX_READ_BYTES = 1_048_576
MAX_WRITE_BYTES = 1_048_576
MAX_LIST_ENTRIES = 500


def is_forbidden_root(path: Path) -> bool:
    try:
        real = path.expanduser().resolve()
    except OSError:
        return True
    drive, tail = os.path.splitdrive(str(real))
    return len(tail.strip("\\/")) == 0


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    cfg = config or {}
    raw_args = args or {}
    root_raw = str(cfg.get("rootPath") or cfg.get("root") or "").strip()
    if not root_raw:
        return _fail("tools.fileAccess.missingRoot")
    root_in = Path(root_raw).expanduser()
    if not root_in.is_absolute():
        return _fail("tools.fileAccess.rootNotDir")
    try:
        root = root_in.resolve()
    except OSError:
        return _fail("tools.fileAccess.rootNotDir")
    if not root.is_dir() or is_forbidden_root(root):
        return _fail("tools.fileAccess.rootNotDir")

    action = str(raw_args.get("action") or "").strip().lower()
    if action not in ACTIONS:
        return _fail("tools.fileAccess.invalidAction")

    allow_write = cfg.get("allowWrite")
    if allow_write is None:
        allow_write = True
    allow_delete = cfg.get("allowDelete")
    if allow_delete is None:
        allow_delete = True
    if action in WRITE_ACTIONS and not allow_write:
        return _fail("tools.fileAccess.readOnly")
    if action in DELETE_ACTIONS and not allow_delete:
        return _fail("tools.fileAccess.deleteDenied")

    target, err = _resolve(root, str(raw_args.get("path") or ""))
    if err or target is None:
        return _fail(err or "tools.fileAccess.invalidPath")

    encoding = str(raw_args.get("encoding") or "utf-8").strip().lower() or "utf-8"
    if encoding not in ENCODINGS:
        return _fail("tools.fileAccess.invalidAction")

    try:
        if action == "list":
            return _list(root, target)
        if action == "stat":
            return _stat(root, target)
        if action == "read":
            return _read(root, target, encoding)
        if action == "write":
            return _write(root, target, raw_args.get("content"), encoding)
        if action == "mkdir":
            return _mkdir(root, target, bool(raw_args.get("recursive")))
        return _delete(root, target)
    except FileNotFoundError:
        return _fail("tools.fileAccess.notFound")
    except PermissionError:
        return _fail("tools.fileAccess.denied")
    except OSError:
        return _fail("tools.fileAccess.denied")


def _fail(key: str, result: object | None = None) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key, result=result)


def _rel(path: Path, root: Path) -> str:
    if path == root:
        return "."
    return path.relative_to(root).as_posix()


def _resolve(root: Path, raw: str) -> tuple[Path | None, str | None]:
    text = (raw or "").strip()
    if not text or text in {".", "./", ".\\"}:
        return root, None
    if "\x00" in text:
        return None, "tools.fileAccess.invalidPath"
    candidate = Path(text)
    joined = candidate if candidate.is_absolute() else (root / candidate)
    try:
        resolved = joined.resolve()
    except OSError:
        return None, "tools.fileAccess.invalidPath"
    if not resolved.is_relative_to(root):
        return None, "tools.fileAccess.outsideRoot"
    return resolved, None


def _list(root: Path, target: Path) -> ExecuteResult:
    if not target.exists():
        return _fail("tools.fileAccess.notFound")
    if not target.is_dir():
        return _fail("tools.fileAccess.notDir")
    entries: list[dict[str, object]] = []
    truncated = False
    try:
        children = sorted(target.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return _fail("tools.fileAccess.denied")
    for child in children:
        if len(entries) >= MAX_LIST_ENTRIES:
            truncated = True
            break
        kind = "dir" if child.is_dir() else "file"
        size = None
        if kind == "file":
            try:
                size = child.stat().st_size
            except OSError:
                size = None
        entries.append({"name": child.name, "type": kind, "size": size})
    return ExecuteResult(
        ok=True,
        result={"path": _rel(target, root), "entries": entries, "truncated": truncated},
    )


def _stat(root: Path, target: Path) -> ExecuteResult:
    if not target.exists():
        return _fail("tools.fileAccess.notFound")
    info = target.stat()
    kind = "dir" if target.is_dir() else "file"
    modified = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat()
    return ExecuteResult(
        ok=True,
        result={
            "path": _rel(target, root),
            "type": kind,
            "size": info.st_size if kind == "file" else None,
            "modified": modified,
        },
    )


def _read(root: Path, target: Path, encoding: str) -> ExecuteResult:
    if not target.exists():
        return _fail("tools.fileAccess.notFound")
    if not target.is_file():
        return _fail("tools.fileAccess.notFile")
    size = target.stat().st_size
    if size > MAX_READ_BYTES:
        return _fail("tools.fileAccess.tooLarge", {"size": size, "maxBytes": MAX_READ_BYTES})
    data = target.read_bytes()
    if encoding == "base64":
        content = base64.b64encode(data).decode("ascii")
    else:
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            return _fail("tools.fileAccess.notText")
    return ExecuteResult(
        ok=True,
        result={
            "path": _rel(target, root),
            "content": content,
            "encoding": encoding,
            "bytes": len(data),
        },
    )


def _write(root: Path, target: Path, content: object, encoding: str) -> ExecuteResult:
    if target == root:
        return _fail("tools.fileAccess.notFile")
    if target.exists() and target.is_dir():
        return _fail("tools.fileAccess.notFile")
    if not target.parent.exists() or not target.parent.is_dir():
        return _fail("tools.fileAccess.notFound")
    if content is None:
        return _fail("tools.fileAccess.missingContent")
    text = str(content)
    if encoding == "base64":
        try:
            data = base64.b64decode(text, validate=True)
        except (ValueError, OSError):
            return _fail("tools.fileAccess.invalidAction")
    else:
        data = text.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        return _fail("tools.fileAccess.tooLarge", {"size": len(data), "maxBytes": MAX_WRITE_BYTES})
    target.write_bytes(data)
    return ExecuteResult(
        ok=True,
        result={"path": _rel(target, root), "bytes": len(data)},
    )


def _mkdir(root: Path, target: Path, recursive: bool) -> ExecuteResult:
    if target == root:
        return ExecuteResult(ok=True, result={"path": ".", "existed": True})
    if target.exists():
        if target.is_dir():
            return ExecuteResult(ok=True, result={"path": _rel(target, root), "existed": True})
        return _fail("tools.fileAccess.notDir")
    target.mkdir(parents=recursive, exist_ok=False)
    return ExecuteResult(ok=True, result={"path": _rel(target, root), "existed": False})


def _delete(root: Path, target: Path) -> ExecuteResult:
    if target == root:
        return _fail("tools.fileAccess.outsideRoot")
    if not target.exists():
        return _fail("tools.fileAccess.notFound")
    rel = _rel(target, root)
    if target.is_dir():
        try:
            target.rmdir()
        except OSError:
            return _fail("tools.fileAccess.notEmpty")
        return ExecuteResult(ok=True, result={"path": rel, "deleted": "dir"})
    target.unlink()
    return ExecuteResult(ok=True, result={"path": rel, "deleted": "file"})
