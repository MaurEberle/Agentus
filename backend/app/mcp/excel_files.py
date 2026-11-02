"""Excel MCP needs workbook files; the node root is a folder."""

from __future__ import annotations

from pathlib import Path

from app.mcp.models import McpToolInfo

_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}
_MAX_FILES = 40
_ZIP_MAGIC = b"PK"
_WRITE_TOOL = "excel_write_to_sheet"


def list_workbooks(root: str | Path) -> list[Path]:
    try:
        base = Path(root).expanduser().resolve()
    except (OSError, RuntimeError):
        return []
    if not base.is_dir():
        return []
    out: list[Path] = []
    try:
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("~$"):
                continue
            if path.suffix.lower() not in _SUFFIXES:
                continue
            out.append(path)
            if len(out) >= _MAX_FILES:
                break
    except OSError:
        return out
    return out


def workbook_hint(root: str | Path) -> str:
    files = list_workbooks(root)
    if not files:
        return (
            "fileAbsolutePath must be an Excel workbook file (.xlsx/.xlsm), "
            "not a folder. No workbooks were found in the node folder."
        )
    names = ", ".join(path.name for path in files)
    return (
        "fileAbsolutePath must be an Excel workbook file (.xlsx/.xlsm), not a folder. "
        f"Workbooks in the node folder: {names}."
    )


def folder_listing_text(root: str | Path) -> str:
    files = list_workbooks(root)
    if not files:
        return (
            "That path is a folder, not a workbook. "
            "No .xlsx/.xlsm files were found in the node folder."
        )
    lines = "\n".join(str(path) for path in files)
    return (
        "That path is a folder, not a workbook. "
        "Call this tool again with fileAbsolutePath set to one of these files:\n"
        + lines
    )


def annotate_excel_tools(tools: list[McpToolInfo], root: str | None) -> list[McpToolInfo]:
    if not root:
        return tools
    hint = workbook_hint(root)
    out: list[McpToolInfo] = []
    for tool in tools:
        description = ((tool.description or "") + " " + hint).strip()
        schema = dict(tool.input_schema or {})
        props = dict(schema.get("properties") or {})
        field = props.get("fileAbsolutePath")
        if isinstance(field, dict):
            field = dict(field)
            extra = hint
            if extra not in str(field.get("description") or ""):
                field["description"] = ((field.get("description") or "Workbook path") + " " + extra).strip()
            props["fileAbsolutePath"] = field
            schema["properties"] = props
        out.append(
            McpToolInfo(name=tool.name, description=description, input_schema=schema)
        )
    return out


def _is_zip_workbook(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(2) == _ZIP_MAGIC
    except OSError:
        return False


def ensure_workbook(path: Path) -> bool:
    """Write a minimal workbook when the target is missing, empty, or not a zip.

    ``excel_write_to_sheet`` only adds a sheet inside an existing workbook.
    A zero-byte or text file named ``.xlsx`` makes that open fail with
    ``zip: not a valid zip file``.
    """
    if path.suffix.lower() not in _SUFFIXES or path.is_dir() or _is_zip_workbook(path):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    from openpyxl import Workbook

    book = Workbook()
    book.save(path)
    return True


def prepare_excel_write(tool_name: str, arguments: dict) -> bool:
    if tool_name != _WRITE_TOOL:
        return False
    raw = arguments.get("fileAbsolutePath") or arguments.get("filepath") or arguments.get("path") or ""
    text = str(raw).strip()
    if not text:
        return False
    path = Path(text)
    if path.is_dir():
        return False
    return ensure_workbook(path)


def folder_tool_result(arguments: dict, root: str | None) -> str | None:
    if not root:
        return None
    raw = (
        arguments.get("fileAbsolutePath")
        or arguments.get("filepath")
        or arguments.get("path")
        or ""
    )
    text = str(raw).strip()
    if not text:
        return folder_listing_text(root)
    try:
        path = Path(text).expanduser()
        if path.is_dir():
            return folder_listing_text(path)
    except OSError:
        return None
    return None
