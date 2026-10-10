"""
services/email_templates.py
Email copy for the Mart Days registration confirmation email.

Edition number, dates, venue, timing and the co-located show are NO LONGER
edited here -- they come from the edition settings the master edits in the
admin page (martdays-admin), read through services/edition_store.py every
time an email is built. Only the wording of the email itself lives in this
file.
"""

from html import escape
from typing import Optional, Tuple

from services import edition_store


def mart_days_confirmation_email(full_name: str, urn: str, edition: Optional[dict] = None) -> Tuple[str, str]:
    """
    Returns (subject, html_body) for one registrant's confirmation email.
    `edition` defaults to the live settings; pass one explicitly only for
    previews/tests. Everything inserted into the HTML is escaped, since the
    name comes from a public form and the rest from an editable page.
    """
    ed = edition or edition_store.get_edition()
    name = escape(full_name or "")
    event = escape(ed["event_name"])
    label = escape(ed["edition_label"])
    dates = escape(ed["dates_long"])
    venue = escape(ed["venue"])
    timing = escape(ed.get("timing") or "")
    co_located = escape(ed.get("co_located_with") or "")
    note = escape(ed.get("email_note") or "").replace("\n", "<br>")

    subject = f"Registration Confirmed — {ed['event_name']} ({ed['edition_label']})"

    timing_html = f", <strong>{timing}</strong>" if timing else ""
    co_located_html = (
        f"<p>This edition is co-located with <strong>{co_located}</strong>.</p>" if co_located else ""
    )
    note_html = f"<p>{note}</p>" if note else ""

    html_body = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; color: #1a1d24; max-width: 600px; margin: 0 auto; line-height: 1.6;">
      <p>Dear {name},</p>

      <p>
        You are a registered participant for the <strong>{label} of {event}</strong>,
        scheduled to be held on <strong>{dates}</strong>{timing_html}, at
        <strong>{venue}</strong>.
      </p>

      {co_located_html}

      <p style="background:#f2f3f6; border:1px dashed #cfd2da; border-radius:8px; padding:12px 16px;">
        <strong>Your Registration Number (URN): {escape(urn)}</strong>
      </p>

      <p>
        Your QR badge is attached with this email as an image. Kindly present this QR Code
        at the Registration Desk to obtain your physical badge.
      </p>

      <p>
        You may show the attached QR code directly from your phone or this email at the
        desk — no separate app download is required.
      </p>

      {note_html}

      <p>We look forward to welcoming you at {event}.</p>

      <p style="color: #666c7a; font-size: 0.85rem; margin-top: 24px;">
        This is an automated confirmation email. Please do not reply to this email.
      </p>
    </div>
    """
    return subject, html_body