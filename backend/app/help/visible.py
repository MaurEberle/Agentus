"""Drop model reasoning tags from help-chat text before it is shown or stored."""

from __future__ import annotations

_OPEN = "<think>"
_CLOSE = "</think>"


def _tag_suffix(text: str, tag: str) -> int:
    """Length of the longest suffix of ``text`` that is a proper prefix of ``tag``."""
    folded = text.lower()
    limit = min(len(tag) - 1, len(text))
    for size in range(limit, 0, -1):
        if folded.endswith(tag[:size]):
            return size
    return 0


class ThinkStripper:
    """Hide ``<think>`` spans across streamed chunks. An unclosed span stays hidden."""

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False
        self._started = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buf += chunk
        return self._drain(final=False)

    def finish(self) -> str:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        parts: list[str] = []
        while self._buf:
            folded = self._buf.lower()
            if self._inside:
                close_at = folded.find(_CLOSE)
                if close_at < 0:
                    if final:
                        self._buf = ""
                    else:
                        hold = _tag_suffix(self._buf, _CLOSE)
                        self._buf = self._buf[-hold:] if hold else ""
                    break
                self._buf = self._buf[close_at + len(_CLOSE) :]
                self._inside = False
                continue
            open_at = folded.find(_OPEN)
            if open_at < 0:
                hold = _tag_suffix(self._buf, _OPEN)
                if hold:
                    visible = self._buf[:-hold]
                    self._buf = "" if final else self._buf[-hold:]
                    if visible:
                        parts.append(self._emit(visible))
                    if not final:
                        break
                    continue
                parts.append(self._emit(self._buf))
                self._buf = ""
                break
            if open_at:
                parts.append(self._emit(self._buf[:open_at]))
            self._buf = self._buf[open_at + len(_OPEN) :]
            self._inside = True
        return "".join(parts)

    def _emit(self, text: str) -> str:
        if not text:
            return ""
        if not self._started:
            text = text.lstrip()
            if not text:
                return ""
            self._started = True
        return text


def strip_think(text: str) -> str:
    tool = ThinkStripper()
    return tool.feed(text) + tool.finish()
