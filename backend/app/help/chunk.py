from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
WINDOW = 800
OVERLAP = 80


@dataclass
class TextChunk:
    title: str
    section: str | None
    text: str
    file_hash: str


def _windows(text: str) -> list[str]:
    body = text.strip()
    if not body:
        return []
    if len(body) <= WINDOW:
        return [body]
    out: list[str] = []
    start = 0
    while start < len(body):
        out.append(body[start : start + WINDOW])
        if start + WINDOW >= len(body):
            break
        start += WINDOW - OVERLAP
    return out


def chunk_markdown(text: str, title: str, file_hash: str) -> list[TextChunk]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return [
            TextChunk(title=title, section=None, text=part, file_hash=file_hash)
            for part in _windows(text)
        ]
    sections: list[tuple[str | None, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = match.group(2).strip()
        body = text[match.end() : end].strip()
        block = f"{match.group(0).strip()}\n{body}".strip()
        sections.append((heading, block))
    chunks: list[TextChunk] = []
    for section, body in sections:
        for part in _windows(body):
            chunks.append(
                TextChunk(title=title, section=section, text=part, file_hash=file_hash)
            )
    return chunks


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
