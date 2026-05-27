"""Auth + rate limiting for write endpoints.

Read endpoints stay public so the UI can list runs anonymously. Anything that
costs LLM tokens (POST /runs) goes through ``require_api_key``.

Auth model:
- Comma-separated ``ENIAK_API_KEYS`` env var holds one or more accepted keys.
- Clients send ``Authorization: Bearer <key>``.
- In ``development`` env an empty key set means "no auth" — convenient for
  local work. In production an empty key set rejects every request to keep us
  from accidentally shipping an open endpoint.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from eniak_api.config import Settings, get_settings


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _matches_any(presented: str, accepted: frozenset[str]) -> bool:
    # Constant-time comparison against each accepted key so timing doesn't
    # leak the position of the matching key.
    matched = False
    for key in accepted:
        matched = hmac.compare_digest(presented, key) or matched
    return matched


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    accepted = settings.api_key_set
    if not accepted:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Write endpoints are disabled: ENIAK_API_KEYS is empty.",
            )
        return  # dev convenience
    presented = _extract_bearer(authorization)
    if presented is None or not _matches_any(presented, accepted):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting behind Cloudflare / Railway."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
