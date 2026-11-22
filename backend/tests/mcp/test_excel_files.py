from __future__ import annotations

from pathlib import Path

from app.mcp.excel_files import (
    annotate_excel_tools,
    ensure_workbook,
    folder_tool_result,
    list_workbooks,
    prepare_excel_write,
    workbook_hint,
)
from openpyxl import load_workbook
from app.mcp.models import McpToolInfo


def test_list_workbooks_skips_pdf_and_lock(tmp_path: Path) -> None:
    (tmp_path / "Watchlist_Aktien.xlsx").write_bytes(b"PK")
    (tmp_path / "note.pdf").write_bytes(b"%PDF")
    (tmp_path / "~$Watchlist_Aktien.xlsx").write_bytes(b"PK")
    names = [path.name for path in list_workbooks(tmp_path)]
    assert names == ["Watchlist_Aktien.xlsx"]


def test_folder_tool_result_for_directory(tmp_path: Path) -> None:
    book = tmp_path / "Watchlist_Aktien.xlsx"
    book.write_bytes(b"PK")
    text = folder_tool_result({"fileAbsolutePath": str(tmp_path)}, str(tmp_path))
    assert text is not None
    assert "Watchlist_Aktien.xlsx" in text
    assert "folder, not a workbook" in text
    assert folder_tool_result({"fileAbsolutePath": str(book)}, str(tmp_path)) is None


def test_ensure_workbook_replaces_empty_and_text_files(tmp_path: Path) -> None:
    missing = tmp_path / "neu" / "Watchlist_Aktien_bereinigt.xlsx"
    assert ensure_workbook(missing)
    assert missing.read_bytes()[:2] == b"PK"
    load_workbook(missing).close()

    empty = tmp_path / "leer.xlsx"
    empty.write_bytes(b"")
    assert ensure_workbook(empty)
    assert empty.read_bytes()[:2] == b"PK"

    text = tmp_path / "text.xlsx"
    text.write_text("Ticker,Name\n", encoding="utf-8")
    assert ensure_workbook(text)
    assert text.read_bytes()[:2] == b"PK"

    real = tmp_path / "Watchlist_Aktien.xlsx"
    real.write_bytes(b"PK\x03\x04kept")
    assert not ensure_workbook(real)
    assert real.read_bytes() == b"PK\x03\x04kept"
    assert not prepare_excel_write("excel_read_sheet", {"fileAbsolutePath": str(missing)})
    created = tmp_path / "via-write.xlsx"
    assert prepare_excel_write("excel_write_to_sheet", {"fileAbsolutePath": str(created)})
    assert created.read_bytes()[:2] == b"PK"


def test_annotate_excel_tools_names_files(tmp_path: Path) -> None:
    (tmp_path / "Watchlist_Aktien.xlsx").write_bytes(b"PK")
    tools = annotate_excel_tools(
        [
            McpToolInfo(
                name="excel_describe_sheets",
                description="List sheets",
                input_schema={
                    "type": "object",
                    "properties": {"fileAbsolutePath": {"type": "string"}},
                    "required": ["fileAbsolutePath"],
                },
            )
        ],
        str(tmp_path),
    )
    assert "Watchlist_Aktien.xlsx" in (tools[0].description or "")
    desc = tools[0].input_schema["properties"]["fileAbsolutePath"]["description"]
    assert "Watchlist_Aktien.xlsx" in desc
    assert "not a folder" in workbook_hint(tmp_path)
