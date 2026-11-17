"""The consent step of OAuth: what the web app's /connect/authorize page shows, and its decision.

A transaction (stored by ``OAuth.authorize``) is bound to the first browser that views it, by a
cookie, and can be claimed once. Approving creates a grant and a single-use code; both outcomes
redirect to the client with ``iss`` (RFC 9207).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.provider import AuthorizationParams, construct_redirect_uri
from mcp.shared.auth import OAuthClientInformationFull

from lectern.files import FileError
from lectern.store import Store
from lectern.users import User

SCOPE = "lectern"
CODE_SECONDS = 600


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Consent:
    """Mixed into ``OAuth``."""

    store: Store
    clock: Any
    issuer: str
    resource: str

    def _txn(self, txn: str) -> Any:
        with self.store.tx() as db:
            row = db.execute(
                "SELECT * FROM oauth_txns WHERE id_hash = ? AND expires_at > ?", (sha(txn), self.clock())
            ).fetchone()
        if row is None:
            raise FileError(404, "this sign-in request has expired; start again from your app")
        return row

    def txn_view(self, txn: str, binding: str | None) -> tuple[dict[str, Any], str | None]:
        """What the consent page shows. The first view binds the request to this browser."""
        row = self._txn(txn)
        new_binding = None
        if row["binding_hash"] is None:
            new_binding = secrets.token_urlsafe(24)
            with self.store.tx() as db:
                db.execute(
                    "UPDATE oauth_txns SET binding_hash = ? WHERE id_hash = ?",
                    (sha(new_binding), row["id_hash"]),
                )
        elif binding is None or sha(binding) != row["binding_hash"]:
            raise FileError(403, "this sign-in request was opened in another browser")
        info = OAuthClientInformationFull.model_validate_json(self._client_row(row["client_id"])["info"])
        redirect = AuthorizationParams.model_validate_json(row["params"]).redirect_uri
        view = {
            "client": info.client_name or "an MCP client",
            "redirect_host": urlparse(str(redirect)).hostname,
            "scopes": [SCOPE],
        }
        return view, new_binding

    def _client_row(self, client_id: str) -> Any:
        with self.store.tx() as db:
            return db.execute("SELECT * FROM oauth_clients WHERE id = ?", (client_id,)).fetchone()

    def complete(self, txn: str, binding: str | None, user: User, approve: bool) -> str:
        """Approve or deny; returns the client redirect (with ``code`` or ``error``, plus ``iss``)."""
        row = self._txn(txn)
        if binding is None or row["binding_hash"] is None or sha(binding) != row["binding_hash"]:
            raise FileError(403, "this sign-in request was opened in another browser")
        with self.store.tx() as db:
            claimed = db.execute(
                "UPDATE oauth_txns SET in_flight = 1 WHERE id_hash = ? AND in_flight = 0", (row["id_hash"],)
            ).rowcount
            if not claimed:
                raise FileError(409, "this sign-in request was already used")
            db.execute("DELETE FROM oauth_txns WHERE id_hash = ?", (row["id_hash"],))
        params = AuthorizationParams.model_validate_json(row["params"])
        redirect = str(params.redirect_uri)
        if not approve:
            return construct_redirect_uri(
                redirect, error="access_denied", state=params.state, iss=self.issuer
            )
        grant_id, code = uuid.uuid4().hex, secrets.token_urlsafe(43)
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO oauth_grants (id, user_id, client_id, scopes, resource, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (grant_id, user.id, row["client_id"], SCOPE, self.resource, self.clock()),
            )
            db.execute(
                "INSERT INTO oauth_codes VALUES (?, ?, ?, ?, ?)",
                (sha(code), grant_id, row["client_id"], row["params"], self.clock() + CODE_SECONDS),
            )
        return construct_redirect_uri(redirect, code=code, state=params.state, iss=self.issuer)
