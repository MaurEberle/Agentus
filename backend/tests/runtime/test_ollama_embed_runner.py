from __future__ import annotations

from pathlib import Path

from app.runtime.ollama_embed_runner import (
    gguf_paths_from_modelfile,
    library_dirs_for_llama,
    preferred_gpu_dir,
    spawn_env,
)


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


def test_library_dirs_prefer_newer_cuda(tmp_path: Path) -> None:
    root = tmp_path / "ollama"
    v12 = root / "cuda_v12"
    v13 = root / "cuda_v13"
    v12.mkdir(parents=True)
    v13.mkdir()
    (v12 / "ggml-cuda.dll").write_bytes(b"12")
    (v13 / "ggml-cuda.dll").write_bytes(b"13")
    exe = root / "llama-server.exe"
    exe.write_bytes(b"exe")
    assert preferred_gpu_dir(root, vendor="cuda") == v13
    dirs = library_dirs_for_llama(exe, vendor="cuda")
    assert dirs[0] == v13
    assert root in dirs
    env = spawn_env(exe, base={"PATH": "C:\\Windows"}, vendor="cuda")
    assert str(v13) in env["OLLAMA_LIBRARY_PATH"]
    assert env["PATH"].startswith(str(v13))


def test_library_dirs_hip_on_amd(tmp_path: Path) -> None:
    root = tmp_path / "ollama"
    cuda = root / "cuda_v13"
    hip = root / "rocm_v7_1"
    cuda.mkdir(parents=True)
    hip.mkdir()
    (cuda / "ggml-cuda.dll").write_bytes(b"cuda")
    (hip / "ggml-hip.dll").write_bytes(b"hip")
    exe = root / "llama-server.exe"
    exe.write_bytes(b"exe")
    assert preferred_gpu_dir(root, vendor="hip") == hip
    assert library_dirs_for_llama(exe, vendor="hip")[0] == hip


def test_library_dirs_vulkan_without_cuda(tmp_path: Path) -> None:
    root = tmp_path / "ollama"
    vulkan = root / "vulkan"
    vulkan.mkdir(parents=True)
    (vulkan / "ggml-vulkan.dll").write_bytes(b"vk")
    exe = root / "llama-server.exe"
    exe.write_bytes(b"exe")
    assert preferred_gpu_dir(root, vendor="vulkan") == vulkan


def test_spawn_passes_ngl_auto_and_gpu_env(tmp_path: Path, monkeypatch) -> None:
    import app.runtime.ollama_embed_runner as runner

    root = tmp_path / "ollama"
    cuda = root / "cuda_v13"
    cuda.mkdir(parents=True)
    (cuda / "ggml-cuda.dll").write_bytes(b"13")
    exe = root / "llama-server.exe"
    exe.write_bytes(b"exe")
    captured: dict = {}

    class _Proc:
        def poll(self) -> None:
            return None

    def _popen(**kwargs):
        captured.update(kwargs)
        return _Proc()

    monkeypatch.setattr(runner, "gpu_vendor", lambda: "cuda")
    monkeypatch.setattr(runner.subprocess, "Popen", lambda **kwargs: _popen(**kwargs))
    proc = runner._spawn(exe, [exe], 12345)
    assert proc is not None
    args = captured["args"]
    assert "-ngl" in args
    assert args[args.index("-ngl") + 1] == "auto"
    env = captured["env"]
    assert str(cuda) in env["OLLAMA_LIBRARY_PATH"]
    assert str(cuda) in env["PATH"]
    assert captured["cwd"] == str(cuda)
