"""
JWT helpers for authenticating end-user clients connecting to the Socket
gateway (app/socket_server.py).

This is separate from API_KEY (app/config.py), which is a static
service-to-service secret. A JWT here carries a `sub` claim identifying the
connecting user, so the gateway can tell clients apart and enforce that a
user only ever joins their own conversation thread.

Nothing here checks a password or a user store — see POST /auth/token in
socket_server.py for the (demo) issuing endpoint.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config import JWT_SECRET_KEY, JWT_EXPIRE_MINUTES

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or invalid."""


def create_token(user_id: str) -> str:
    """Issue a signed JWT for user_id, valid for JWT_EXPIRE_MINUTES."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: Optional[str]) -> str:
    """Verify a token's signature and expiry, and return its user_id (`sub`)."""
    if not token:
        raise TokenError("Missing token")

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token expired")
    except jwt.InvalidTokenError:
        raise TokenError("Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise TokenError("Token missing 'sub' claim")

    return user_id
