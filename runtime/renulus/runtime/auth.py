"""App-owned OpenAI dynamic registration, loopback OAuth, PKCE and OIDC."""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt

from renulus.contracts import ApiError
from .policy import safe_error

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = ISSUER + "/api/accounts/authorize"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"
REVOKE_URL = ISSUER + "/api/accounts/oauth/revoke"
JWKS_URL = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke " + PLAN_SCOPE


@dataclass
class _Attempt:
    id: str
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    verifier: str = field(repr=False)
    redirect_uri: str
    expires_at: float
    select: bool
    client_id: str | None = None
    subject: str | None = None
    status: str = "pending"
    error: dict | None = None
    server: asyncio.Server | None = field(default=None, repr=False)
    expiry_task: asyncio.Task | None = field(default=None, repr=False)


class CodexLogin:
    def __init__(self, manager):
        self.manager = manager
        self._attempts: dict[str, _Attempt] = {}

    async def start(self, *, select: bool = False) -> dict:
        await self.cancel_all()
        self._attempts.clear()
        login_id = secrets.token_urlsafe(24)
        self.manager._save()
        attempt = _Attempt(login_id, secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                           secrets.token_urlsafe(48), "", time.time() + 600, select)
        record = self.manager._settings["connections"].get("codex")
        if record:
            attempt.client_id = record["client_id"]
            attempt.subject = record["subject"]

        async def callback(reader, writer):
            status = 400
            try:
                raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
                if len(raw) > 8192:
                    raise ValueError("header size")
                method, target, _ = raw.split(b"\r\n", 1)[0].decode("ascii").split(" ", 2)
                parsed = urlsplit(target)
                if method != "GET" or parsed.path != "/auth/callback" or parsed.netloc:
                    raise ValueError("callback route")
                values = parse_qs(parsed.query, max_num_fields=10)
                if any(len(value) != 1 for value in values.values()):
                    raise ValueError("duplicate callback field")
                await self.complete(login_id, {key: value[0] for key, value in values.items()})
                status = 200
            except Exception:
                pass
            try:
                body = b"Return to Renulus to see the connection result."
                writer.write(("HTTP/1.1 " + str(status) + " Result\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: " + str(len(body)) + "\r\n\r\n").encode() + body)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(callback, "127.0.0.1", 0, limit=8192)
        attempt.server = server
        attempt.redirect_uri = "http://127.0.0.1:" + str(server.sockets[0].getsockname()[1]) + "/auth/callback"
        self._attempts[login_id] = attempt

        async def expire():
            await asyncio.sleep(600)
            if attempt.status == "pending":
                self._fail(attempt, ApiError("login_expired", "Start Continue with ChatGPT again.", 401, True))
                await self._stop_listener(attempt)
        attempt.expiry_task = asyncio.create_task(expire())
        query = {
            "client_id": attempt.client_id or "dynamic_agent_client",
            "ext_agent_host_id": self.manager._settings["host_id"],
            "response_type": "code", "redirect_uri": attempt.redirect_uri,
            "scope": SCOPES, "resource": RESOURCE,
            "state": attempt.state, "nonce": attempt.nonce,
            "code_challenge_method": "S256",
            "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest()).decode().rstrip("="),
        }
        if not attempt.client_id:
            query["agent_name_hint"] = "Renulus"
        # An ID token hint is optional. Omit it so no credential enters the UI.
        return {**self.status(login_id), "authorization_url": AUTHORIZE_URL + "?" + urlencode(query),
                "expires_at": attempt.expires_at}

    def status(self, login_id: str) -> dict:
        attempt = self._attempts.get(login_id)
        if not attempt:
            raise ApiError("login_not_found", "This login attempt is no longer active.", 404)
        result = {"login_id": login_id, "status": attempt.status}
        if attempt.error:
            result["error"] = dict(attempt.error)
        return result

    def _fail(self, attempt: _Attempt, error: ApiError) -> None:
        attempt.status = "error"
        attempt.error = {"code": error.code, "message": error.message, "retryable": error.retryable}

    async def _stop_listener(self, attempt: _Attempt) -> None:
        if attempt.server:
            attempt.server.close()
            # Python 3.14 waits for accepted connections in wait_closed().
            # The active callback must first send its response and close itself.
            attempt.server = None
        if attempt.expiry_task and attempt.expiry_task is not asyncio.current_task():
            attempt.expiry_task.cancel()
        attempt.verifier = attempt.nonce = attempt.state = ""

    async def _validate_identity(self, token: str, attempt: _Attempt, client_id: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError("JWT algorithm")
            async with self.manager._client() as client:
                response = await client.get(JWKS_URL)
                response.raise_for_status()
                keys = response.json()["keys"]
            candidates = [key for key in keys if key.get("kid") == header["kid"] and key.get("kty") == "RSA"]
            if len(candidates) != 1:
                raise ValueError("JWT signing key")
            key = jwt.PyJWK.from_dict(candidates[0], algorithm="RS256").key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=client_id,
                                issuer=ISSUER, options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]}, leeway=30)
            if not secrets.compare_digest(str(claims["nonce"]), attempt.nonce):
                raise ValueError("OIDC nonce")
            if attempt.subject and claims["sub"] != attempt.subject:
                raise ValueError("account changed")
            return claims
        except Exception:
            raise ApiError("identity_validation_failed", "The ChatGPT identity could not be validated. Start sign-in again.", 401, True) from None

    async def complete(self, login_id: str, query: dict[str, str]) -> dict:
        attempt = self._attempts.get(login_id)
        if not attempt or attempt.status != "pending":
            raise ApiError("login_not_active", "This login attempt has already finished.", 409)
        if not secrets.compare_digest(query.get("state", ""), attempt.state):
            raise ApiError("login_state_mismatch", "This callback does not match the Renulus login.", 403)
        attempt.status = "exchanging"
        try:
            if time.time() >= attempt.expires_at:
                raise ApiError("login_expired", "Start Continue with ChatGPT again.", 401, True)
            if query.get("error"):
                raise ApiError("login_declined", "ChatGPT sign-in or plan permission was declined.", 403, True)
            issued = query.get("client_id") or attempt.client_id
            if not issued or issued == "dynamic_agent_client" or not query.get("code"):
                raise ApiError("registration_incomplete", "ChatGPT did not return a completed app registration.", 401, True)
            if attempt.client_id and issued != attempt.client_id:
                raise ApiError("registration_mismatch", "The callback changed this account's registration.", 401)
            async with self.manager._client() as client:
                response = await client.post(TOKEN_URL, data={
                    "grant_type": "authorization_code", "client_id": issued,
                    "code": query["code"], "code_verifier": attempt.verifier,
                    "redirect_uri": attempt.redirect_uri, "resource": RESOURCE})
                response.raise_for_status()
                tokens = response.json()
            scopes = set(tokens.get("scope", "").split())
            if PLAN_SCOPE not in scopes or "resource.invoke" not in scopes:
                raise ApiError("plan_permission_required", "Authorize ChatGPT plan usage before connecting Renulus.", 403)
            if tokens.get("token_type", "").lower() != "bearer" or not isinstance(tokens.get("access_token"), str):
                raise ApiError("invalid_token_response", "ChatGPT did not return a supported plan token.", 401)
            claims = await self._validate_identity(tokens["id_token"], attempt, issued)
            catalog = await self.manager._fetch_catalog("codex", tokens["access_token"])
            if attempt.status != "exchanging":
                raise ApiError("login_cancelled", "The login was cancelled.", 409)
            self.manager._stop_provider_runs("codex")
            self.manager._clear_capabilities("codex")
            self.manager._settings["connections"]["codex"] = {
                "client_id": issued, "subject": claims["sub"], "issuer": ISSUER,
                "access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token"),
                "id_token": tokens["id_token"], "scopes": sorted(scopes),
                "expires_at": time.time() + float(tokens["expires_in"]),
            }
            self.manager._catalogs["codex"] = catalog
            self.manager._catalog_errors.pop("codex", None)
            if attempt.select:
                previous = self.manager._settings["selected_provider"]
                if previous and previous != "codex":
                    self.manager._stop_provider_runs(previous)
                self.manager._settings["selected_provider"] = "codex"
            self.manager._save()
            attempt.status = "connected"
        except Exception as error:
            if attempt.status != "cancelled":
                self._fail(attempt, safe_error(error))
        finally:
            await self._stop_listener(attempt)
        return self.status(login_id)

    async def cancel(self, login_id: str) -> dict:
        attempt = self._attempts.get(login_id)
        if not attempt:
            raise ApiError("login_not_found", "This login attempt is no longer active.", 404)
        if attempt.status in ("pending", "exchanging"):
            attempt.status = "cancelled"
        await self._stop_listener(attempt)
        return self.status(login_id)

    async def cancel_all(self) -> None:
        for login_id in list(self._attempts):
            await self.cancel(login_id)
