"""OAuth 2.1 for MCP connectors such as claude.ai (decision D13).

The MCP SDK's auth handlers (``mcp.server.auth``) speak the protocol: metadata, ``/authorize``,
``/token``, ``/register`` (dynamic client registration) and ``/revoke``. This module is the
provider behind them, stored in SQLite:

* **Clients** register themselves. Only public clients (PKCE S256, no secret) whose redirect URIs
  are loopback or an exact allowed callback (claude.ai's and claude.com's by default; more with
  ``LECTERN_OAUTH_REDIRECTS``) are accepted.
* **Consent:** ``/authorize`` stores a 10-minute transaction and sends the browser to the web app's
  ``/connect/authorize`` page. The signed-in user approves or denies; the transaction is bound to
  that browser by a cookie and can be claimed once.
* **Tokens:** single-use authorization codes (10 minutes); access tokens ``lectern_oa_…`` (1 hour);
  refresh tokens ``lectern_or_…`` (30 days) that rotate, and reusing one revokes its whole family.
  Only sha256 hashes are stored. Every check also requires the user to be active, the client
  enabled and the grant not revoked, so disabling any of them cuts access at once.
"""

from __future__ import annotations

import ipaddress
import os
import secrets
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from lectern.files import FileError
from lectern.oauth_admin import Connections
from lectern.oauth_consent import SCOPE, Consent, sha
from lectern.store import Store
from lectern.users import User, Users

ACCESS_PREFIX, REFRESH_PREFIX = "lectern_oa_", "lectern_or_"
ACCESS_SECONDS, REFRESH_DAYS, TXN_SECONDS = 3600, 30, 600
KNOWN_CALLBACKS = ("https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback")
SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (
  id TEXT PRIMARY KEY, info TEXT NOT NULL, created_at REAL NOT NULL, last_used_at REAL, disabled_at REAL);
CREATE TABLE IF NOT EXISTS oauth_txns (
  id_hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, params TEXT NOT NULL, binding_hash TEXT,
  in_flight INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_grants (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, client_id TEXT NOT NULL, scopes TEXT NOT NULL,
  resource TEXT, created_at REAL NOT NULL, last_used_at REAL, revoked_at REAL);
CREATE TABLE IF NOT EXISTS oauth_codes (
  code_hash TEXT PRIMARY KEY, grant_id TEXT NOT NULL, client_id TEXT NOT NULL, params TEXT NOT NULL,
  expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_tokens (
  token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL, family TEXT NOT NULL, grant_id TEXT NOT NULL,
  user_id INTEGER NOT NULL, client_id TEXT NOT NULL, scopes TEXT NOT NULL, resource TEXT,
  expires_at REAL NOT NULL, used_at REAL, revoked_at REAL);
"""


def is_loopback(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def allowed_callbacks() -> set[str]:
    extra = os.environ.get("LECTERN_OAUTH_REDIRECTS", "")
    return set(KNOWN_CALLBACKS) | {u.strip() for u in extra.split(",") if u.strip()}


class OAuth(Consent, Connections):
    """The provider the SDK's handlers call, plus the consent step and the admin views."""

    def __init__(
        self, store: Store, users: Users, issuer: str, resource: str, clock: Any = time.time
    ) -> None:
        self.store, self.users, self.clock = store, users, clock
        self.issuer, self.resource = issuer.rstrip("/"), resource.rstrip("/")
        with store.tx() as db:
            db.executescript(SCHEMA)

    # clients ------------------------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with self.store.tx() as db:
            row = db.execute(
                "SELECT info, disabled_at FROM oauth_clients WHERE id = ?", (client_id,)
            ).fetchone()
        if row is None or row["disabled_at"]:
            return None
        return OAuthClientInformationFull.model_validate_json(row["info"])

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        uris = [str(u) for u in client_info.redirect_uris or []]
        bad = [u for u in uris if not (is_loopback(u) or u in allowed_callbacks())]
        if not uris or bad:
            raise RegistrationError(
                "invalid_redirect_uri", f"redirect URI not allowed: {', '.join(bad) or 'none given'}"
            )
        info = client_info.model_copy(
            update={
                "token_endpoint_auth_method": "none",
                "client_secret": None,
                "client_secret_expires_at": None,
                "grant_types": ["authorization_code", "refresh_token"],
                "scope": SCOPE,
            }
        )
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO oauth_clients (id, info, created_at) VALUES (?, ?, ?)",
                (info.client_id, info.model_dump_json(), self.clock()),
            )

    # authorize and consent ----------------------------------------------------------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if params.resource and params.resource.rstrip("/") != self.resource:
            raise AuthorizeError("invalid_request", "unknown resource")
        if params.code_challenge is None:
            raise AuthorizeError("invalid_request", "PKCE (S256) is required")
        txn = secrets.token_urlsafe(32)
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO oauth_txns (id_hash, client_id, params, expires_at) VALUES (?, ?, ?, ?)",
                (sha(txn), client.client_id, params.model_dump_json(), self.clock() + TXN_SECONDS),
            )
        return f"{self.issuer}/connect/authorize?txn={txn}"

    # codes and tokens ---------------------------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        with self.store.tx() as db:
            row = db.execute(
                "SELECT * FROM oauth_codes WHERE code_hash = ? AND client_id = ? AND expires_at > ?",
                (sha(authorization_code), client.client_id, self.clock()),
            ).fetchone()
        if row is None:
            return None
        params = AuthorizationParams.model_validate_json(row["params"])
        return AuthorizationCode(
            code=authorization_code,
            scopes=[SCOPE],
            expires_at=row["expires_at"],
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=self.resource,
            subject=row["grant_id"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        with self.store.tx() as db:
            used = db.execute(
                "DELETE FROM oauth_codes WHERE code_hash = ?", (sha(authorization_code.code),)
            ).rowcount
        if not used:  # single use
            raise TokenError("invalid_grant", "authorization code already used")
        return self._mint(str(authorization_code.subject), uuid.uuid4().hex)

    def _grant(self, grant_id: str) -> Any:
        with self.store.tx() as db:
            return db.execute(
                "SELECT g.*, c.disabled_at AS client_disabled FROM oauth_grants g JOIN oauth_clients c"
                " ON c.id = g.client_id WHERE g.id = ?",
                (grant_id,),
            ).fetchone()

    def _mint(self, grant_id: str, family: str) -> OAuthToken:
        grant, now = self._grant(grant_id), self.clock()
        if grant is None or grant["revoked_at"] or grant["client_disabled"]:
            raise TokenError("invalid_grant", "this connection was revoked")
        access, refresh = (
            ACCESS_PREFIX + secrets.token_urlsafe(32),
            REFRESH_PREFIX + secrets.token_urlsafe(32),
        )
        rows = [
            (sha(access), "access", now + ACCESS_SECONDS),
            (sha(refresh), "refresh", now + REFRESH_DAYS * 86400),
        ]
        with self.store.tx() as db:
            db.executemany(
                "INSERT INTO oauth_tokens (token_hash, kind, family, grant_id, user_id, client_id, scopes,"
                " resource, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        h,
                        kind,
                        family,
                        grant_id,
                        grant["user_id"],
                        grant["client_id"],
                        SCOPE,
                        self.resource,
                        exp,
                    )
                    for h, kind, exp in rows
                ],
            )
            db.execute("UPDATE oauth_grants SET last_used_at = ? WHERE id = ?", (now, grant_id))
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_SECONDS,
            scope=SCOPE,
            refresh_token=refresh,
        )

    def _token(self, token: str, kind: str) -> Any:
        with self.store.tx() as db:
            return db.execute(
                "SELECT * FROM oauth_tokens WHERE token_hash = ? AND kind = ?", (sha(token), kind)
            ).fetchone()

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = self._token(refresh_token, "refresh")
        if (
            row is None
            or row["client_id"] != client.client_id
            or row["revoked_at"]
            or row["expires_at"] < self.clock()
        ):
            return None
        if row["used_at"]:  # a rotated token presented again: someone copied it, so end the family
            self._revoke_family(row["family"])
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=[SCOPE],
            expires_at=int(row["expires_at"]),
            resource=self.resource,
            subject=row["grant_id"],
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        row = self._token(refresh_token.token, "refresh")
        with self.store.tx() as db:
            claimed = db.execute(
                "UPDATE oauth_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                (self.clock(), sha(refresh_token.token)),
            ).rowcount
        if row is None or not claimed:
            raise TokenError("invalid_grant", "refresh token already used")
        return self._mint(row["grant_id"], row["family"])

    async def exchange_identity_assertion(
        self, client: OAuthClientInformationFull, params: Any
    ) -> OAuthToken:
        """Enterprise identity assertions (ID-JAG) are not supported."""
        raise TokenError("unsupported_grant_type", "identity assertions are not supported")

    async def load_access_token(self, token: str) -> AccessToken | None:
        user = self.user_for(token)
        if user is None:
            return None
        row = self._token(token, "access")
        return AccessToken(
            token=token,
            client_id=row["client_id"],
            scopes=[SCOPE],
            expires_at=int(row["expires_at"]),
            resource=self.resource,
            subject=str(user.id),
        )

    def user_for(self, token: str) -> User | None:
        """The active user behind a live access token, or None (revoked, expired, disabled anything)."""
        if not token.startswith(ACCESS_PREFIX) or len(token) > 200:
            return None
        row = self._token(token, "access")
        if row is None or row["revoked_at"] or row["expires_at"] < self.clock():
            return None
        grant = self._grant(row["grant_id"])
        if grant is None or grant["revoked_at"] or grant["client_disabled"]:
            return None
        with self.store.tx() as db:
            db.execute(
                "UPDATE oauth_clients SET last_used_at = ? WHERE id = ?", (self.clock(), row["client_id"])
            )
        try:
            user = self.users.get(row["user_id"])
        except FileError:
            return None
        return user if user.status == "active" else None

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        for kind in ("access", "refresh"):
            row = self._token(token.token, kind)
            if row is not None:
                self._revoke_family(row["family"])

    def _revoke_family(self, family: str) -> None:
        with self.store.tx() as db:
            db.execute(
                "UPDATE oauth_tokens SET revoked_at = ? WHERE family = ? AND revoked_at IS NULL",
                (self.clock(), family),
            )
