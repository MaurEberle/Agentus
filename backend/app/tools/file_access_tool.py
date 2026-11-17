from __future__ import annotations

import base64
import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult
from app.tools.sandbox import configured_root, is_forbidden_root, tool_fail

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
# File text one read returns, counted as it appears in the JSON result. With the
# envelope (path, line numbers) the whole result stays under the 4000 characters a
# tool result may have (app.mcp.payload.TOOL_RESULT_CHARS). The rest is paged with
# offset/limit instead of being cut off.
READ_PAGE_CHARS = 3000
# read_many splits the page between its files; each still gets this much.
READ_MANY_MIN_CHARS = 400


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    cfg = config or {}
    raw_args = args or {}
    root, root_error = configured_root(cfg, error_prefix="tools.fileAccess")
    if root is None:
        return _fail(root_error or "tools.fileAccess.missingRoot")

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
            return _read(
                root,
                target,
                encoding,
                head=_optional_int(raw_args.get("head")),
                tail=_optional_int(raw_args.get("tail")),
                offset=_optional_int(raw_args.get("offset")),
                limit=_optional_int(raw_args.get("limit")),
            )
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


_fail = tool_fail


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


def _load(target: Path) -> tuple[bytes | None, ExecuteResult | None]:
    """Whole file as bytes, or the failure to return."""
    if not target.exists():
        return None, _fail("tools.fileAccess.notFound")
    if not target.is_file():
        return None, _fail("tools.fileAccess.notFile")
    size = target.stat().st_size
    if size > MAX_READ_BYTES:
        return None, _fail("tools.fileAccess.tooLarge", {"size": size, "maxBytes": MAX_READ_BYTES})
    return target.read_bytes(), None


def _json_len(text: str) -> int:
    """Length of ``text`` inside a JSON string (line breaks and quotes count double)."""
    return len(json.dumps(text, ensure_ascii=False)) - 2


def _clip_line(line: str, limit: int) -> str:
    """Head and tail of one line that is longer than a whole page."""
    room = max(40, limit - 60)
    head = int(room * 0.7)
    tail = room - head
    omitted = len(line) - head - tail
    return f"{line[:head]}[... {omitted} characters of this line omitted ...]{line[len(line) - tail:]}"


def _read(
    root: Path,
    target: Path,
    encoding: str,
    *,
    head: int | None = None,
    tail: int | None = None,
    offset: int | None = None,
    limit: int | None = None,
    budget: int = READ_PAGE_CHARS,
) -> ExecuteResult:
    """One page of a file.

    The text is returned line by line up to ``budget`` characters. ``lines`` is the
    size of the file, ``startLine``/``endLine`` the part in ``content``. When lines
    follow, ``nextOffset`` is the ``offset`` for the next read; ``truncated`` says the
    page ended before the requested range did. Nothing is cut off silently (H6).
    """
    data, failed = _load(target)
    if failed is not None or data is None:
        return failed or _fail("tools.fileAccess.notFound")
    rel = _rel(target, root)
    if encoding == "base64":
        content = base64.b64encode(data).decode("ascii")
        if len(content) > budget:
            return _fail(
                "tools.fileAccess.tooLarge",
                {"size": len(data), "maxBytes": (budget * 3) // 4},
            )
        return ExecuteResult(
            ok=True,
            result={"path": rel, "content": content, "encoding": encoding, "bytes": len(data)},
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _fail("tools.fileAccess.notText")
    # Line endings stay: the text of a page is the exact text of those lines.
    lines = text.splitlines(keepends=True)
    total = len(lines)
    if tail is not None and offset is None and limit is None and head is None:
        start = max(0, total - tail)
        stop = total
    else:
        start = min(total, offset - 1) if offset else 0
        count = limit if limit is not None else head
        stop = total if count is None else min(total, start + count)
    picked: list[str] = []
    used = 0
    index = start
    clipped = False
    while index < stop:
        line = lines[index]
        cost = _json_len(line)
        if picked and used + cost > budget:
            break
        if not picked and cost > budget:
            picked.append(_clip_line(line, budget))
            clipped = True
            index += 1
            break
        picked.append(line)
        used += cost
        index += 1
    result: dict[str, object] = {
        "path": rel,
        "content": "".join(picked),
        "encoding": encoding,
        "bytes": len(data),
        "lines": total,
    }
    if picked:
        result["startLine"] = start + 1
        result["endLine"] = index
    if index < stop or clipped:
        result["truncated"] = True
    if index < total:
        result["nextOffset"] = index + 1
    return ExecuteResult(ok=True, result=result)


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
    # The files share one page; a file that does not fit says so with nextOffset.
    share = max(READ_MANY_MIN_CHARS, READ_PAGE_CHARS // len(raw_paths))
    for item in raw_paths:
        target, err = _resolve(root, str(item or ""))
        if err or target is None:
            return _fail(err or "tools.fileAccess.invalidPath")
        one = _read(root, target, encoding, budget=share)
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
    # The edit works on the whole file, not on one read page.
    data, failed = _load(target)
    if failed is not None or data is None:
        return failed or _fail("tools.fileAccess.notFound")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _fail("tools.fileAccess.notText")
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
