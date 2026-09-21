from __future__ import annotations

from pathlib import Path

from app.runtime.ollama_embed_runner import gguf_paths_from_modelfile


def test_gguf_paths_keep_existing_files_only(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    proj = tmp_path / "mmproj.gguf"
    model.write_bytes(b"gguf")
    proj.write_bytes(b"proj")
    text = "\n".join(
        [
            "FROM hf.co/example/model",
            f"FROM {model}",
            f'FROM "{proj}"',
            "PARAMETER stop <|im_end|>",
        ]
    )
    assert gguf_paths_from_modelfile(text) == [model, proj]
