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
    `role` is "operator", "master", or "scanner" — existing frontend
    code that doesn't read this field is unaffected.

    REVERTED: the `event` field ("other" / "mart_days", from when the
    badge desk had two operator logins for two separate events) is
    gone — there's only ever one event again now that Mart Days runs
    on its own separate portal.
    """
    access_token: str
    expires_in_hours: int
    username: str
    role: str = "operator"