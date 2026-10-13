"""
services/email_service.py
Sends the Mart Days registration confirmation email (with the e-badge
attached) via EITHER Postmark (EMAIL_PROVIDER=postmark, or auto when
POSTMARK_SERVER_TOKEN is set) OR Mailchimp Transactional (the original
provider, below). The Mailchimp Transactional notes that follow apply to the
Mandrill path: its API
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

KNOWN ISSUE (as of this deployment): Mandrill needs its OWN paid
activation (a separate billing block, e.g. $20 per 25,000 emails) on
top of whatever regular Mailchimp Marketing plan is already active --
until that's done, the account stays in a restricted/demo mode that
only delivers to the account's OWN verified sending domain. Sending
to any other domain (gmail.com, etc.) gets accepted by the API
(200 OK) but then rejected with reason "recipient-domain-mismatch" --
visible only in the Mandrill dashboard's Activity tab, not in this
backend's own logs, since the API call itself succeeded. If mail
stops arriving again, check Activity tab there first.

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
import re
from html import unescape
from typing import Optional

import httpx

from config import settings
from services.badge_image import build_ebadge_pdf
from services.email_templates import mart_days_confirmation_email

logger = logging.getLogger("email_service")

MANDRILL_SEND_URL = "https://mandrillapp.com/api/1.0/messages/send.json"
POSTMARK_SEND_URL = "https://api.postmarkapp.com/email"


def _active_provider() -> str:
    """'postmark' or 'mandrill'. EMAIL_PROVIDER wins; else Postmark if its token is set."""
    choice = (settings.email_provider or "").strip().lower()
    if choice in ("postmark", "mandrill"):
        return choice
    return "postmark" if settings.postmark_server_token else "mandrill"


def _html_to_text(html: str) -> str:
    """Plain-text alternative for the email (better deliverability than HTML only)."""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", unescape(text)).strip()


async def _send_postmark(urn, full_name, email, subject, html_body, pdf_base64) -> bool:
    missing = []
    if not settings.postmark_server_token:
        missing.append("POSTMARK_SERVER_TOKEN")
    if not settings.postmark_sender_email:
        missing.append("POSTMARK_SENDER_EMAIL")
    if missing:
        logger.warning(
            "%s not set (check Render env vars, not just local .env) -- "
            "skipping email to %s (URN %s). Registration itself is unaffected.",
            " and ".join(missing), email, urn,
        )
        return False

    payload = {
        "From": f"{settings.postmark_sender_name} <{settings.postmark_sender_email}>",
        "To": f"{full_name} <{email}>".replace(",", " ") if full_name else email,
        "Subject": subject,
        "HtmlBody": html_body,
        "TextBody": _html_to_text(html_body),
        "MessageStream": settings.postmark_message_stream or "outbound",
        "Attachments": [
            {"Name": f"{urn}-ebadge.pdf", "Content": pdf_base64, "ContentType": "application/pdf"}
        ],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": settings.postmark_server_token,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(POSTMARK_SEND_URL, json=payload, headers=headers)
        body = {}
        try:
            body = resp.json()
        except Exception:
            pass
        # Postmark reports problems as HTTP 4xx/5xx with {"ErrorCode": n, "Message": "..."}.
        # ErrorCode 412 = account still pending approval (can only send to your own domain).
        if resp.status_code >= 400 or body.get("ErrorCode", 0) != 0:
            logger.error(
                "Postmark send failed for URN %s (HTTP %s, ErrorCode %s): %s",
                urn, resp.status_code, body.get("ErrorCode"), body.get("Message") or resp.text,
            )
            return False
        logger.info("Confirmation email sent via Postmark for URN %s to %s", urn, email)
        return True
    except Exception:
        logger.exception("Postmark send raised an exception for URN %s", urn)
        return False


async def _send_mandrill(urn, full_name, email, subject, html_body, pdf_base64) -> bool:
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

    payload = {
        "key": settings.mailchimp_transactional_api_key,
        "message": {
            "subject": subject,
            "html": html_body,
            "from_email": settings.mailchimp_sender_email,
            "from_name": settings.mailchimp_sender_name,
            "to": [{"email": email, "name": full_name, "type": "to"}],
            "attachments": [
                {"type": "application/pdf", "name": f"{urn}-ebadge.pdf", "content": pdf_base64}
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


async def send_mart_days_confirmation(
    urn: str,
    full_name: str,
    email: str,
    mobile: Optional[str] = None,
    company_name: Optional[str] = None,
) -> bool:
    """
    Sends one confirmation email through the active provider. Returns True/False
    purely for logging by the caller -- nothing downstream depends on the return
    value, since this always runs as a background task after the registration
    response has already gone out.
    """
    try:
        # crop_front_only=True -- email should only show the front side of
        # the card, matching what the physical badge looks like when worn.
        # The /badge-download endpoint (routers/mart_registration.py) does
        # NOT pass this, so it keeps downloading the full front+back PDF
        # exactly as it does today.
        ebadge_pdf = build_ebadge_pdf(urn, full_name, company_name or "", mobile=mobile, email=email, crop_front_only=True)
    except Exception:
        logger.exception(
            "Failed to build e-badge PDF for URN %s -- email NOT sent because of this "
            "(check assets/badge_templates and assets/fonts are present in the deployed backend)",
            urn,
        )
        return False

    pdf_base64 = base64.b64encode(ebadge_pdf).decode("ascii")
    subject, html_body = mart_days_confirmation_email(full_name, urn)

    if _active_provider() == "postmark":
        return await _send_postmark(urn, full_name, email, subject, html_body, pdf_base64)
    return await _send_mandrill(urn, full_name, email, subject, html_body, pdf_base64)