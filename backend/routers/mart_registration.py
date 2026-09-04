"""
routers/mart_registration.py
NEW — the public-facing "Mart Days" registration endpoint.

CRITICAL DIFFERENCE from every other router in this backend:
this one has NO `Depends(get_current_admin)` — it must be reachable
by any visitor filling the public form, with no login. Every other
router (registration.py, master.py, sync.py, export.py) stays exactly
as it was; this file doesn't import or touch any of them.

Writes go to the mart_days_registrations table only, via
master_store.insert_mart_days_visitor() — kept separate from the
`visitors` table so Mart Days registrants don't get mixed into
regular event visitor data.

source="mart_days" tags every row this endpoint creates, so it's
always possible to tell "who came in through this public form" apart
from onsite/sheet/portal registrations, e.g. for the master console
later or for debugging.

EMAIL (Step 2 — NOW wired up):
Confirmation email + QR badge attachment is sent via
services/email_service.py (Brevo API), as a BackgroundTask — added
AFTER the response is built, so a slow/failed email never delays or
breaks the registration itself. The URN is also still returned
directly in the response, so the on-screen confirmation never
depends on the email succeeding.

BADGE DOWNLOAD (Step 3 — NEW):
GET /badge-download is the "enter your URN / email / phone, get your
e-badge" self-service endpoint — the same idea as Bharat Tex's public
badge-download page, just for Mart Days. It reuses:
  - master_store.get_mart_days_by_urn() / find_mart_days_by_email() /
    find_mart_days_by_mobile()  (existing lookups, untouched)
  - services/badge_image.build_ebadge_png()  (the SAME badge builder
    already used for the confirmation email attachment, so the
    downloaded badge is pixel-identical to the emailed one)
No new tables, no new badge design — just a public lookup + the
existing PNG builder, wired together. Also public on purpose, same
as /register above.
"""

import logging
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response

from models.mart_registration import MartDaysRegisterRequest, MartDaysRegisterResponse
from services import badge_image, email_service, master_store
from utils.urn import generate_urn

logger = logging.getLogger("mart_registration")

# No Depends() here on purpose — this router is intentionally public.
router = APIRouter()

_URN_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


@router.post("/register", response_model=MartDaysRegisterResponse)
async def register_mart_days_visitor(payload: MartDaysRegisterRequest, background_tasks: BackgroundTasks):
    """
    Public registration for the Mart Days event. Anyone with the link
    (once "sir" makes it public) can submit this — no login involved.
    """
    # Duplicate check — same person can't register twice through this
    # public form. Email checked first (usually the more meaningful
    # identifier); mobile checked second. Scoped to source='mart_days'
    # only — see master_store.py's comment on these two functions.
    existing = master_store.find_mart_days_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This email is already registered for IEML Mart Sourcing Days "
                f"(URN: {existing['urn']}). Please check your inbox for the confirmation email, "
                f"or contact the registration desk if you can't find it."
            ),
        )

    existing = master_store.find_mart_days_by_mobile(payload.phone_number)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This phone number is already registered for IEML Mart Sourcing Days "
                f"(URN: {existing['urn']}). Please check your inbox for the confirmation email, "
                f"or contact the registration desk if you can't find it."
            ),
        )

    urn = generate_urn()

    # The full public-form submission — every field sir asked for,
    # each its own real column (see master_store.py's
    # mart_days_registrations table). This is the table to query/
    # export/clear for Mart Days specifically, independent of every
    # other event's data sitting in the visitors table.
    mart_days_data = {
        "buyer_type": payload.buyer_type,
        "full_name": payload.full_name,
        "company_name": payload.company_name,
        "designation": payload.designation,
        "email": payload.email,
        "phone_number": payload.phone_number,
        "address": payload.address,
        "district": payload.district,
        "state": payload.state,
        "country": payload.country,
        "pincode": payload.pincode,
    }

    try:
        master_store.insert_mart_days_visitor(urn, mart_days_data)
    except Exception:
        logger.exception("Failed to save Mart Days registration for %s", payload.email)
        raise HTTPException(
            status_code=500,
            detail="Registration could not be saved right now. Please try again.",
        )

    # Scheduled to run AFTER this response is sent to the browser —
    # registrant sees their URN instantly; email goes out right after,
    # in the background. A Mailchimp Transactional failure here never
    # touches the response the registrant already received.
    background_tasks.add_task(
        email_service.send_mart_days_confirmation,
        urn,
        payload.full_name,
        payload.email,
        payload.phone_number,
        payload.company_name,
    )

    return MartDaysRegisterResponse(
        urn=urn,
        full_name=payload.full_name,
        buyer_type=payload.buyer_type,
        email=payload.email,
    )


def _find_mart_days_registrant(identifier: str) -> dict | None:
    """
    Tries URN first (cheapest, most specific — 6-char alphanumeric,
    matches utils/urn.py's format exactly), then email, then phone.
    First match wins. find_mart_days_by_email()/find_mart_days_by_mobile()
    return the RAW mart_days_registrations row, so once either finds a
    match we re-fetch through get_mart_days_by_urn() to get back the
    normalized visitor-shape dict (name/organization/mobile/... —
    exactly what badge_image.build_ebadge_png() expects).
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None

    urn_candidate = identifier.upper().replace(" ", "")
    if _URN_PATTERN.fullmatch(urn_candidate):
        record = master_store.get_mart_days_by_urn(urn_candidate)
        if record:
            return record

    if "@" in identifier:
        found = master_store.find_mart_days_by_email(identifier)
        if found:
            return master_store.get_mart_days_by_urn(found["urn"])

    found = master_store.find_mart_days_by_mobile(identifier)
    if found:
        return master_store.get_mart_days_by_urn(found["urn"])

    return None


@router.get("/badge-download")
async def download_mart_days_badge(
    value: str = Query(..., description="URN, email, or phone number of the Mart Days registrant"),
):
    """
    Public self-service e-badge download — GET /api/mart-days/badge-download?value=...
    Looks the person up by URN/email/phone, builds the exact same PNG
    badge_image.build_ebadge_png() already emails out, and returns it
    as a direct file download. Every successful download increments
    badge_download_count (shown on the master console).
    """
    record = _find_mart_days_registrant(value)
    if not record:
        raise HTTPException(
            status_code=404,
            detail="No Mart Days registration found for this URN, email, or phone number. Please double-check and try again.",
        )

    urn = record["urn"]

    try:
        png_bytes = badge_image.build_ebadge_png(
            urn=urn,
            name=record.get("name"),
            company=record.get("organization"),
            mobile=record.get("mobile"),
            email=record.get("email"),
        )
    except Exception:
        logger.exception("Failed to build e-badge PNG for URN %s", urn)
        raise HTTPException(
            status_code=500,
            detail="Could not generate your e-badge right now. Please try again in a moment.",
        )

    try:
        master_store.log_mart_days_badge_download(urn)
    except Exception:
        # Counter is a nice-to-have for the master console — never let
        # a logging failure stop the person from getting their badge.
        logger.exception("Failed to log badge download for URN %s", urn)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="IEML-MartDays-Badge-{urn}.png"'},
    )