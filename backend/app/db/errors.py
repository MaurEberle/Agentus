"""Persistence errors. HTTP maps ``message_key``; never put secrets here."""

from __future__ import annotations


class PersistError(Exception):
    def __init__(self, message_key: str, *, store_id: str | None = None) -> None:
        self.message_key = message_key
        self.store_id = store_id
        super().__init__(message_key)


class StoreUnavailable(PersistError):
    """Store file missing or sqlite unusable."""


class VaultError(PersistError):
    """OS credential store failed. Message must not include the secret."""


class ConfigError(PersistError):
    """Invalid or read-only data directory / bootstrap."""


class NotFound(PersistError):
    """Row does not exist."""
