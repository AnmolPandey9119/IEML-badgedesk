"""
services/email_templates.py
Email copy for the Mart Days registration confirmation email.

*** THIS IS THE ONE FILE TO EDIT once "sir" gives the final wording. ***
Change only the text/constants inside this file — nothing else in the
email-sending pipeline (email_service.py, the router) ever needs to
change just because the wording changes.

Current content is a PLACEHOLDER — adapted for "IEML Sourcing Mart
Days, 29th Edition" as you asked, following the same structure as
the UPITS sample you shared. Update EVENT_DATES and anything else
in double brackets once confirmed.
"""

from typing import Tuple

# ----------------------------------------------------------------
# Edit these 4 lines whenever the event details change — everything
# below reads from these, so you never have to hunt through HTML.
# ----------------------------------------------------------------
EVENT_NAME = "IEML Sourcing Mart Days"
EVENT_EDITION = "29th Edition"
EVENT_DATES = "[[EVENT DATES — TO BE CONFIRMED]]"
EVENT_VENUE = "India Expo Centre & Mart, Greater Noida"


def mart_days_confirmation_email(full_name: str, urn: str) -> Tuple[str, str]:
    """
    Returns (subject, html_body) for one registrant's confirmation
    email. Called fresh per email, so `full_name` and `urn` are
    always the specific registrant's — never reused across people.
    """
    subject = f"Registration Confirmed — {EVENT_NAME} ({EVENT_EDITION})"

    html_body = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; color: #1a1d24; max-width: 600px; margin: 0 auto; line-height: 1.6;">
      <p>Dear {full_name},</p>

      <p>
        You are a registered participant for the <strong>{EVENT_EDITION} of {EVENT_NAME}</strong>,
        scheduled to be held on <strong>{EVENT_DATES}</strong>, at
        <strong>{EVENT_VENUE}</strong>.
      </p>

      <p style="background:#f2f3f6; border:1px dashed #cfd2da; border-radius:8px; padding:12px 16px;">
        <strong>Your Registration Number (URN): {urn}</strong>
      </p>

      <p>
        Your QR badge is attached with this email as an image. Kindly present this QR Code
        at the Registration Desk to obtain your physical badge.
      </p>

      <p>
        You may show the attached QR code directly from your phone or this email at the
        desk — no separate app download is required.
      </p>

      <p>We look forward to welcoming you at {EVENT_NAME}.</p>

      <p style="color: #666c7a; font-size: 0.85rem; margin-top: 24px;">
        This is an automated confirmation email. Please do not reply to this email.
      </p>
    </div>
    """
    return subject, html_body