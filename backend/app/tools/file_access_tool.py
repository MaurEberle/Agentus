from __future__ import annotations

import base64
import fnmatch
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult

FILE_ACTION_ORDER = (
    "list",
    "stat",
    "read",
    "read_many",
    "write",
    "mkdir",
    "delete",
    "edit",
    "move",
    "search",
    "tree",
)
ACTIONS = frozenset(FILE_ACTION_ORDER)
WRITE_ACTIONS = frozenset({"write", "mkdir", "edit", "move"})
DELETE_ACTIONS = frozenset({"delete"})
ENCODINGS = frozenset({"utf-8", "base64"})
MAX_READ_BYTES = 1_048_576
MAX_WRITE_BYTES = 1_048_576
MAX_LIST_ENTRIES = 500
MAX_SEARCH = 200
MAX_TREE_NODES = 200
MAX_TREE_DEPTH = 4
MAX_READ_MANY = 8


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
    chosen = _chosen_actions(cfg)
    if chosen is not None and action not in chosen:
        return _fail("tools.fileAccess.disabled")

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
            return _read(root, target, encoding, head=_optional_int(raw_args.get("head")), tail=_optional_int(raw_args.get("tail")))
        if action == "read_many":
            return _read_many(root, raw_args.get("paths"), encoding)
        if action == "write":
            return _write(root, target, raw_args.get("content"), encoding)
        if action == "mkdir":
            return _mkdir(root, target, bool(raw_args.get("recursive")))
        if action == "edit":
            return _edit(root, target, raw_args)
        if action == "move":
            return _move(root, target, str(raw_args.get("destination") or ""))
        if action == "search":
            return _search(root, target, str(raw_args.get("pattern") or ""))
        if action == "tree":
            return _tree(root, target)
        return _delete(root, target)
    except FileNotFoundError:
        return _fail("tools.fileAccess.notFound")
    except PermissionError:
        return _fail("tools.fileAccess.denied")
    except OSError:
        return _fail("tools.fileAccess.denied")


def _chosen_actions(cfg: dict[str, Any]) -> set[str] | None:
    raw = cfg.get("fileActions")
    if not isinstance(raw, list):
        return None
    return {str(item) for item in raw if str(item) in ACTIONS}


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


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer() and value > 0:
        return int(value)
    return None


def _read(root: Path, target: Path, encoding: str, *, head: int | None = None, tail: int | None = None) -> ExecuteResult:
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
    if head is not None or tail is not None:
        lines = content.splitlines()
        if head is not None:
            lines = lines[:head]
        elif tail is not None:
            lines = lines[-tail:]
        content = "\n".join(lines)
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
    parent = target.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    elif not parent.is_dir():
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


def _read_many(root: Path, raw_paths: object, encoding: str) -> ExecuteResult:
    if not isinstance(raw_paths, list) or not raw_paths:
        return _fail("tools.fileAccess.invalidPath")
    if len(raw_paths) > MAX_READ_MANY:
        return _fail("tools.fileAccess.tooLarge", {"count": len(raw_paths), "max": MAX_READ_MANY})
    files: list[dict[str, object]] = []
    for item in raw_paths:
        target, err = _resolve(root, str(item or ""))
        if err or target is None:
            return _fail(err or "tools.fileAccess.invalidPath")
        one = _read(root, target, encoding)
        if not one.ok:
            return one
        files.append(one.result if isinstance(one.result, dict) else {"path": str(item)})
    return ExecuteResult(ok=True, result={"files": files})


def _edit_pairs(raw: dict[str, Any]) -> tuple[list[tuple[str, str]] | None, str | None]:
    edits = raw.get("edits")
    pairs: list[tuple[str, str]] = []
    if isinstance(edits, list):
        for item in edits:
            if not isinstance(item, dict):
                return None, "tools.fileAccess.invalidAction"
            old = item.get("oldText")
            new = item.get("newText")
            if not isinstance(old, str) or old == "" or not isinstance(new, str):
                return None, "tools.fileAccess.invalidAction"
            pairs.append((old, new))
    else:
        old = raw.get("oldText")
        new = raw.get("newText")
        if not isinstance(old, str) or old == "" or not isinstance(new, str):
            return None, "tools.fileAccess.invalidAction"
        pairs.append((old, new))
    if not pairs:
        return None, "tools.fileAccess.invalidAction"
    return pairs, None


def _edit(root: Path, target: Path, raw: dict[str, Any]) -> ExecuteResult:
    if not target.is_file():
        return _fail("tools.fileAccess.notFile")
    loaded = _read(root, target, "utf-8")
    if not loaded.ok or not isinstance(loaded.result, dict):
        return loaded
    text = str(loaded.result.get("content") or "")
    pairs, err = _edit_pairs(raw)
    if err or pairs is None:
        return _fail(err or "tools.fileAccess.invalidAction")
    for old, new in pairs:
        count = text.count(old)
        if count == 0:
            return _fail("tools.fileAccess.editMiss")
        if count > 1:
            return _fail("tools.fileAccess.editAmbiguous")
        text = text.replace(old, new, 1)
    rel = _rel(target, root)
    if bool(raw.get("dryRun")):
        return ExecuteResult(ok=True, result={"path": rel, "dryRun": True, "replacements": len(pairs)})
    data = text.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        return _fail("tools.fileAccess.tooLarge", {"size": len(data), "maxBytes": MAX_WRITE_BYTES})
    target.write_bytes(data)
    return ExecuteResult(ok=True, result={"path": rel, "bytes": len(data), "replacements": len(pairs)})


def _move(root: Path, source: Path, destination: str) -> ExecuteResult:
    if source == root or not source.exists():
        return _fail("tools.fileAccess.notFound")
    dest, err = _resolve(root, destination)
    if err or dest is None:
        return _fail(err or "tools.fileAccess.invalidPath")
    if dest == root or dest == source:
        return _fail("tools.fileAccess.invalidPath")
    if dest.exists():
        return _fail("tools.fileAccess.notFile")
    parent = dest.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    elif not parent.is_dir():
        return _fail("tools.fileAccess.notFound")
    source.rename(dest)
    return ExecuteResult(
        ok=True,
        result={"path": _rel(dest, root), "from": _rel(source, root)},
    )


def _search(root: Path, target: Path, pattern: str) -> ExecuteResult:
    if not target.is_dir():
        return _fail("tools.fileAccess.notDir")
    glob = pattern.strip()
    if not glob or "\x00" in glob:
        return _fail("tools.fileAccess.invalidPath")
    matches: list[str] = []
    truncated = False
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        try:
            if not path.resolve().is_relative_to(root):
                continue
        except OSError:
            continue
        rel = path.relative_to(target).as_posix()
        if fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(path.name, glob):
            if len(matches) >= MAX_SEARCH:
                truncated = True
                break
            matches.append(_rel(path, root))
    return ExecuteResult(
        ok=True,
        result={"path": _rel(target, root), "pattern": glob, "matches": matches, "truncated": truncated},
    )


def _tree(root: Path, target: Path) -> ExecuteResult:
    if not target.exists():
        return _fail("tools.fileAccess.notFound")
    if not target.is_dir():
        return _fail("tools.fileAccess.notDir")
    state = {"nodes": 0, "truncated": False}

    def walk(folder: Path, depth: int) -> list[dict[str, object]]:
        children: list[dict[str, object]] = []
        try:
            entries = sorted(folder.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            return children
        for child in entries:
            if state["nodes"] >= MAX_TREE_NODES:
                state["truncated"] = True
                break
            try:
                if not child.resolve().is_relative_to(root):
                    continue
            except OSError:
                continue
            state["nodes"] += 1
            kind = "dir" if child.is_dir() else "file"
            node: dict[str, object] = {"name": child.name, "type": kind}
            if kind == "dir" and depth < MAX_TREE_DEPTH:
                node["children"] = walk(child, depth + 1)
            children.append(node)
        return children

    return ExecuteResult(
        ok=True,
        result={
            "path": _rel(target, root),
            "children": walk(target, 1),
            "truncated": state["truncated"],
        },
    )
