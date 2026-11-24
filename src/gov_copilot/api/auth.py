"""Microsoft Entra ID JWT validation + role-based access control.

The API is registered as an Entra app exposing App Roles: Copilot.Viewer, Copilot.Reviewer,
Copilot.Admin. Users/groups are assigned roles in Entra; the access token's `roles` claim is
checked here. Tokens are validated against the tenant's JWKS (signature, issuer, audience, expiry).
When AUTH_ENABLED=false (local dev only) a synthetic dev user with all roles is used.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from gov_copilot.config import Settings, get_settings


class Role(StrEnum):
    VIEWER = "Copilot.Viewer"
    REVIEWER = "Copilot.Reviewer"
    ADMIN = "Copilot.Admin"


# Role hierarchy: admin > reviewer > viewer
_IMPLIES = {
    Role.ADMIN: {Role.ADMIN, Role.REVIEWER, Role.VIEWER},
    Role.REVIEWER: {Role.REVIEWER, Role.VIEWER},
    Role.VIEWER: {Role.VIEWER},
}


class User(BaseModel):
    oid: str
    name: str
    roles: set[Role]

    def has(self, role: Role) -> bool:
        return any(role in _IMPLIES[r] for r in self.roles)


_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks(tenant_id: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys")


def decode_token(token: str, s: Settings) -> dict[str, Any]:
    key = _jwks(s.entra_tenant_id).get_signing_key_from_jwt(token).key
    claims: dict[str, Any] = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=[s.entra_api_audience, s.entra_api_audience.removeprefix("api://")],
        issuer=f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0",
        options={"require": ["exp", "iat", "aud", "iss"]},
    )
    return claims


def user_from_claims(claims: dict[str, Any]) -> User:
    roles = {Role(r) for r in claims.get("roles", []) if r in Role._value2member_map_}
    return User(oid=str(claims.get("oid", "")), name=str(claims.get("name", "")), roles=roles)


async def current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    s: Annotated[Settings, Depends(get_settings)],
) -> User:
    if not s.auth_enabled:
        user = User(oid="dev", name="Local Developer", roles={Role.ADMIN})
    else:
        if creds is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
        try:
            user = user_from_claims(decode_token(creds.credentials, s))
        except jwt.PyJWTError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from e
    request.state.user = user
    return user


def require(role: Role):  # type: ignore[no-untyped-def]
    async def dep(user: Annotated[User, Depends(current_user)]) -> User:
        if not user.has(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role {role.value}")
        return user

    return dep
