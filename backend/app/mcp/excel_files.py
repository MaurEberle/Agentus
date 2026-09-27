"""Excel MCP needs workbook files; the node root is a folder."""

from __future__ import annotations

from pathlib import Path

from app.mcp.models import McpToolInfo

_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}
_MAX_FILES = 40


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
