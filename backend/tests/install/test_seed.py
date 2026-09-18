from __future__ import annotations

from pathlib import Path

from app.db import init
from app.db.paths import RAG_DIR_NAME
from app.install_seed import SEED_MARKER, bundled_help_docs, seed_help_documents
from app.settings.defaults import default_settings


def _mini_corpus(root: Path) -> Path:
    bundled = root / "bundled"
    (bundled / "de").mkdir(parents=True)
    (bundled / "en").mkdir(parents=True)
    (bundled / "de" / "00-user-guide.md").write_text("# Guide\nHallo", encoding="utf-8")
    (bundled / "en" / "00-user-guide.md").write_text("# Guide\nHello", encoding="utf-8")
    return bundled


def test_seed_empty_target_then_noop(tmp_path: Path) -> None:
    bundled = _mini_corpus(tmp_path)
    data_dir = tmp_path / "data"
    seed_help_documents(data_dir, bundled=bundled)
    target = data_dir / RAG_DIR_NAME
    guide = target / "de" / "00-user-guide.md"
    assert guide.is_file()
    assert (target / SEED_MARKER).is_file()
    guide.write_text("# Guide\nedited", encoding="utf-8")
    seed_help_documents(data_dir, bundled=bundled)
    assert guide.read_text(encoding="utf-8") == "# Guide\nedited"


def test_seed_existing_user_file_not_overwritten(tmp_path: Path) -> None:
    bundled = _mini_corpus(tmp_path)
    data_dir = tmp_path / "data"
    target = data_dir / RAG_DIR_NAME
    target.mkdir(parents=True)
    user = target / "user.md"
    user.write_text("mine", encoding="utf-8")
    seed_help_documents(data_dir, bundled=bundled)
    assert user.read_text(encoding="utf-8") == "mine"
    assert not (target / "de" / "00-user-guide.md").exists()
    assert not (target / SEED_MARKER).exists()


def test_seed_bundled_missing_is_noop(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    seed_help_documents(data_dir, bundled=tmp_path / "missing-corpus")
    target = data_dir / RAG_DIR_NAME
    assert target.is_dir()
    assert not (target / SEED_MARKER).exists()
    assert list(target.iterdir()) == []


def test_init_seeds_when_help_docs_env_set(tmp_path: Path, monkeypatch) -> None:
    bundled = _mini_corpus(tmp_path)
    monkeypatch.setenv("AGENTUS_NETWORK_HELP_DOCS", str(bundled))
    bootstrap = init()
    target = bootstrap.data_dir / RAG_DIR_NAME
    assert (target / "de" / "00-user-guide.md").is_file()
    assert (target / SEED_MARKER).is_file()


def test_bundled_help_docs_pytest_is_none() -> None:
    assert bundled_help_docs() is None


def test_default_help_chat_models() -> None:
    settings = default_settings()
    assert settings.help_chat.model == "llama3.2:1b"
    assert settings.help_chat.fallback_model == "llama3.2:1b"
    assert settings.help_chat.embedding_model == "nomic-embed-text"
    assert settings.help_chat.provider == "ollama"
    assert settings.history_retention_days == 90
