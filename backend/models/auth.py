"""
models/auth.py
Pydantic schemas for the login endpoint. Actual auth LOGIC
(password check, JWT creation/decoding) lives in utils/auth.py —
this file only defines the request/response SHAPES, same pattern
as models/visitor.py.
"""

from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Body for POST /api/auth/login"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """
    Returned by POST /api/auth/login on success.
    `role` ("operator" or "master" or "scanner") — existing frontend
    code that doesn't read this field is unaffected.

    `event` is NEW — "other" or "mart_days" for the badge desk's two
    operator logins (ADMIN_USERNAME / ADMIN_MARTDAYS_USERNAME), None
    for master/scanner logins (they aren't scoped to one event). The
    badge desk frontend uses this directly to decide which mode to
    open in, instead of an in-app gate screen — see js/auth.js.
    """
    access_token: str
    expires_in_hours: int
    username: str
    role: str = "operator"
    event: Optional[str] = None


# NOTE: the old POST /api/auth/verify-mart-days-access endpoint (and
# its MartDaysGateRequest/MartDaysGateResponse models) was removed —
# Mart Days access on the badge desk is now decided at LOGIN time
# (ADMIN_MARTDAYS_USERNAME is its own account), not by a second
# in-app password prompt after a regular operator login.