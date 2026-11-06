from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult
from app.tools.sandbox import configured_root, tool_fail

# Interpreters are never implied: a missing list grants git only. Users opt in explicitly.
DEFAULT_PROGRAMS = ("git",)
TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 32_000
MAX_COMMAND_CHARS = 4_000
_SHELL_BREAKS = set("|<>&;\n\r")


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    cfg = config or {}
    raw_args = args or {}
    root, root_error = configured_root(cfg, error_prefix="tools.terminal")
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
    if _inline_code(name, parsed[1:]):
        return _fail("tools.terminal.inlineCode", {"program": name})
    executable = shutil.which(name)
    if not executable:
        return _fail("tools.terminal.notFound", {"program": name})
    return _spawn(root, [executable, *parsed[1:]])


# Options that turn a granted program into a one-line code runner (python -c, git -c alias.x=!cmd).
_INLINE_SHORT = {"python": "c", "py": "c", "node": "ep"}
_INLINE_LONG = {
    "node": ("--eval", "--print"),
    "git": ("-c", "--config-env", "--exec-path"),
}
# Global options that consume the next argument; scanning continues after the value.
_VALUE_OPTS = {
    "git": ("-C", "--namespace", "--git-dir", "--work-tree", "--super-prefix"),
    "python": ("-X", "-W"),
    "py": ("-X", "-W"),
    "node": ("-r", "--require", "--import", "--loader", "--conditions", "-C"),
}


def _inline_code(name: str, args: list[str]) -> bool:
    """True when an option before the script/subcommand would run code from the command line."""
    shorts = _INLINE_SHORT.get(name, "")
    longs = _INLINE_LONG.get(name, ())
    takes_value = _VALUE_OPTS.get(name, ())
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if not arg.startswith("-"):
            return False
        flag = arg.split("=", 1)[0]
        if flag in longs or flag.lower() in longs:
            return True
        if flag in takes_value and "=" not in arg:
            skip = True
            continue
        if shorts and not arg.startswith("--") and any(ch in shorts for ch in arg[1:].lower()):
            return True
    return False


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


_fail = tool_fail
