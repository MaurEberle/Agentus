"""Token progress llama-server prints while Ollama still holds a tool call.

Ollama's qwen parser does not forward a tool-call body until the call is
complete. ``/api/chat`` stays silent, so a read timeout looks like a stall
and the UI never sees the tokens. Ollama 0.40 starts llama-server at log
verbosity 4, which prints ``n_gen`` for those same tokens.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_GEN_LINE = re.compile(
    r"n_gen\s*=\s*(\d+).*?\btg\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*t/s"
)
_PENDING_MAX = 8192


def ollama_server_log() -> Path | None:
    """Active Ollama server log, if this machine has one."""
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Ollama" / "server.log")
    candidates.append(Path.home() / ".ollama" / "logs" / "server.log")
    for path in candidates:
        if path.is_file():
            return path
    return None


class RunnerGenTail:
    """``n_gen`` lines appended after this tail was created."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.offset = path.stat().st_size if path is not None and path.is_file() else 0
        self.pending = ""
        self.tokens = 0
        self.rate: float | None = None

    def poll(self) -> bool:
        """Read new lines. True when the generated-token count moved forward."""
        if self.path is None or not self.path.is_file():
            return False
        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0
            self.pending = ""
        if size == self.offset and not self.pending:
            return False
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            data = handle.read()
            self.offset = handle.tell()
        text = self.pending + data.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self.pending = lines.pop()
        if len(self.pending) > _PENDING_MAX:
            self.pending = self.pending[-_PENDING_MAX:]
        advanced = False
        for line in lines:
            match = _GEN_LINE.search(line)
            if match is None:
                continue
            tokens = int(match.group(1))
            if tokens <= self.tokens:
                continue
            self.tokens = tokens
            self.rate = float(match.group(2))
            advanced = True
        return advanced
