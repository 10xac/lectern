"""Who is connected through OAuth, and which apps registered: the views people and admins use."""

from __future__ import annotations

import json
from typing import Any

from lectern.files import FileError
from lectern.store import Store


class Connections:
    """Mixed into ``OAuth``: a person's connected apps, every connection, and the registered clients."""

    store: Store
    clock: Any

    # connections (people) and clients (admins) --------------------------------------------------

    def connections(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """Live grants, newest first: whose, which app, when made and last used."""
        sql = (
            "SELECT g.id, g.user_id, u.email, c.info, g.created_at, g.last_used_at FROM oauth_grants g"
            " JOIN oauth_clients c ON c.id = g.client_id JOIN users u ON u.id = g.user_id"
            " WHERE g.revoked_at IS NULL"
            + (" AND g.user_id = ?" if user_id is not None else "")
            + " ORDER BY g.created_at DESC"
        )
        with self.store.tx() as db:
            rows = db.execute(sql, (user_id,) if user_id is not None else ()).fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "email": r["email"],
                "client": json.loads(r["info"]).get("client_name") or "an MCP client",
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
            }
            for r in rows
        ]

    def revoke_grant(self, grant_id: str, user_id: int | None = None) -> None:
        """End a connection and every token it issued (``user_id``: only one's own)."""
        with self.store.tx() as db:
            sql = "UPDATE oauth_grants SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL"
            args: tuple[Any, ...] = (self.clock(), grant_id)
            if user_id is not None:
                sql, args = sql + " AND user_id = ?", (*args, user_id)
            if db.execute(sql, args).rowcount == 0:
                raise FileError(404, "no such connection")
            db.execute(
                "UPDATE oauth_tokens SET revoked_at = ? WHERE grant_id = ? AND revoked_at IS NULL",
                (self.clock(), grant_id),
            )

    def clients(self) -> list[dict[str, Any]]:
        with self.store.tx() as db:
            rows = db.execute("SELECT * FROM oauth_clients ORDER BY created_at DESC").fetchall()
        return [
            {
                "id": r["id"],
                "name": json.loads(r["info"]).get("client_name") or "an MCP client",
                "redirect_uris": json.loads(r["info"]).get("redirect_uris", []),
                "created_at": r["created_at"],
                "last_used_at": r["last_used_at"],
                "disabled": bool(r["disabled_at"]),
            }
            for r in rows
        ]

    def set_client_disabled(self, client_id: str, disabled: bool) -> None:
        with self.store.tx() as db:
            changed = db.execute(
                "UPDATE oauth_clients SET disabled_at = ? WHERE id = ?",
                (self.clock() if disabled else None, client_id),
            ).rowcount
        if not changed:
            raise FileError(404, "no such client")
