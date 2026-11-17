"""OAuth routes for MCP connectors (decision D13): the SDK's handlers, plus consent and connections.

GET  /.well-known/oauth-authorization-server          metadata (with RFC 9207 ``iss`` support)
GET  /.well-known/oauth-protected-resource/mcp        what protects /mcp, and who issues tokens
GET  /authorize   POST /token   POST /register   POST /revoke      (the SDK's handlers)
GET  /oauth/txn?txn=          the consent page's view (signed in; binds the request to this browser)
POST /oauth/complete          {txn, approve} → {redirect_to}
GET  /me/connections   DELETE /me/connections/{id}                 a person's connected apps
GET  /admin/oauth/clients   POST /admin/oauth/clients/{id}/disable|enable
GET  /admin/oauth/connections   DELETE /admin/oauth/connections/{id}
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import (
    AUTHORIZATION_PATH,
    REGISTRATION_PATH,
    REVOCATION_PATH,
    cors_middleware,
    create_auth_routes,
    create_protected_resource_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import AnyHttpUrl, BaseModel
from starlette.routing import Route

from lectern.auth_routes import admin, current
from lectern.guard import RateLimiter, client_ip
from lectern.oauth import OAuth
from lectern.oauth_consent import SCOPE

BINDING = "lectern_oatxn"


class Decision(BaseModel):
    txn: str
    approve: bool


def with_iss(location: str, issuer: str) -> str:
    """RFC 9207: every redirect back to the client names the issuer (error redirects included)."""
    parsed = urlparse(location)
    query = dict(parse_qsl(parsed.query))
    if "iss" in query or "error" not in query:
        return location
    return parsed._replace(query=urlencode({**query, "iss": issuer})).geturl()


def protocol_routes(oauth: OAuth) -> list[Route]:
    """The SDK's OAuth routes, with three adjustments: ``iss`` on redirects and in the metadata,
    revocation for public clients (the SDK expects a client_secret field), and a per-IP limit on
    dynamic client registration."""
    issuer = AnyHttpUrl(oauth.issuer)
    registration = ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE])
    sdk = create_auth_routes(
        oauth,
        issuer,
        client_registration_options=registration,
        revocation_options=RevocationOptions(enabled=True),
    )
    authorize_handler = AuthorizationHandler(oauth)
    revoke_handler = RevocationHandler(oauth, ClientAuthenticator(oauth))
    registration_handler = RegistrationHandler(oauth, options=registration)
    registrations = RateLimiter(int(os.environ.get("LECTERN_REGISTRATIONS_PER_MINUTE", "10")))

    async def meta(request: Request) -> Response:
        return JSONResponse(metadata_json(oauth), headers={"Cache-Control": "public, max-age=3600"})

    async def authorize(request: Request) -> Response:
        resp = await authorize_handler.handle(request)
        if "location" in resp.headers:
            resp.headers["location"] = with_iss(resp.headers["location"], oauth.issuer)
        return resp

    async def revoke(request: Request) -> Response:
        form = dict(await request.form())
        form.setdefault("client_secret", "")
        body = urlencode(form).encode()

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        return await revoke_handler.handle(Request(request.scope, receive))

    async def register(request: Request) -> Response:
        if not registrations.allow(client_ip(request, os.environ)):
            return JSONResponse(
                {"error": "slow_down", "error_description": "too many registrations"},
                429,
                headers={"Retry-After": "60"},
            )
        return await registration_handler.handle(request)

    resource = create_protected_resource_routes(
        AnyHttpUrl(oauth.resource), [issuer], scopes_supported=[SCOPE], resource_name="lectern"
    )
    ours = {
        "/.well-known/oauth-authorization-server": Route(
            "/.well-known/oauth-authorization-server",
            cors_middleware(meta, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        ),
        AUTHORIZATION_PATH: Route(AUTHORIZATION_PATH, authorize, methods=["GET", "POST"]),
        REVOCATION_PATH: Route(
            REVOCATION_PATH, cors_middleware(revoke, ["POST", "OPTIONS"]), methods=["POST", "OPTIONS"]
        ),
        REGISTRATION_PATH: Route(
            REGISTRATION_PATH, cors_middleware(register, ["POST", "OPTIONS"]), methods=["POST", "OPTIONS"]
        ),
    }
    return [ours.get(r.path, r) for r in sdk] + list(resource)


def metadata_json(oauth: OAuth) -> dict[str, Any]:
    from mcp.server.auth.routes import build_metadata

    meta = build_metadata(
        AnyHttpUrl(oauth.issuer),
        None,
        ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
        RevocationOptions(enabled=True),
    )
    return meta.model_dump(mode="json", exclude_none=True) | {
        "authorization_response_iss_parameter_supported": True
    }


def add_oauth_routes(app: FastAPI, oauth: OAuth) -> None:
    app.router.routes.extend(protocol_routes(oauth))

    @app.get("/oauth/txn")
    def txn_view(txn: str, request: Request, response: Response) -> dict[str, Any]:
        current(request)
        view, binding = oauth.txn_view(txn, request.cookies.get(BINDING))
        if binding is not None:
            response.set_cookie(
                BINDING,
                binding,
                max_age=600,
                path="/",
                httponly=True,
                samesite="lax",
                secure=oauth.issuer.startswith("https://"),
            )
        return view

    @app.post("/oauth/complete")
    def complete(body: Decision, request: Request) -> dict[str, str]:
        user = current(request)
        return {"redirect_to": oauth.complete(body.txn, request.cookies.get(BINDING), user, body.approve)}

    @app.get("/me/connections")
    def my_connections(request: Request) -> list[dict[str, Any]]:
        return oauth.connections(current(request).id)

    @app.delete("/me/connections/{grant_id}", status_code=204)
    def end_mine(grant_id: str, request: Request) -> None:
        oauth.revoke_grant(grant_id, current(request).id)

    @app.get("/admin/oauth/clients")
    def clients(request: Request) -> list[dict[str, Any]]:
        admin(request)
        return oauth.clients()

    @app.post("/admin/oauth/clients/{client_id}/{action}")
    def toggle(client_id: str, action: str, request: Request) -> dict[str, str]:
        admin(request)
        if action not in ("disable", "enable"):
            return {"detail": "use disable or enable"}
        oauth.set_client_disabled(client_id, action == "disable")
        return {"status": action + "d"}

    @app.get("/admin/oauth/connections")
    def all_connections(request: Request) -> list[dict[str, Any]]:
        admin(request)
        return oauth.connections()

    @app.delete("/admin/oauth/connections/{grant_id}", status_code=204)
    def end_any(grant_id: str, request: Request) -> None:
        admin(request)
        oauth.revoke_grant(grant_id)
