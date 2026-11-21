from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult
from app.tools.sandbox import configured_root, tool_fail

# Interpreters are never implied: a missing list grants git only. Users opt in explicitly.
DEFAULT_PROGRAMS = ("git",)
TIMEOUT_SECONDS = 30
TIMEOUT_MIN = 5
TIMEOUT_MAX = 600
MAX_OUTPUT_CHARS = 32_000
MAX_COMMAND_CHARS = 4_000
_SHELL_BREAKS = set("|<>&;\n\r")
# M14: cmd.exe parses the arguments of a .cmd/.bat shim (npm, npx, pnpm) again,
# quotes included. These characters would start a second command there.
_BATCH_SUFFIXES = (".cmd", ".bat")
_BATCH_METAS = set('&|<>^%!"()\n\r')
# PowerShell 5.1 writes to a pipe in the OEM code page; switch it to UTF-8 first.
_PS_UTF8 = (
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    "$OutputEncoding = [System.Text.Encoding]::UTF8; "
)


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

    timeout = _timeout(cfg)
    unrestricted = str(cfg.get("terminalMode") or "restricted").strip().lower() == "unrestricted"
    if unrestricted:
        return _run_powershell(root, command, timeout)
    programs = _programs(cfg)
    if not programs:
        return _fail("tools.terminal.notGranted")
    command, habits = strip_shell_habits(command, root)
    if not command:
        return _fail("tools.terminal.missingCommand")
    result = _run_program(root, command, programs, timeout)
    # Only a command that ran gets "ran" and the note. A rejected rest kept them and the
    # note recommended a command that is rejected again (Coder_Team run, 2026-11-20: 44 times).
    if habits.removed and (result.ok or result.error_key == "tools.terminal.timeout"):
        _apply_habits(result, habits, command)
    return result


# Shell parts models add out of habit that change nothing here (Dev Team run, 2026-11-17:
# 26 of 35 rejected commands). "cd <root> &&": the command runs there anyway. "2>&1":
# stderr comes back on its own. A trailing "| head -N" or "| tail -N" is done on the output.
_CD_PREFIX = re.compile(r"""^\s*cd\s+(?:/d\s+)?(?P<dir>"[^"]*"|'[^']*'|[^\s&|;"']+)\s*&&\s*""", re.IGNORECASE)
_PIPE_LINES = re.compile(
    r"\s*\|\s*(?P<kind>head|tail)(?:\s+-n)?(?:\s+-?(?P<count>\d+))?\s*$", re.IGNORECASE
)
_MERGE_STDERR = "2>&1"
_DEFAULT_LINES = 10


class ShellHabits:
    def __init__(self) -> None:
        self.removed: list[str] = []
        self.lines: tuple[str, int] | None = None


def strip_shell_habits(command: str, root: Path) -> tuple[str, ShellHabits]:
    """The command without cd to the root, 2>&1 and a trailing head/tail, and what was taken off."""
    habits = ShellHabits()
    text = command.strip()
    changed = True
    while changed:
        changed = False
        match = _CD_PREFIX.match(text)
        if match and _is_root(match.group("dir"), root):
            habits.removed.append(match.group(0).strip())
            text = text[match.end():].strip()
            changed = True
        pipe = _PIPE_LINES.search(text)
        if pipe and habits.lines is None and _outside_quotes(text, pipe.start()):
            count = int(pipe.group("count") or _DEFAULT_LINES)
            habits.lines = (pipe.group("kind").lower(), max(1, count))
            habits.removed.append(pipe.group(0).strip())
            text = text[: pipe.start()].rstrip()
            changed = True
    without = _drop_token(text, _MERGE_STDERR)
    if without != text:
        habits.removed.append(_MERGE_STDERR)
        text = without
    return text, habits


def _is_root(raw: str, root: Path) -> bool:
    from app.tools.file_access_tool import path_candidates

    value = raw.strip().strip('"').strip("'")
    if value in {".", "./", ".\\"}:
        return True
    try:
        target = root.resolve()
    except OSError:
        return False
    for option in path_candidates(value):
        path = Path(option)
        try:
            resolved = (path if path.is_absolute() else root / path).resolve()
        except OSError:
            continue
        if resolved == target:
            return True
    return False


def _outside_quotes(text: str, index: int) -> bool:
    quote: str | None = None
    for char in text[:index]:
        if quote:
            if char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
    return quote is None


def _drop_token(text: str, token: str) -> str:
    """``text`` without ``token`` where it stands alone outside quotes."""
    out: list[str] = []
    quote: str | None = None
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if quote:
            out.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            out.append(char)
            index += 1
            continue
        end = index + len(token)
        if (
            text.startswith(token, index)
            and (index == 0 or text[index - 1].isspace())
            and (end == size or text[end].isspace())
        ):
            index = end
            continue
        out.append(char)
        index += 1
    return "".join(out).strip()


def _keep_lines(text: object, kind: str, count: int) -> tuple[object, bool]:
    if not isinstance(text, str):
        return text, False
    lines = text.splitlines()
    if len(lines) <= count:
        return text, False
    kept = lines[:count] if kind == "head" else lines[-count:]
    return "\n".join(kept) + "\n", True


def _apply_habits(result: ExecuteResult, habits: ShellHabits, ran: str) -> None:
    """Do the head/tail on the output and tell the model what was not needed."""
    payload = result.result if isinstance(result.result, dict) else {}
    if habits.lines is not None:
        kind, count = habits.lines
        cut = False
        for key in ("stdout", "stderr"):
            if key in payload:
                payload[key], clipped = _keep_lines(payload[key], kind, count)
                cut = cut or clipped
        if cut:
            payload["truncated"] = True
    payload["ran"] = ran
    payload["note"] = (
        "Not needed here and taken off: " + ", ".join(habits.removed) + ". "
        f"Next time send only: {ran}"
    )
    result.result = payload


def _timeout(cfg: dict[str, Any]) -> float:
    """Per node ``timeoutSec`` (M14), clamped to 5..600 s. Unset: TIMEOUT_SECONDS."""
    raw = cfg.get("timeoutSec")
    if raw is None or isinstance(raw, bool) or not str(raw).strip():
        return float(TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(TIMEOUT_SECONDS)
    if value != value:  # NaN
        return float(TIMEOUT_SECONDS)
    return max(float(TIMEOUT_MIN), min(float(TIMEOUT_MAX), value))


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


def _run_program(root: Path, command: str, programs: set[str], timeout: float) -> ExecuteResult:
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
    if _dir_outside_root(name, parsed[1:], root):
        return _fail("tools.terminal.outsideRoot", {"program": name})
    executable = shutil.which(name)
    if not executable:
        return _fail("tools.terminal.notFound", {"program": name})
    if executable.lower().endswith(_BATCH_SUFFIXES) and any(
        char in _BATCH_METAS for arg in parsed[1:] for char in arg
    ):
        return _fail("tools.terminal.shellSyntax", {"program": name})
    return _spawn(root, [executable, *parsed[1:]], timeout)


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


# Options that point a program at another directory. They must stay inside the root.
_DIR_OPTS = {"git": ("-C", "--git-dir", "--work-tree")}


def _dir_outside_root(name: str, args: list[str], root: Path) -> bool:
    """True when a directory option (git -C <dir>) leaves the configured root."""
    options = _DIR_OPTS.get(name, ())
    if not options:
        return False
    from app.tools.file_access_tool import path_candidates

    index = 0
    while index < len(args):
        arg = args[index]
        if not arg.startswith("-"):
            return False
        value = None
        if arg in options:
            value = args[index + 1] if index + 1 < len(args) else ""
            index += 1
        else:
            for option in options:
                if option.startswith("--") and arg.startswith(option + "="):
                    value = arg.split("=", 1)[1]
        if value is not None and not _inside_root(value, root, path_candidates):
            return True
        index += 1
    return False


def _inside_root(value: str, root: Path, candidates) -> bool:
    for option in candidates(value.strip()):
        path = Path(option)
        try:
            resolved = (path if path.is_absolute() else root / path).resolve()
        except OSError:
            continue
        if resolved.is_relative_to(root.resolve()):
            return True
    return False


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
        # Exact for single-dash flags: git -C (directory) is not git -c (config).
        if flag in longs or (flag.startswith("--") and flag.lower() in longs):
            return True
        if flag in takes_value and "=" not in arg:
            skip = True
            continue
        if shorts and not arg.startswith("--") and any(ch in shorts for ch in arg[1:].lower()):
            return True
    return False


def _run_powershell(root: Path, command: str, timeout: float | None = None) -> ExecuteResult:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        return _fail("tools.terminal.notFound", {"program": "powershell"})
    return _spawn(
        root,
        [executable, "-NoProfile", "-NonInteractive", "-Command", _PS_UTF8 + command],
        timeout,
    )


def _spawn(root: Path, argv: list[str], timeout: float | None = None) -> ExecuteResult:
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
        stdout_b, stderr_b = proc.communicate(timeout=TIMEOUT_SECONDS if timeout is None else timeout)
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
    """UTF-8 first; Windows console programs that ignore it write the OEM code page."""
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if os.name == "nt":
        try:
            return data.decode("oem")
        except (LookupError, UnicodeDecodeError):
            pass
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
