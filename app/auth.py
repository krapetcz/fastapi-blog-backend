"""
Auth0 JWT verification for FastAPI.

Validates incoming `Authorization: Bearer <JWT>` against the Auth0 JWKS
endpoint and exposes the decoded claims to route handlers via a FastAPI
dependency.

Public surface:
- bearer_scheme:     FastAPI security object (extracts the Bearer credentials)
- verify_jwt:        pure function — verifies a token string, returns claims
- get_current_user:  FastAPI dependency — yields claims dict, raises 401 on error
- require_admin:     FastAPI dependency — passes only if claims.email is whitelisted

Design notes:
- We use HTTPBearer(auto_error=False) and raise our own 401 (with the
  WWW-Authenticate header that RFC 6750 expects) rather than relying on
  FastAPI's default 403 when the header is missing.
- The PyJWKClient is cached per Auth0 domain via lru_cache so the JWKS
  document is fetched once and reused; inside the client, individual
  signing keys are cached for `lifespan` seconds (key rotation safety).
- Issuer comparison is normalized to a single trailing slash because
  Auth0 emits `iss` with a trailing slash and we don't want .env typos
  to silently break verification.
"""
from functools import lru_cache
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import Settings, get_settings


# auto_error=False → we handle the missing-header case ourselves and
# can return 401 + WWW-Authenticate instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    """Build a 401 with the WWW-Authenticate header RFC 6750 expects."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def _jwks_client_for(domain: str) -> PyJWKClient:
    """
    Process-wide JWKS client for one Auth0 domain.

    Caching the client matters: each PyJWKClient instance maintains its
    own in-memory cache of signing keys, so creating a new client per
    request would re-fetch JWKS every time.
    """
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=600)


def _normalize_issuer(value: str) -> str:
    """Force exactly one trailing slash, matching Auth0's iss claim format."""
    return value.rstrip("/") + "/"


def verify_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """
    Verify an Auth0-issued JWT and return its claims.

    Checks performed (any failure raises 401):
    - Token header references a known JWKS key (kid).
    - RS256 signature is valid.
    - `aud` matches the configured API audience.
    - `iss` matches the configured issuer (normalized).
    - `exp` is in the future (PyJWT checks by default).

    We catch jwt.PyJWTError — the shared base class of PyJWKClientError
    (JWKS fetch / unknown kid) and InvalidTokenError (bad signature,
    wrong audience/issuer, expired, malformed header). Any failure from
    PyJWT means the caller is unauthenticated from the API's POV, so
    surfacing all of them as 401 is correct and keeps the code simple.
    """
    try:
        signing_key = (
            _jwks_client_for(settings.auth0_domain)
            .get_signing_key_from_jwt(token)
            .key
        )
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=_normalize_issuer(settings.auth0_issuer),
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized(f"Invalid token: {exc}") from exc

    return claims


def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """
    FastAPI dependency: decode and verify the Bearer token, return claims.

    Raises 401 if the header is missing, uses a non-Bearer scheme, or the
    token fails any verification step.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing bearer token")
    if credentials.scheme.lower() != "bearer":
        raise _unauthorized("Expected Bearer authentication scheme")

    return verify_jwt(credentials.credentials, settings)


def require_admin(
    claims: Annotated[dict[str, Any], Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """
    FastAPI dependency: allow only admins past.

    Chains on top of get_current_user, so the caller must already have a
    valid Auth0 JWT. Then checks the token's `email` claim against the
    ADMIN_EMAILS whitelist from settings.

    Raises:
        403 Forbidden if:
        - the token has no `email` claim (probably missing the 'email'
          scope on the frontend — Auth0 only issues the claim when the
          scope is granted), or
        - the email is not on the whitelist.

    Uses 403, not 401: the user IS authenticated, they just lack
    permission. That's the distinction RFC 7235 expects.

    Returns the same claims dict, so handlers can still read e.g. `sub`
    if they need it.
    """
    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Token has no 'email' claim — ensure the frontend requests "
                "the 'email' scope when logging in with Auth0."
            ),
        )
    if email.lower() not in settings.admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
    return claims
