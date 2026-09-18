"""OS credential store. Secrets never go to YAML, sqlite, or logs.

Windows: ``keyring`` → Credential Manager, service ``Agentus-Network``,
username ``credential/{id}`` (target ``Agentus-Network/credential/{id}``).
Tests: ``AGENTUS_NETWORK_VAULT=memory`` or ``use_memory()``.
"""

from __future__ import annotations

import os

from app.db.errors import VaultError

_SERVICE = "Agentus-Network"
_memory: dict[str, str] = {}
_force_memory = False


def use_memory() -> None:
    global _force_memory
    _force_memory = True


def reset_memory() -> None:
    _memory.clear()


def _is_memory() -> bool:
    if _force_memory:
        return True
    return os.environ.get("AGENTUS_NETWORK_VAULT", "").strip().lower() == "memory"


def _username(credential_id: str) -> str:
    return f"credential/{credential_id}"


def put(credential_id: str, secret: str) -> None:
    if _is_memory():
        _memory[credential_id] = secret
        return
    try:
        import keyring

        keyring.set_password(_SERVICE, _username(credential_id), secret)
    except Exception as exc:
        raise VaultError("vault.error") from exc


def get(credential_id: str) -> str | None:
    if _is_memory():
        return _memory.get(credential_id)
    try:
        import keyring

        return keyring.get_password(_SERVICE, _username(credential_id))
    except Exception as exc:
        raise VaultError("vault.error") from exc


def delete(credential_id: str) -> None:
    if _is_memory():
        _memory.pop(credential_id, None)
        return
    try:
        import keyring
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password(_SERVICE, _username(credential_id))
        except PasswordDeleteError:
            return
    except Exception as exc:
        raise VaultError("vault.error") from exc
