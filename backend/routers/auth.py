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
"""

from fastapi import APIRouter, Depends, HTTPException, status

from config import settings
from models.auth import LoginRequest, LoginResponse, MartDaysGateRequest, MartDaysGateResponse
from utils.auth import create_access_token, get_current_staff, verify_password

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

    # ---- Regular operator credentials (unchanged from before) ----
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


@router.post("/verify-mart-days-access", response_model=MartDaysGateResponse, dependencies=[Depends(get_current_staff)])
async def verify_mart_days_access(payload: MartDaysGateRequest):
    """
    Second gate, only reachable by someone who's ALREADY logged in as
    operator/master (get_current_staff) — this is not a login by
    itself, it just unlocks the counter app's "Mart Days" mode for
    this browser session. A blank MART_DAYS_GATE_PASSWORD in .env
    means this can never succeed (fails safe), matching the same
    "empty config = refuse everything" behavior as verify_password().
    """
    configured = settings.mart_days_gate_password
    if not configured or payload.password != configured:
        # 403, not 401 — this must NOT trigger api.js's auto-logout-on-401
        # handling (that's reserved for an expired/invalid session token).
        # A wrong Mart Days gate password just means "not authorized for
        # this specific mode", exactly like get_current_master's 403 for
        # a valid-but-wrong-role token.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect Mart Days password",
        )
    return MartDaysGateResponse(ok=True)