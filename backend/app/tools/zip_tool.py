from __future__ import annotations

import stat
import zipfile
from pathlib import Path
from typing import Any

from app.tools.file_access_tool import _resolve, is_forbidden_root
from app.tools.models import ExecuteResult

ACTIONS = frozenset({"list", "extract"})
MAX_ENTRIES = 500
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    cfg = config or {}
    raw = args or {}
    root, root_error = _root(cfg)
    if root_error or root is None:
        return _fail(root_error or "tools.zip.missingRoot")
    action = str(raw.get("action") or "").strip().lower()
    if action not in ACTIONS:
        return _fail("tools.zip.invalidAction")
    archive, err = _resolve(root, str(raw.get("path") or ""))
    if err == "tools.fileAccess.outsideRoot":
        return _fail("tools.zip.outsideRoot")
    if err or archive is None or archive == root or not archive.is_file():
        return _fail("tools.zip.notFound")
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        return _fail("tools.zip.invalid")
    with zf:
        entries, entry_error = _entries(zf)
        if entry_error:
            return _fail(entry_error)
        if action == "list":
            shown = entries[:MAX_ENTRIES]
            return ExecuteResult(
                ok=True,
                result={"entries": shown, "count": len(entries), "truncated": len(entries) > len(shown)},
            )
        return _extract(root, archive, zf, entries, str(raw.get("destination") or ""))


def _root(cfg: dict[str, Any]) -> tuple[Path | None, str | None]:
    root_raw = str(cfg.get("rootPath") or cfg.get("root") or "").strip()
    if not root_raw:
        return None, "tools.zip.missingRoot"
    root_in = Path(root_raw).expanduser()
    if not root_in.is_absolute():
        return None, "tools.zip.rootNotDir"
    try:
        root = root_in.resolve()
    except OSError:
        return None, "tools.zip.rootNotDir"
    if not root.is_dir() or is_forbidden_root(root):
        return None, "tools.zip.rootNotDir"
    return root, None


def _entries(zf: zipfile.ZipFile) -> tuple[list[dict[str, object]], str | None]:
    rows: list[dict[str, object]] = []
    total = 0
    for info in zf.infolist():
        name = _safe_name(info.filename)
        if name is None:
            return [], "tools.zip.unsafePath"
        if _is_symlink(info):
            return [], "tools.zip.unsafePath"
        size = int(info.file_size)
        if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
            return [], "tools.zip.tooLarge"
        total += size
        rows.append({"name": name, "size": size, "directory": info.is_dir()})
        if len(rows) > MAX_ENTRIES * 4:
            return [], "tools.zip.tooLarge"
    return rows, None


def _extract(
    root: Path,
    archive: Path,
    zf: zipfile.ZipFile,
    entries: list[dict[str, object]],
    destination: str,
) -> ExecuteResult:
    files = [item for item in entries if not item["directory"]]
    if len(files) > MAX_ENTRIES:
        return _fail("tools.zip.tooLarge")
    target_raw = destination.strip() or archive.stem
    target, err = _resolve(root, target_raw)
    if err == "tools.fileAccess.outsideRoot":
        return _fail("tools.zip.outsideRoot")
    if err or target is None:
        return _fail("tools.zip.invalidPath")
    if target.is_file():
        return _fail("tools.zip.notDir")
    written: list[str] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = _safe_name(info.filename)
        if name is None:
            return _fail("tools.zip.unsafePath")
        dest = target / name
        try:
            resolved = dest.resolve()
        except OSError:
            return _fail("tools.zip.invalidPath")
        if not resolved.is_relative_to(target.resolve()):
            return _fail("tools.zip.unsafePath")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, resolved.open("wb") as out:
            copied = 0
            while True:
                chunk = src.read(64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > MAX_FILE_BYTES:
                    return _fail("tools.zip.tooLarge")
                out.write(chunk)
        written.append(resolved.relative_to(root).as_posix())
    return ExecuteResult(ok=True, result={"destination": target.relative_to(root).as_posix() if target != root else ".", "files": written})


def _safe_name(name: str) -> str | None:
    text = name.replace("\\", "/").strip()
    if not text or text.startswith("/") or text.startswith("//"):
        return None
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or ":" in part or part in {".", ".."}:
            return None
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _fail(key: str, result: object | None = None) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key, result=result)
