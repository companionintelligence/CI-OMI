"""
API Authentication for Omi Companion App
Shared-secret API key guarding every route that reads user data or mutates state
"""
import logging
import os
import secrets
from typing import Optional

from fastapi import HTTPException, Security, WebSocket, WebSocketException, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Environment variable holding the shared secret. `utils.config` already calls
# load_dotenv() at import time, so a value placed in `.env` is visible here too.
API_KEY_ENV_VAR = "OMI_COMPANION_API_KEY"

# Header clients present the key in.
API_KEY_HEADER_NAME = "X-API-Key"

# Query parameter accepted on /ws/live only - browsers cannot set request headers
# on a WebSocket handshake.
API_KEY_QUERY_PARAM = "api_key"

# Not enforced, only warned about: refusing to start on a short key would lock
# operators out of an appliance they can already reach over the local network.
MIN_API_KEY_LENGTH = 16

# Deliberately NOT a field on SystemConfig. `GET /api/status` serialises the whole
# config object with asdict() and `PUT /api/config` setattr()s arbitrary keys onto
# it, so anything stored there is both readable and writable over the API.
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def get_configured_api_key() -> str:
    """Read the shared secret from the environment.

    Read per request rather than cached at import time so the key can be rotated
    without rebuilding the application object.
    """
    return os.getenv(API_KEY_ENV_VAR, "").strip()


def _matches(presented: Optional[str], expected: str) -> bool:
    """Compare a presented key against the configured one in constant time"""
    if not presented:
        return False
    return secrets.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def _unconfigured_message() -> str:
    """Operator-facing message for a deployment with no key set"""
    return (
        f"API authentication is not configured. Set {API_KEY_ENV_VAR} in the "
        "server environment or .env file."
    )


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """FastAPI dependency rejecting any request without a valid API key.

    Fails closed: when OMI_COMPANION_API_KEY is unset every guarded request is
    refused with 503 rather than allowed through. An unconfigured deployment must
    never be an open one.
    """
    expected = get_configured_api_key()
    if not expected:
        logger.error(
            "❌ %s is not set - refusing guarded request", API_KEY_ENV_VAR
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_unconfigured_message(),
        )

    if not _matches(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )

    return api_key


async def require_api_key_ws(websocket: WebSocket) -> str:
    """WebSocket flavour of `require_api_key`.

    An HTTPException cannot be rendered onto a WebSocket, so a failed check closes
    the handshake with 1008 (policy violation) instead. The close happens before
    accept(), so a real client sees the upgrade fail with HTTP 403.

    The key may arrive in the `X-API-Key` header or, for browser clients that
    cannot set one, the `api_key` query parameter - the latter lands in proxy
    access logs, so prefer the header wherever the client can send it.
    """
    expected = get_configured_api_key()
    if not expected:
        logger.error(
            "❌ %s is not set - refusing WebSocket handshake", API_KEY_ENV_VAR
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=_unconfigured_message(),
        )

    presented = websocket.headers.get(API_KEY_HEADER_NAME)
    if not presented:
        presented = websocket.query_params.get(API_KEY_QUERY_PARAM)

    if not _matches(presented, expected):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid or missing API key",
        )

    return presented


def log_configuration_state():
    """Report at startup whether authentication is usable"""
    expected = get_configured_api_key()
    if not expected:
        logger.error(
            "❌ %s is not set - every authenticated endpoint will return 503 "
            "until it is. Only /health stays reachable.",
            API_KEY_ENV_VAR,
        )
    elif len(expected) < MIN_API_KEY_LENGTH:
        logger.warning(
            "⚠️  %s is shorter than %d characters - use a longer random secret "
            "(e.g. `openssl rand -hex 32`).",
            API_KEY_ENV_VAR,
            MIN_API_KEY_LENGTH,
        )
    else:
        logger.info(
            "🔐 API authentication enabled via the %s header", API_KEY_HEADER_NAME
        )
