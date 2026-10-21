import zipfile
from pathlib import Path

from app.tools.execute import execute_first_party


def _zip(path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in entries.items():
            zf.writestr(name, text)


def test_list_and_extract(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    _zip(archive, {"a.txt": "alpha", "dir/b.txt": "beta"})
    config = {"rootPath": str(tmp_path)}
    listed = execute_first_party("zip", config=config, args={"action": "list", "path": "pack.zip"})
    assert listed.ok is True
    names = [item["name"] for item in listed.result["entries"] if not item["directory"]]
    assert names == ["a.txt", "dir/b.txt"]
    extracted = execute_first_party("zip", config=config, args={"action": "extract", "path": "pack.zip"})
    assert extracted.ok is True
    assert (tmp_path / "pack" / "a.txt").read_text(encoding="utf-8") == "alpha"
    assert (tmp_path / "pack" / "dir" / "b.txt").read_text(encoding="utf-8") == "beta"


def test_extracts_into_destination(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    _zip(archive, {"a.txt": "alpha"})
    result = execute_first_party(
        "zip",
        config={"rootPath": str(tmp_path)},
        args={"action": "extract", "path": "pack.zip", "destination": "out"},
    )
    assert result.ok is True
    assert (tmp_path / "out" / "a.txt").read_text(encoding="utf-8") == "alpha"


def test_rejects_parent_path(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    _zip(archive, {"../escape.txt": "no"})
    result = execute_first_party(
        "zip",
        config={"rootPath": str(tmp_path)},
        args={"action": "extract", "path": "pack.zip"},
    )
    assert result.error_key == "tools.zip.unsafePath"
    assert not (tmp_path.parent / "escape.txt").exists()


def test_missing_root(tmp_path: Path) -> None:
    archive = tmp_path / "pack.zip"
    _zip(archive, {"a.txt": "alpha"})
    result = execute_first_party("zip", args={"action": "list", "path": "pack.zip"})
    assert result.error_key == "tools.zip.missingRoot"
