"""
services/email_service.py
Sends the Mart Days registration confirmation email (with the QR
badge attached) via Brevo's transactional email API
(https://api.brevo.com/v3/smtp/email) — a plain HTTPS call, no SMTP
connection held open. Chosen specifically because this backend runs
on Render's free tier: a free-tier service can be asleep when a
registration comes in, and a slow/blocked SMTP handshake on a
cold-starting service is exactly the kind of thing that makes a
registration submission hang. A single HTTPS POST doesn't have that
problem.

ALWAYS called as a FastAPI BackgroundTask from the router — never
awaited directly in the request path. That means:
  - The registrant's screen shows their URN immediately, without
    waiting for Brevo to respond.
  - If Brevo is briefly down or misconfigured, the registration
    ITSELF still succeeds (already saved to Neon) — only the email
    silently fails and gets logged. Nobody's registration is lost
    because an email didn't go out.
"""

import base64
import io
import logging
from typing import Optional

import httpx
import qrcode

from config import settings
from services.email_templates import mart_days_confirmation_email

logger = logging.getLogger("email_service")

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _generate_qr_png_base64(urn: str, name: str, mobile: Optional[str], email: Optional[str]) -> str:
    """
    Builds the QR image and returns it as base64 (what Brevo's
    attachment field expects). QR content format matches
    frontend/js/print.js EXACTLY (URN first line, then Name/Mobile/
    Email if present) — so a badge printed at the counter and this
    emailed QR always decode to the identical thing for the
    entrance-scanning app. If this format ever changes in print.js,
    mirror the change here too.
    """
    lines = [f"URN: {urn}"]
    if name:
        lines.append(f"Name: {name}")
    if mobile:
        lines.append(f"Mobile: {mobile}")
    if email:
        lines.append(f"Email: {email}")
    qr_text = "\n".join(lines)

    img = qrcode.make(qr_text)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def send_mart_days_confirmation(
    urn: str,
    full_name: str,
    email: str,
    mobile: Optional[str] = None,
) -> bool:
    """
    Sends one confirmation email. Returns True/False purely for
    logging by the caller — nothing downstream depends on the return
    value, since this always runs as a background task after the
    registration response has already gone out.
    """
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        logger.warning(
            "BREVO_API_KEY / BREVO_SENDER_EMAIL not set in .env — skipping "
            "email to %s (URN %s). Registration itself is unaffected.",
            email, urn,
        )
        return False

    qr_base64 = _generate_qr_png_base64(urn, full_name, mobile, email)
    subject, html_body = mart_days_confirmation_email(full_name, urn)

    payload = {
        "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
        "to": [{"email": email, "name": full_name}],
        "subject": subject,
        "htmlContent": html_body,
        "attachment": [
            {
                "content": qr_base64,
                "name": f"{urn}-badge-qr.png",
            }
        ],
    }
    headers = {
        "api-key": settings.brevo_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Brevo send failed for URN %s (%s): %s", urn, resp.status_code, resp.text)
            return False
        logger.info("Confirmation email sent for URN %s to %s", urn, email)
        return True
    except Exception:
        logger.exception("Brevo send raised an exception for URN %s", urn)
        return False