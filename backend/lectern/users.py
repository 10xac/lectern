"""Users, invites and sessions in SQLite (decision D11). Only admins add users.

* An admin invites a user by email and gets a **one-time link** (``/accept-invite#token=…``; the
  token sits in the URL fragment, so it never reaches a server log or a Referer header). The user
  opens it and chooses a password. Re-inviting issues a new link and voids the old one; it is also
  how an admin resets a forgotten password.
* The **first admin** is seeded from the command line: ``lectern users create-admin <email>``
  prints an invite link. It is safe to re-run while that admin is still invited.
* Passwords are hashed with scrypt (stdlib). Session and invite tokens are random; only their
  sha256 is stored, so a copied database row is not a credential.
* **Personal access tokens** for MCP: a user creates named tokens (up to 90 days) in the web app.
  A token is shown once and stored as its sha256; each use resolves its owner afresh, so disabling
  the user (or revoking the token) stops it at once. MCP calls are recorded as that user's.
* Five wrong passwords lock an account for 15 minutes. An unknown email and a wrong password take
  the same work and give the same answer.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any, Literal

from pydantic import BaseModel

from lectern.files import FileError
from lectern.store import Store

Role = Literal["admin", "member"]
Status = Literal["invited", "active", "disabled"]
MIN_PASSWORD, MAX_PASSWORD = 12, 1024
LOCK_AFTER, LOCK_SECONDS = 5, 15 * 60
SESSION_DAYS, INVITE_DAYS = 14, 7
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL, status TEXT NOT NULL,
  password_hash TEXT, failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0,
  created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS access_tokens (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  revoked_at REAL, last_used_at REAL);
"""
PAT_PREFIX, PAT_MAX_DAYS = "lectern_pat_", 90


class User(BaseModel):
    id: int
    email: str
    role: Role
    status: Status


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(stored: str | None, password: str) -> bool:
    """Constant work whether or not there is a stored hash (no account-existence oracle)."""
    salt_hex, want = stored.split("$")[1:] if stored else ("00" * 16, "")
    got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **SCRYPT).hex()
    return bool(stored) and hmac.compare_digest(got, want)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_for(session_token: str) -> str:
    """The CSRF token bound to a session, derived from the HttpOnly cookie a cross-site page cannot read."""
    return hashlib.sha256(b"lectern-csrf:" + session_token.encode()).hexdigest()


def check_password(password: str) -> None:
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise FileError(422, f"a password is {MIN_PASSWORD} to {MAX_PASSWORD} characters")


class Users:
    def __init__(self, store: Store, clock: Any = time.time) -> None:
        self.store, self.clock = store, clock
        with store.tx() as db:
            db.executescript(SCHEMA)

    def _user(self, where: str, arg: object) -> dict[str, Any] | None:
        with self.store.tx() as db:
            row = db.execute(f"SELECT * FROM users WHERE {where}", (arg,)).fetchone()
        return dict(row) if row else None

    def get(self, user_id: int) -> User:
        row = self._user("id = ?", user_id)
        if row is None:
            raise FileError(404, f"no user {user_id}")
        return User(**row)

    def all_users(self) -> list[User]:
        with self.store.tx() as db:
            return [User(**dict(r)) for r in db.execute("SELECT * FROM users ORDER BY id")]

    def count_admins(self) -> int:
        with self.store.tx() as db:
            row = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
            ).fetchone()
        return int(row[0])

    # invites --------------------------------------------------------------------------------------

    def invite(self, email: str, role: Role = "member") -> tuple[User, str]:
        """Create the user (or re-invite them) and return a fresh one-time invite token."""
        email = email.strip().lower()
        if "@" not in email or len(email) > 320:
            raise FileError(422, "an invite needs an email address")
        row = self._user("email = ?", email)
        with self.store.tx() as db:
            if row is None:
                cur = db.execute(
                    "INSERT INTO users (email, role, status, created_at) VALUES (?, ?, 'invited', ?)",
                    (email, role, self.clock()),
                )
                user_id = int(cur.lastrowid or 0)
            else:
                user_id = row["id"]
            db.execute("DELETE FROM invites WHERE user_id = ?", (user_id,))  # older links stop working
            token = secrets.token_urlsafe(32)
            expires = self.clock() + INVITE_DAYS * 86400
            db.execute("INSERT INTO invites VALUES (?, ?, ?)", (token_hash(token), user_id, expires))
        return self.get(user_id), token

    def accept(self, token: str, password: str) -> tuple[User, str]:
        """Set the password from an invite (or re-invite) and start a session."""
        check_password(password)
        with self.store.tx() as db:
            row = db.execute("SELECT * FROM invites WHERE token_hash = ?", (token_hash(token),)).fetchone()
            if row is None or row["expires_at"] < self.clock():
                raise FileError(400, "this invite link is invalid or has expired; ask an admin for a new one")
            user = db.execute("SELECT status FROM users WHERE id = ?", (row["user_id"],)).fetchone()
            if user["status"] == "disabled":
                raise FileError(403, "this account is disabled")
            db.execute("DELETE FROM invites WHERE user_id = ?", (row["user_id"],))
            db.execute(
                "UPDATE users SET password_hash = ?, status = 'active', failures = 0, locked_until = 0"
                " WHERE id = ?",
                (hash_password(password), row["user_id"]),
            )
        return self.get(row["user_id"]), self._session(row["user_id"])

    # sessions -------------------------------------------------------------------------------------

    def login(self, email: str, password: str) -> tuple[User, str]:
        row = self._user("email = ?", email.strip().lower())
        if row is not None and row["locked_until"] > self.clock():
            raise FileError(429, "too many failed attempts; try again later")
        usable = row["password_hash"] if row is not None and row["status"] == "active" else None
        if not verify_password(usable, password) or row is None:
            if row is not None:
                failures = row["failures"] + 1
                locked = self.clock() + LOCK_SECONDS if failures >= LOCK_AFTER else 0
                with self.store.tx() as db:
                    db.execute(
                        "UPDATE users SET failures = ?, locked_until = ? WHERE id = ?",
                        (0 if locked else failures, locked, row["id"]),
                    )
            raise FileError(401, "invalid email or password")
        with self.store.tx() as db:
            db.execute("UPDATE users SET failures = 0 WHERE id = ?", (row["id"],))
        return User(**row), self._session(row["id"])

    def _session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (token_hash(token), user_id, self.clock() + SESSION_DAYS * 86400),
            )
        return token

    def by_session(self, token: str) -> User | None:
        """The active user behind a session cookie, or None."""
        if not token:
            return None
        with self.store.tx() as db:
            row = db.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
                (token_hash(token), self.clock()),
            ).fetchone()
        return User(**dict(row)) if row else None

    def logout(self, token: str) -> None:
        with self.store.tx() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))

    def update(self, user_id: int, role: Role | None = None, status: Status | None = None) -> User:
        """Change a role or enable/disable a user. Disabling ends their sessions. The last admin stays."""
        user = self.get(user_id)
        losing_admin = (
            user.role == "admin" and user.status == "active" and (role == "member" or status == "disabled")
        )
        if losing_admin and self.count_admins() <= 1:
            raise FileError(409, "lectern needs at least one active admin")
        if status == "active" and user.status == "invited":
            raise FileError(409, "an invited user becomes active by accepting the invite")
        with self.store.tx() as db:
            db.execute(
                "UPDATE users SET role = COALESCE(?, role), status = COALESCE(?, status) WHERE id = ?",
                (role, status, user_id),
            )
            if status == "disabled":
                db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return self.get(user_id)

    # personal access tokens (MCP) -------------------------------------------------------------------

    def create_token(self, user_id: int, name: str, days: int) -> tuple[dict[str, Any], str]:
        """A new token for ``user_id``. The returned secret is shown once and never stored."""
        if not 1 <= days <= PAT_MAX_DAYS or not 1 <= len(name.strip()) <= 100:
            raise FileError(422, f"a token needs a name and a lifetime of 1 to {PAT_MAX_DAYS} days")
        secret, token_id, now = PAT_PREFIX + secrets.token_urlsafe(32), secrets.token_hex(6), self.clock()
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO access_tokens (id, user_id, name, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (token_id, user_id, name.strip(), token_hash(secret), now, now + days * 86400),
            )
        return next(t for t in self.tokens(user_id) if t["id"] == token_id), secret

    def tokens(self, user_id: int) -> list[dict[str, Any]]:
        """A user's tokens, newest first; never a hash or a secret."""
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT id, name, created_at, expires_at, revoked_at, last_used_at FROM access_tokens"
                " WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def revoke_token(self, user_id: int, token_id: str) -> None:
        with self.store.tx() as db:
            cur = db.execute(
                "UPDATE access_tokens SET revoked_at = ? WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
                (self.clock(), token_id, user_id),
            )
        if cur.rowcount == 0:
            raise FileError(404, f"no live token {token_id}")

    def by_token(self, secret: str) -> User | None:
        """The active owner of a live token (and mark it used), or None."""
        if not secret.startswith(PAT_PREFIX) or len(secret) > 200:
            return None
        now = self.clock()
        with self.store.tx() as db:
            row = db.execute(
                "SELECT u.*, t.id AS token_id FROM access_tokens t JOIN users u ON u.id = t.user_id WHERE"
                " t.token_hash = ? AND t.revoked_at IS NULL AND t.expires_at > ? AND u.status = 'active'",
                (token_hash(secret), now),
            ).fetchone()
            if row is not None:
                db.execute("UPDATE access_tokens SET last_used_at = ? WHERE id = ?", (now, row["token_id"]))
        return None if row is None else User(**{k: row[k] for k in ("id", "email", "role", "status")})
