"""Model settings and API keys managed from the web app by admins (decision D12).

Settings (provider, model, base URL …) are plain rows. API keys are encrypted with Fernet under
``LECTERN_SECRET_KEY`` (generate one with
``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``);
without it, keys can only come from the environment and the key endpoints answer 503.

What an admin stores overrides the environment: ``apply()`` writes the effective values into
this process's environment at start and after every change, so the agents, triage, System1, the
web researcher and the CLI all read one place. Removing a stored value restores the original
environment value. The API never returns a key: only whether it is set, where it comes from, and
its last four characters.
"""

from __future__ import annotations

import os
import time
from collections.abc import MutableMapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from lectern.files import FileError
from lectern.store import Store

SETTINGS = (
    "LECTERN_PROVIDER",
    "LECTERN_MODEL",
    "LECTERN_BASE_URL",
    "LECTERN_MODEL_ALLOWLIST",
    "SYSTEM1_MODEL_PROVIDER",
    "SYSTEM1_MODEL_NAME",
    "SYSTEM1_BASE_URL",
    "LECTERN_JEV_MODEL",
)
SECRETS = ("LECTERN_API_KEY", "SYSTEM1_API_KEY", "OPENROUTER_API_KEY", "EXA_API_KEY")
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  name TEXT PRIMARY KEY, value TEXT NOT NULL, secret INTEGER NOT NULL, updated_at REAL NOT NULL,
  updated_by TEXT);
"""


class Settings:
    def __init__(self, store: Store, env: MutableMapping[str, str] | None = None) -> None:
        self.store = store
        self.env = os.environ if env is None else env
        self.original = {k: self.env.get(k) for k in SETTINGS + SECRETS}  # what the deployment set
        key = self.env.get("LECTERN_SECRET_KEY", "")
        self.box = Fernet(key.encode()) if key else None
        with store.tx() as db:
            db.executescript(SCHEMA)
        self.apply()

    def _rows(self) -> dict[str, tuple[str, bool]]:
        with self.store.tx() as db:
            return {r["name"]: (r["value"], bool(r["secret"])) for r in db.execute("SELECT * FROM settings")}

    def stored(self) -> dict[str, str]:
        """Every stored value, decrypted (secrets that no longer decrypt are skipped)."""
        out = {}
        for name, (value, secret) in self._rows().items():
            if not secret:
                out[name] = value
            elif self.box is not None:
                try:
                    out[name] = self.box.decrypt(value.encode()).decode()
                except InvalidToken:  # LECTERN_SECRET_KEY changed: the old keys cannot be read
                    continue
        return out

    def apply(self) -> None:
        stored = self.stored()
        for name in SETTINGS + SECRETS:
            value = stored.get(name, self.original.get(name))
            if value:
                self.env[name] = value
            else:
                self.env.pop(name, None)

    def set(self, name: str, value: str | None, by: str | None = None) -> None:
        """Store (or with ``None``/"" remove) one setting or key, then apply."""
        secret = name in SECRETS
        if not secret and name not in SETTINGS:
            raise FileError(404, f"{name} is not a setting lectern manages")
        if value and secret and self.box is None:
            raise FileError(503, "set LECTERN_SECRET_KEY to store API keys in lectern")
        with self.store.tx() as db:
            if not value:
                db.execute("DELETE FROM settings WHERE name = ?", (name,))
            else:
                stored = self.box.encrypt(value.encode()).decode() if secret and self.box else value.strip()
                db.execute(
                    "INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?, ?)",
                    (name, stored, int(secret), time.time(), by),
                )
        self.apply()

    def public(self) -> dict[str, Any]:
        """For the admin page: values of settings, and only set/unset, source and last 4 of keys."""
        rows = self._rows()

        def source(name: str) -> str:
            return "lectern" if name in rows else ("environment" if self.original.get(name) else "unset")

        keys = [
            {
                "name": n,
                "set": bool(self.env.get(n)),
                "source": source(n),
                "last4": self.env[n][-4:] if len(self.env.get(n, "")) >= 12 else None,
            }
            for n in SECRETS
        ]
        values = [{"name": n, "value": self.env.get(n, ""), "source": source(n)} for n in SETTINGS]
        return {"settings": values, "keys": keys, "store_configured": self.box is not None}
