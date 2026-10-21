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
    (root / "a.txt").write_text("one\ntwo\nthree", encoding="utf-8")
    (root / "b.txt").write_text("bee", encoding="utf-8")
    head = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read", "path": "a.txt", "head": 2},
    )
    assert head.ok is True
    assert head.result["content"] == "one\ntwo"
    many = execute_first_party(
        "file_access",
        config={"rootPath": str(root)},
        args={"action": "read_many", "path": ".", "paths": ["a.txt", "b.txt"]},
    )
    assert many.ok is True
    assert [item["path"] for item in many.result["files"]] == ["a.txt", "b.txt"]
