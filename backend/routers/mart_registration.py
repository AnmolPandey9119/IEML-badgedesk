"""
routers/mart_registration.py
NEW — the public-facing "Mart Days" registration endpoint.

CRITICAL DIFFERENCE from every other router in this backend:
this one has NO `Depends(get_current_admin)` — it must be reachable
by any visitor filling the public form, with no login. Every other
router (registration.py, master.py, sync.py, export.py) stays exactly
as it was; this file doesn't import or touch any of them.

Data still lands in the SAME `visitors` table, via the SAME
master_store.insert_visitor()/generate_urn() that onsite counter
registration and the Google Sheet sync already use — so a Mart Days
registrant shows up correctly in search, print, and the master
console, no separate table or code path needed there.

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
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.mart_registration import MartDaysRegisterRequest, MartDaysRegisterResponse
from services import email_service, master_store
from utils.urn import generate_urn

logger = logging.getLogger("mart_registration")

# No Depends() here on purpose — this router is intentionally public.
router = APIRouter()


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

    row_data = {
        "name": payload.full_name,
        "org": payload.company_name,
        "city": payload.district,
        "category": payload.to_category_slug(),
        "status": None,
        "email": payload.email,
        "mobile": payload.phone_number,
        # Everything below isn't a core visitors column — it rides
        # along in extra_json automatically (see master_store.py),
        # exactly like "designation" already does for onsite regs.
        "designation": payload.designation,
        "address": payload.address,
        "state": payload.state,
        "country": payload.country,
        "pincode": payload.pincode,
        "buyer_type": payload.buyer_type,
        "event": "IEML Mart Sourcing Days",
    }

    try:
        master_store.insert_visitor(urn, row_data, source="mart_days")
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