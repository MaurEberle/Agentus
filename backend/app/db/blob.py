"""float32 little-endian blobs for RAG embeddings."""

from __future__ import annotations

import struct


def pack_f32(vec: list[float]) -> bytes:
    if not vec:
        return b""
    return struct.pack("<" + "f" * len(vec), *vec)


def unpack_f32(blob: bytes | None) -> list[float]:
    if not blob:
        return []
    n = len(blob) // 4
    if n == 0:
        return []
    return list(struct.unpack("<" + "f" * n, blob[: n * 4]))
