"""Custom credential payload. One JSON object in the vault, never in sqlite."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_MAX_FIELDS = 8
_MAX_VALUE = 8_000
_HEADER = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_BLOCKED_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "upgrade",
        "te",
        "trailer",
    }
)
_BLOCKED_ENV = frozenset(
    {
        "PATH",
        "PATHEXT",
        "PYTHONPATH",
        "PYTHONHOME",
        "COMSPEC",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "PROMPT",
    }
)


@dataclass(frozen=True)
class CustomCredential:
    token: str
    headers: dict[str, str]
    env: dict[str, str]


def parse_custom_secret(raw: str) -> CustomCredential:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("json") from exc
    if not isinstance(data, dict) or set(data) - {"token", "headers", "env"}:
        raise ValueError("shape")
    token = _text(data.get("token", ""), "token")
    headers = _pairs(data.get("headers", {}), _HEADER, _BLOCKED_HEADERS, fold=True)
    env = _pairs(data.get("env", {}), _ENV, frozenset(), fold=False)
    for name in env:
        upper = name.upper()
        if upper in _BLOCKED_ENV or upper.startswith("AGENTUS_"):
            raise ValueError("env")
    if not token and not headers and not env:
        raise ValueError("empty")
    return CustomCredential(token=token, headers=headers, env=env)


def encode_custom_secret(cred: CustomCredential) -> str:
    body: dict[str, object] = {}
    if cred.token:
        body["token"] = cred.token
    if cred.headers:
        body["headers"] = cred.headers
    if cred.env:
        body["env"] = cred.env
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def mask_custom(cred: CustomCredential) -> str:
    value = cred.token or next(iter(cred.headers.values()), "") or next(iter(cred.env.values()), "")
    if len(value) < 4:
        return "***"
    return "…" + value[-4:]


def try_parse_custom_secret(raw: str | None) -> CustomCredential | None:
    if not raw:
        return None
    text = raw.strip()
    if not text.startswith("{"):
        return None
    try:
        return parse_custom_secret(text)
    except ValueError:
        return None


def apply_http_secret(secret: str | None, headers: dict[str, str]) -> dict[str, str]:
    merged = dict(headers)
    parsed = try_parse_custom_secret(secret)
    if parsed is None:
        if secret and not _has_auth(merged):
            merged["Authorization"] = f"Bearer {secret}"
        return merged
    for name, value in parsed.headers.items():
        if not any(key.lower() == name.lower() for key in merged):
            merged[name] = value
    if parsed.token and not _has_auth(merged):
        merged["Authorization"] = f"Bearer {parsed.token}"
    return merged


def apply_process_secret(secret: str | None, env: dict[str, str], headers: dict[str, str]) -> None:
    if not secret:
        return
    parsed = try_parse_custom_secret(secret)
    if parsed is None:
        if not _has_auth(headers):
            headers["Authorization"] = f"Bearer {secret}"
        return
    env.update(parsed.env)
    for name, value in parsed.headers.items():
        if not any(key.lower() == name.lower() for key in headers):
            headers[name] = value
    if parsed.token and not _has_auth(headers):
        headers["Authorization"] = f"Bearer {parsed.token}"


def _has_auth(headers: dict[str, str]) -> bool:
    return any(key.lower() == "authorization" for key in headers)


def _text(value: object, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or "\n" in value or "\r" in value or len(value) > _MAX_VALUE:
        raise ValueError(label)
    return value.strip()


def _pairs(
    value: object,
    pattern: re.Pattern[str],
    blocked: frozenset[str],
    *,
    fold: bool,
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > _MAX_FIELDS:
        raise ValueError("pairs")
    out: dict[str, str] = {}
    for key, item in value.items():
        name = str(key).strip()
        check = name.lower() if fold else name
        if not pattern.fullmatch(name) or check in blocked or (fold and name.lower() in blocked):
            raise ValueError("name")
        text = _text(item, "value")
        if not text:
            continue
        out[name] = text
    return out
