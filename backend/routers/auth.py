"""
routers/auth.py
Single endpoint: POST /api/auth/login
This is the ONLY route in this whole backend that stays public
(besides /health) — every other route requires a valid token from
here, enforced via Depends(get_current_admin) in main.py.

UPDATED: this same endpoint now also accepts MASTER_USERNAME /
MASTER_PASSWORD_HASH credentials (checked first) and issues a
role="master" token in that case. The regular operator check below
it is completely untouched — same username/password/hash comparison
as before, same role="operator" behavior. Both login.html (operator)
and the new master-login.html (master) point at this one endpoint;
which set of credentials you type in decides which role you get.

REVERTED (Mart Days operator login removed): this backend used to
also carry a THIRD operator login (ADMIN_MARTDAYS_USERNAME), issuing
a token with an event="mart_days" claim so the badge desk knew which
of two tables to search/register into. Now that Mart Days runs on
its own separate portal, there's only ever one event again — so the
event claim is gone entirely and this is back to just two logins:
regular operator (ADMIN_USERNAME) and master (MASTER_USERNAME), plus
the separate scanner login below.
"""

from fastapi import APIRouter, HTTPException, status

from config import settings
from models.auth import LoginRequest, LoginResponse
from utils.auth import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    username = payload.username.strip()

    # ---- Try MASTER credentials first ----
    # Only matches if MASTER_USERNAME is actually configured in .env
    # (empty string means master login is simply not set up yet, so
    # this branch never accidentally matches an empty username).
    if settings.master_username.strip() and username == settings.master_username.strip():
        if verify_password(payload.password, settings.master_password_hash):
            token = create_access_token(settings.master_username, role="master")
            return LoginResponse(
                access_token=token,
                expires_in_hours=settings.jwt_expiry_hours,
                username=settings.master_username,
                role="master",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # ---- Try SCANNER credentials next ----
    # Same guard pattern as master: only matches if SCANNER_USERNAME
    # is actually configured, so an empty value never accidentally
    # matches.
    if settings.scanner_username.strip() and username == settings.scanner_username.strip():
        if verify_password(payload.password, settings.scanner_password_hash):
            token = create_access_token(settings.scanner_username, role="scanner")
            return LoginResponse(
                access_token=token,
                expires_in_hours=settings.jwt_expiry_hours,
                username=settings.scanner_username,
                role="scanner",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # ---- Regular operator credentials ----
    # Unchanged password/hash comparison from before Mart Days ever
    # existed in this backend.
    valid_username = username == settings.admin_username.strip()
    valid_password = verify_password(payload.password, settings.admin_password_hash)

    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(settings.admin_username, role="operator")
    return LoginResponse(
        access_token=token,
        expires_in_hours=settings.jwt_expiry_hours,
        username=settings.admin_username,
        role="operator",
    )