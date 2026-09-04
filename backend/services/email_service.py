"""
services/email_service.py
Sends the Mart Days registration confirmation email (with the e-badge
attached) via Mailchimp Transactional's API
(https://mandrillapp.com/api/1.0/messages/send.json) -- a plain HTTPS
call, no SMTP connection held open. Chosen specifically because this
backend runs on Render's free tier: a free-tier service can be asleep
when a registration comes in, and a slow/blocked SMTP handshake on a
cold-starting service is exactly the kind of thing that makes a
registration submission hang. A single HTTPS POST doesn't have that
problem.

NOTE: Mailchimp Transactional (formerly "Mandrill") is a SEPARATE
product from the regular Mailchimp Marketing plan used for
audience/campaign emails. It needs its own API key, generated from a
Mailchimp Transactional / Mandrill account, and its own verified
sending domain (SPF/DKIM) -- a normal Mailchimp Marketing login does
NOT give you this key. If MAILCHIMP_TRANSACTIONAL_API_KEY isn't set,
or the account doesn't actually have Transactional enabled, sends
will fail -- see the "if not settings..." check below, which logs a
warning and skips sending rather than crashing anything.

ALWAYS called as a FastAPI BackgroundTask from the router -- never
awaited directly in the request path. That means:
  - The registrant's screen shows their URN immediately, without
    waiting for Mailchimp to respond.
  - If Mailchimp Transactional is briefly down or misconfigured, the
    registration ITSELF still succeeds (already saved to Neon) --
    only the email silently fails and gets logged. Nobody's
    registration is lost because an email didn't go out.
"""

import base64
import logging
from typing import Optional

import httpx

from config import settings
from services.badge_image import build_ebadge_pdf
from services.email_templates import mart_days_confirmation_email

logger = logging.getLogger("email_service")

MANDRILL_SEND_URL = "https://mandrillapp.com/api/1.0/messages/send.json"


async def send_mart_days_confirmation(
    urn: str,
    full_name: str,
    email: str,
    mobile: Optional[str] = None,
    company_name: Optional[str] = None,
) -> bool:
    """
    Sends one confirmation email. Returns True/False purely for
    logging by the caller -- nothing downstream depends on the return
    value, since this always runs as a background task after the
    registration response has already gone out.
    """
    missing = []
    if not settings.mailchimp_transactional_api_key:
        missing.append("MAILCHIMP_TRANSACTIONAL_API_KEY")
    if not settings.mailchimp_sender_email:
        missing.append("MAILCHIMP_SENDER_EMAIL")
    if missing:
        logger.warning(
            "%s not set (check Render env vars, not just local .env) -- "
            "skipping email to %s (URN %s). Registration itself is unaffected.",
            " and ".join(missing), email, urn,
        )
        return False

    try:
        ebadge_pdf = build_ebadge_pdf(urn, full_name, company_name or "", mobile=mobile, email=email)
    except Exception:
        logger.exception(
            "Failed to build e-badge PDF for URN %s -- email NOT sent because of this "
            "(check assets/badge_templates and assets/fonts are present in the deployed backend)",
            urn,
        )
        return False
    ebadge_base64 = base64.b64encode(ebadge_pdf).decode("ascii")

    subject, html_body = mart_days_confirmation_email(full_name, urn)

    payload = {
        "key": settings.mailchimp_transactional_api_key,
        "message": {
            "subject": subject,
            "html": html_body,
            "from_email": settings.mailchimp_sender_email,
            "from_name": settings.mailchimp_sender_name,
            "to": [{"email": email, "name": full_name, "type": "to"}],
            "attachments": [
                {
                    "type": "application/pdf",
                    "name": f"{urn}-ebadge.pdf",
                    "content": ebadge_base64,
                }
            ],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(MANDRILL_SEND_URL, json=payload)

        if resp.status_code >= 400:
            logger.error("Mandrill send failed for URN %s (%s): %s", urn, resp.status_code, resp.text)
            return False

        results = resp.json()
        # Mandrill returns 200 even for a rejected/invalid recipient --
        # the actual per-recipient outcome is inside the response body.
        if isinstance(results, list) and results:
            status = results[0].get("status")
            if status in ("rejected", "invalid"):
                logger.error(
                    "Mandrill accepted the request but rejected the email for URN %s: %s",
                    urn, results[0],
                )
                return False

        logger.info("Confirmation email sent for URN %s to %s", urn, email)
        return True
    except Exception:
        logger.exception("Mandrill send raised an exception for URN %s", urn)
        return False