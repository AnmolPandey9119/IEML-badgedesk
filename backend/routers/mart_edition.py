"""
routers/mart_edition.py
Edition settings for Mart Days (edition number, dates, timing, venue,
co-located show, email note).

  GET  /api/mart-edition              PUBLIC  -- the registration page, the
                                      e-badge page and the desk call this on
                                      load to show the current edition.
  PUT  /api/mart-edition              MASTER  -- save changes (admin page).
  GET  /api/mart-edition/email-preview MASTER -- subject + HTML of the
                                      confirmation email with current values.
  POST /api/mart-edition/test-email   MASTER  -- send that email (with a
                                      sample badge) to an address you enter.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field, model_validator

from services import edition_store, email_service
from services.email_templates import mart_days_confirmation_email
from utils.auth import get_current_master

router = APIRouter()


class EditionUpdate(BaseModel):
    edition_number: int = Field(..., ge=1, le=999, description="e.g. 30 -> shown as '30th Edition'")
    start_date: date
    end_date: date
    event_name: str = Field(..., min_length=1, max_length=120)
    timing: str = Field("", max_length=60)
    venue: str = Field("", max_length=200)
    co_located_with: str = Field("", max_length=200)
    badge_tag: str = Field("", max_length=60)
    email_note: str = Field("", max_length=1000)

    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class TestEmailRequest(BaseModel):
    to: EmailStr


@router.get("")
async def get_edition(response: Response):
    # Short cache: pages load fast, and a saved change shows up within ~30s.
    response.headers["Cache-Control"] = "public, max-age=30"
    return edition_store.get_edition()


@router.put("")
async def update_edition(payload: EditionUpdate, master: str = Depends(get_current_master)):
    data = payload.model_dump()
    for key in ("event_name", "timing", "venue", "co_located_with", "badge_tag", "email_note"):
        data[key] = data[key].strip()
    return edition_store.save_edition(data, updated_by=master)


@router.get("/email-preview")
async def email_preview(_: str = Depends(get_current_master)):
    subject, html = mart_days_confirmation_email("Test Registrant", "ABC123")
    return {"subject": subject, "html": html}


@router.post("/test-email")
async def send_test_email(payload: TestEmailRequest, _: str = Depends(get_current_master)):
    ok = await email_service.send_mart_days_confirmation(
        urn="TEST01",
        full_name="Test Registrant",
        email=str(payload.to),
        mobile="+91 9999999999",
        company_name="Test Company",
    )
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Test email could not be sent. Check MAILCHIMP_TRANSACTIONAL_API_KEY / "
                   "MAILCHIMP_SENDER_EMAIL on the server and the server logs.",
        )
    return {"sent": True, "to": str(payload.to)}