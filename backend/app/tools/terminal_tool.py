from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.tools.file_access_tool import is_forbidden_root
from app.tools.models import ExecuteResult

DEFAULT_PROGRAMS = ("git", "python", "py", "dotnet")
TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 32_000
MAX_COMMAND_CHARS = 4_000
_SHELL_BREAKS = set("|<>&;\n\r")


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    cfg = config or {}
    raw_args = args or {}
    root, root_error = _root(cfg)
    if root_error or root is None:
        return _fail(root_error or "tools.terminal.missingRoot")

    command = str(raw_args.get("command") or "")
    if not command.strip():
        return _fail("tools.terminal.missingCommand")
    if len(command) > MAX_COMMAND_CHARS:
        return _fail("tools.terminal.commandTooLong")

    unrestricted = str(cfg.get("terminalMode") or "restricted").strip().lower() == "unrestricted"
    if unrestricted:
        return _run_powershell(root, command)
    programs = _programs(cfg)
    if not programs:
        return _fail("tools.terminal.notGranted")
    return _run_program(root, command, programs)


def _root(cfg: dict[str, Any]) -> tuple[Path | None, str | None]:
    root_raw = str(cfg.get("rootPath") or cfg.get("root") or "").strip()
    if not root_raw:
        return None, "tools.terminal.missingRoot"
    root_in = Path(root_raw).expanduser()
    if not root_in.is_absolute():
        return None, "tools.terminal.rootNotDir"
    try:
        root = root_in.resolve()
    except OSError:
        return None, "tools.terminal.rootNotDir"
    if not root.is_dir() or is_forbidden_root(root):
        return None, "tools.terminal.rootNotDir"
    return root, None


def _programs(cfg: dict[str, Any]) -> set[str]:
    raw = cfg.get("terminalPrograms")
    if isinstance(raw, list):
        names = [_program_name(str(item)) for item in raw]
        return {name for name in names if name}
    return set(DEFAULT_PROGRAMS)


def _program_name(token: str) -> str:
    name = token.strip().strip('"').strip("'")
    base = Path(name).name
    if base.lower().endswith(".exe"):
        base = base[:-4]
    return base.casefold()


def _split_command(command: str) -> tuple[list[str] | None, str | None]:
    args: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for char in command:
        if quote:
            if char == quote:
                quote = None
            else:
                buf.append(char)
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char in _SHELL_BREAKS:
            return None, "tools.terminal.shellSyntax"
        if char.isspace():
            if buf:
                args.append("".join(buf))
                buf = []
            continue
        buf.append(char)
    if quote:
        return None, "tools.terminal.shellSyntax"
    if buf:
        args.append("".join(buf))
    if not args:
        return None, "tools.terminal.missingCommand"
    return args, None


def _run_program(root: Path, command: str, programs: set[str]) -> ExecuteResult:
    parsed, error = _split_command(command)
    if error or not parsed:
        return _fail(error or "tools.terminal.missingCommand")
    token = parsed[0]
    if any(sep in token for sep in ("/", "\\", ":")):
        return _fail("tools.terminal.notGranted")
    name = _program_name(token)
    if not name or name not in programs:
        return _fail("tools.terminal.notGranted", {"program": name or token})
    executable = shutil.which(name)
    if not executable:
        return _fail("tools.terminal.notFound", {"program": name})
    return _spawn(root, [executable, *parsed[1:]])


def _run_powershell(root: Path, command: str) -> ExecuteResult:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        return _fail("tools.terminal.notFound", {"program": "powershell"})
    return _spawn(
        root,
        [executable, "-NoProfile", "-NonInteractive", "-Command", command],
    )


def _spawn(root: Path, argv: list[str]) -> ExecuteResult:
    try:
        proc = subprocess.Popen(
            argv,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            **_popen_kwargs(),
        )
    except OSError:
        return _fail("tools.terminal.notFound", {"program": Path(argv[0]).name})
    timed_out = False
    try:
        stdout_b, stderr_b = proc.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        _kill_tree(proc)
        stdout_b = exc.stdout or b""
        stderr_b = exc.stderr or b""
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    code = proc.returncode
    stdout, stdout_cut = _clip(_decode(stdout_b))
    stderr, stderr_cut = _clip(_decode(stderr_b))
    payload = {
        "exitCode": code,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": stdout_cut or stderr_cut,
        "timedOut": timed_out,
    }
    if timed_out:
        return _fail("tools.terminal.timeout", payload)
    return ExecuteResult(ok=True, result=payload)


def _clip(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS], True


def _decode(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def _popen_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": 0x08000000}


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=0x08000000,
        )
        return
    proc.kill()


def _fail(key: str, result: object | None = None) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key, result=result)
