"""
utils/auth.py
Everything auth-related lives here:
  - verify_password()  -> checks a plaintext password against the
                           bcrypt hash stored in .env
  - create_access_token() -> issues a JWT after successful login
  - get_current_admin     -> FastAPI dependency; add this to any
                           router that must be login-gated (any
                           logged-in user — operator OR master).
                           Raises 401 if the request has no valid
                           token. Behavior is UNCHANGED from before.
  - get_current_master    -> NEW. Same as above, but additionally
                           requires role="master". Use this on
                           master-console-only routes (delete,
                           master stats, etc). Raises 403 if a
                           logged-in operator (not master) tries
                           to hit one of those routes.

Nothing outside this file should touch jwt/bcrypt directly — same
"single place decides" pattern as services/org_api_client.py.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

_JWT_ALGORITHM = "HS256"

# FastAPI's Bearer scheme — reads the "Authorization: Bearer <token>"
# header automatically and hands us the raw token.
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Checks a plaintext password against the stored bcrypt hash."""
    if not password_hash:
        # No hash configured in .env yet — refuse everything rather
        # than silently accepting any password.
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash in .env (e.g. someone pasted the plaintext
        # password by mistake) — treat as "no valid login possible".
        return False


def hash_password(plain_password: str) -> str:
    """Used by generate_password_hash.py to create the .env value."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(username: str, role: str = "operator") -> str:
    """
    Issues a JWT valid for settings.jwt_expiry_hours, signed with
    settings.jwt_secret. `role` is either "operator" (regular counter
    login, the default — so any existing call site that doesn't pass
    role keeps working exactly as before) or "master" (master console
    login).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please log in again",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session, please log in again",
        )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Add `Depends(get_current_admin)` to any router that must be
    login-gated (search, register, print, counter). Returns the
    logged-in username if the token is valid; raises 401 otherwise.
    UNCHANGED: still accepts a valid token from EITHER an operator
    or a master login — this is the "just logged in" check, not a
    role check.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in",
        )
    payload = _decode_token(credentials.credentials)
    return payload["sub"]


async def get_current_master(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    NEW. Add `Depends(get_current_master)` to any route that only the
    master console should be able to call (delete a visitor, master
    stats/list endpoints). Requires a valid token AND role="master" —
    a regular counter operator's token will be rejected with 403 here,
    even though it's perfectly valid for get_current_admin routes.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in",
        )
    payload = _decode_token(credentials.credentials)
    if payload.get("role") != "master":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master console access only",
        )
    return payload["sub"]


async def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    NEW. Add `Depends(get_current_staff)` to any route that operator
    OR master should reach, but a scanner-role token must NOT — e.g.
    exporting the full visitor database, or creating/editing visitor
    records. get_current_admin (above) accepts ANY valid role
    including "scanner", which is correct for search/print-log/
    scan-log (the scanner app genuinely needs those), but wrong for
    routes a gate-staff login was never meant to reach. This is that
    narrower check: valid token AND role in {"operator", "master"}.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in",
        )
    payload = _decode_token(credentials.credentials)
    if payload.get("role") not in ("operator", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or master access only",
        )
    return payload["sub"]