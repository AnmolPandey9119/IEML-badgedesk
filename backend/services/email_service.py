"""
services/email_service.py
Sends the Mart Days registration confirmation email (with the e-badge
attached) via Gmail SMTP, using an App Password.

SWITCHED FROM Mailchimp Transactional (Mandrill) because Mandrill
needs its OWN paid activation (separate billing block, e.g. $20 per
25,000 emails) on top of a regular Mailchimp Marketing plan -- that
wasn't set up, so every send was rejected with reason
"recipient-domain-mismatch" (Mandrill's restricted/demo-mode
behaviour: only deliver to the account's own verified domain until
fully activated).

GMAIL APP PASSWORD (NOT your normal Gmail login password):
  1. Turn on 2-Step Verification on the Gmail account:
     https://myaccount.google.com/security
  2. Generate an App Password: https://myaccount.google.com/apppasswords
  3. Put the sending Gmail address in GMAIL_SENDER_EMAIL and the
     16-character app password (no spaces) in GMAIL_APP_PASSWORD.

GMAIL SENDING LIMITS: a regular Gmail account can send ~500
emails/day (a Google Workspace account ~2000/day). Fine for
onsite/Mart-Days registration volumes; if the event ever needs more
than that in a day, this will need revisiting.

Still ALWAYS called as a FastAPI BackgroundTask from the router --
never awaited directly in the request path -- for the same reason as
before: the registrant's screen shows their URN immediately, and if
Gmail SMTP is briefly down/misconfigured, the registration ITSELF
still succeeds (already saved to Neon) -- only the email silently
fails and gets logged.

smtplib is blocking (not async), so the actual send happens inside
asyncio.to_thread() -- this keeps the SMTP handshake from blocking
the FastAPI event loop while it runs.
"""

import asyncio
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from config import settings
from services.badge_image import build_ebadge_pdf
from services.email_templates import mart_days_confirmation_email

logger = logging.getLogger("email_service")

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


def _send_via_gmail_sync(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    ebadge_pdf: bytes,
    urn: str,
) -> None:
    """
    Blocking SMTP send -- runs inside asyncio.to_thread() from the
    caller, never called directly on the event loop.
    """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.gmail_sender_name, settings.gmail_sender_email))
    msg["To"] = formataddr((to_name, to_email))

    msg.attach(MIMEText(html_body, "html"))

    attachment = MIMEApplication(ebadge_pdf, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=f"{urn}-ebadge.pdf"
    )
    msg.attach(attachment)

    with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=20) as server:
        server.login(settings.gmail_sender_email, settings.gmail_app_password)
        server.sendmail(settings.gmail_sender_email, [to_email], msg.as_string())


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
    if not settings.gmail_sender_email:
        missing.append("GMAIL_SENDER_EMAIL")
    if not settings.gmail_app_password:
        missing.append("GMAIL_APP_PASSWORD")
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

    subject, html_body = mart_days_confirmation_email(full_name, urn)

    try:
        await asyncio.to_thread(
            _send_via_gmail_sync, email, full_name, subject, html_body, ebadge_pdf, urn,
        )
        logger.info("Confirmation email sent (Gmail SMTP) for URN %s to %s", urn, email)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail SMTP login failed for URN %s -- GMAIL_APP_PASSWORD is wrong/expired, "
            "or it's the normal Gmail password instead of an App Password", urn,
        )
        return False
    except Exception:
        logger.exception("Gmail SMTP send raised an exception for URN %s", urn)
        return False