"""App log file (B1): agentus.* to a rotating file, masked; open the folder via the API."""

from __future__ import annotations

import logging
import threading

from app import applog


def test_app_log_writes_masked_lines(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(applog.DISABLE_ENV, raising=False)
    target = tmp_path / "logs" / "agentus.log"
    hook = threading.excepthook
    try:
        assert applog.setup_app_log(target) == target
        # A second call keeps the one handler.
        assert applog.setup_app_log(target) == target
        logging.getLogger("agentus.run").warning("run memory not stored Authorization: Bearer abc123secret")
        logging.getLogger("agentus.run").debug("debug is not written")
    finally:
        applog.remove_app_log()
    text = target.read_text(encoding="utf-8")
    assert "app start" in text
    assert "run memory not stored" in text
    assert "abc123secret" not in text
    assert "debug is not written" not in text
    assert text.count("run memory not stored") == 1
    assert threading.excepthook is hook


def test_app_log_is_off_with_the_switch(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(applog.DISABLE_ENV, "1")
    assert applog.setup_app_log(tmp_path / "agentus.log") is None
    assert not (tmp_path / "agentus.log").exists()


def test_thread_errors_reach_the_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(applog.DISABLE_ENV, raising=False)
    target = tmp_path / "agentus.log"
    monkeypatch.setattr(threading, "excepthook", lambda args: None)
    try:
        applog.setup_app_log(target)

        def _boom() -> None:
            raise ValueError("worker broke")

        worker = threading.Thread(target=_boom, name="worker-1")
        worker.start()
        worker.join()
    finally:
        applog.remove_app_log()
    text = target.read_text(encoding="utf-8")
    assert "thread worker-1 ended with an error" in text
    assert "ValueError: worker broke" in text

