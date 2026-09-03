"""
models/auth.py
Pydantic schemas for the login endpoint. Actual auth LOGIC
(password check, JWT creation/decoding) lives in utils/auth.py —
this file only defines the request/response SHAPES, same pattern
as models/visitor.py.
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Body for POST /api/auth/login"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """
    Returned by POST /api/auth/login on success.
    `role` is NEW ("operator" or "master") — existing frontend code
    (login.html/app.js) already ignores fields it doesn't read, so
    this addition doesn't change anything for the existing counter
    login flow.
    """
    access_token: str
    expires_in_hours: int
    username: str
    role: str = "operator"


class MartDaysGateRequest(BaseModel):
    """Body for POST /api/auth/verify-mart-days-access."""
    password: str = Field(..., min_length=1)


class MartDaysGateResponse(BaseModel):
    """Returned by POST /api/auth/verify-mart-days-access on success."""
    ok: bool = True