from __future__ import annotations

from app.tools.execute import execute_first_party
from app.tools.file_access_tool import MAX_WRITE_BYTES


def test_write_read_list_delete(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    config = {"rootPath": str(root)}
    written = execute_first_party(
        "file_access",
        config=config,
        args={"action": "write", "path": "note.txt", "content": "hello"},
    )
    assert written.ok is True
    assert written.result["path"] == "note.txt"
    listed = execute_first_party("file_access", config=config, args={"action": "list", "path": "."})
    assert listed.ok is True
    names = [item["name"] for item in listed.result["entries"]]
    assert "note.txt" in names
    read = execute_first_party("file_access", config=config, args={"action": "read", "path": "note.txt"})
    assert read.ok is True
    assert read.result["content"] == "hello"
    deleted = execute_first_party(
        "file_access", config=config, args={"action": "delete", "path": "note.txt"}
    )
    assert deleted.ok is True
    missing = execute_first_party(
        "file_access", config=config, args={"action": "read", "path": "note.txt"}
    )
    assert missing.ok is False
    assert missing.error_key == "tools.fileAccess.notFound"


def test_mkdir_and_nested_write(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    config = {"rootPath": str(root)}
    made = execute_first_party(
        "file_access",
        config=config,
        args={"action": "mkdir", "path": "a/b", "recursive": True},
    )
    assert made.ok is True
    written = execute_first_party(
        "file_access",
        config=config,
        args={"action": "write", "path": "a/b/c.txt", "content": "nested"},
    )
    assert written.ok is True
    stat = execute_first_party(
        "file_access", config=config, args={"action": "stat", "path": "a/b/c.txt"}
    )
    assert stat.ok is True
    assert stat.result["type"] == "file"


def test_escape_parent(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "../secret.txt"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.outsideRoot"


def test_unchecked_action_is_rejected(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root), "fileActions": ["read", "list"]},
        args={"action": "write", "path": "x.txt", "content": "x"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.disabled"
    assert not (root / "x.txt").exists()


def test_read_only(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root), "allowWrite": False},
        args={"action": "write", "path": "x.txt", "content": "x"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.readOnly"


def test_delete_denied(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.txt").write_text("x", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root), "allowDelete": False},
        args={"action": "delete", "path": "keep.txt"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.deleteDenied"
    assert (root / "keep.txt").exists()


def test_write_off_delete_on(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "gone.txt").write_text("x", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root), "allowWrite": False, "allowDelete": True},
        args={"action": "delete", "path": "gone.txt"},
    )
    assert result.ok is True
    assert not (root / "gone.txt").exists()


def test_missing_root() -> None:
    result = execute_first_party("file_access", args={"action": "list", "path": "."})
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.missingRoot"


def test_relative_root_rejected(tmp_path) -> None:
    (tmp_path / "root").mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": "root"},
        args={"action": "list", "path": "."},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.rootNotDir"


def test_delete_nonempty_dir(tmp_path) -> None:
    root = tmp_path / "root"
    nested = root / "keep"
    nested.mkdir(parents=True)
    (nested / "f.txt").write_text("x", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "delete", "path": "keep"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.notEmpty"


def test_delete_root_rejected(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "delete", "path": "."},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.outsideRoot"


def test_too_large(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "write", "path": "big.txt", "content": "x" * (MAX_WRITE_BYTES + 1)},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.tooLarge"


def test_absolute_inside_root(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "abs.txt"
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "write", "path": str(target), "content": "abs"},
    )
    assert result.ok is True
    read = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": str(target)},
    )
    assert read.ok is True
    assert read.result["content"] == "abs"


def test_write_creates_missing_parents(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "write", "path": "src/types/weather.ts", "content": "export {}"},
    )
    assert result.ok is True
    assert (root / "src" / "types" / "weather.ts").read_text(encoding="utf-8") == "export {}"


def test_edit_replaces_one_occurrence(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("alpha beta", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "edit", "path": "a.txt", "oldText": "beta", "newText": "gamma"},
    )
    assert result.ok is True
    assert (root / "a.txt").read_text(encoding="utf-8") == "alpha gamma"


def test_edit_rejects_ambiguous_text(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("x x", encoding="utf-8")
    result = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "edit", "path": "a.txt", "oldText": "x", "newText": "y"},
    )
    assert result.ok is False
    assert result.error_key == "tools.fileAccess.editAmbiguous"
    assert (root / "a.txt").read_text(encoding="utf-8") == "x x"


def test_move_search_and_tree(tmp_path) -> None:
    root = tmp_path / "root"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.ts").write_text("hi", encoding="utf-8")
    moved = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "move", "path": "src/app.ts", "destination": "src/main.ts"},
    )
    assert moved.ok is True
    assert (root / "src" / "main.ts").is_file()
    found = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "search", "path": ".", "pattern": "*.ts"},
    )
    assert found.ok is True
    assert found.result["matches"] == ["src/main.ts"]
    tree = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "tree", "path": "."},
    )
    assert tree.ok is True
    names = [item["name"] for item in tree.result["children"]]
    assert names == ["src"]


def test_read_head_and_many(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    # Bytes, not write_text: on Windows that would store CRLF and the page shows it.
    (root / "a.txt").write_bytes(b"one\ntwo\nthree")
    (root / "b.txt").write_bytes(b"bee")
    head = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "a.txt", "head": 2},
    )
    assert head.ok is True
    # A page is the exact text of its lines, line endings included.
    assert head.result["content"] == "one\ntwo\n"
    assert head.result["lines"] == 3
    assert (head.result["startLine"], head.result["endLine"]) == (1, 2)
    assert head.result["nextOffset"] == 3
    many = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read_many", "path": ".", "paths": ["a.txt", "b.txt"]},
    )
    assert many.ok is True
    assert [item["path"] for item in many.result["files"]] == ["a.txt", "b.txt"]


def test_read_pages_through_a_large_file(tmp_path) -> None:
    import json

    from app.mcp.payload import TOOL_RESULT_CHARS, format_tool_result

    root = tmp_path / "root"
    root.mkdir()
    lines = [f"line {index:04d} " + "x" * 40 for index in range(1, 401)]
    (root / "big.txt").write_bytes("\n".join(lines).encode("utf-8"))
    seen: list[str] = []
    offset: int | None = None
    for _ in range(40):
        args: dict[str, object] = {"action": "read", "path": "big.txt"}
        if offset is not None:
            args["offset"] = offset
        page = execute_first_party("file_access", config={"rootPath": str(root)}, args=args)
        assert page.ok is True
        # The whole result fits the tool budget and stays valid JSON.
        text = format_tool_result(page.model_dump(by_alias=True))
        assert len(text) <= TOOL_RESULT_CHARS
        assert json.loads(text)["result"]["lines"] == 400
        seen.append(page.result["content"])
        offset = page.result.get("nextOffset")
        if offset is None:
            assert "truncated" not in page.result
            break
        assert page.result["truncated"] is True
    assert "".join(seen) == "\n".join(lines)
    assert len(seen) > 1


def test_read_offset_and_limit_pick_a_line_range(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_bytes(b"one\ntwo\nthree\nfour\n")
    page = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "a.txt", "offset": 2, "limit": 2},
    )
    assert page.result["content"] == "two\nthree\n"
    assert (page.result["startLine"], page.result["endLine"]) == (2, 3)
    assert page.result["nextOffset"] == 4
    assert "truncated" not in page.result
    tail = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "a.txt", "tail": 1},
    )
    assert tail.result["content"] == "four\n"
    assert "nextOffset" not in tail.result


def test_read_keeps_code_that_only_looks_like_a_secret(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = 'headers = {"Authorization": f"Bearer {token}"}\nKEY = "sk-abcdefghijklmnop"\n'
    (root / "client.py").write_bytes(source.encode("utf-8"))
    read = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "client.py"},
    )
    content = read.result["content"]
    # H5: the template survives; a real-looking key is still masked.
    assert 'f"Bearer {token}"}' in content
    assert "sk-abcdefghijklmnop" not in content
    assert "sk-***" in content


def test_edit_reads_the_whole_file_not_one_page(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    lines = [f"line {index:04d} " + "x" * 40 for index in range(1, 401)]
    (root / "big.txt").write_bytes("\n".join(lines).encode("utf-8"))
    edited = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "edit", "path": "big.txt", "oldText": "line 0390 ", "newText": "LINE 390 "},
    )
    assert edited.ok is True
    assert "LINE 390 " in (root / "big.txt").read_text(encoding="utf-8")
