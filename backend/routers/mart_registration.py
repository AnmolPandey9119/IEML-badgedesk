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

EMAIL (Step 2 — NOT wired up yet):
Right where marked below is exactly where the confirmation email +
QR badge attachment will be triggered once the email approach
(SMTP vs Brevo etc.) is decided. Registration itself already works
fully without it — the URN is returned directly in the response so
the frontend can show it on-screen either way.
"""

import logging

from fastapi import APIRouter, HTTPException

from models.mart_registration import MartDaysRegisterRequest, MartDaysRegisterResponse
from services import master_store
from utils.urn import generate_urn

logger = logging.getLogger("mart_registration")

# No Depends() here on purpose — this router is intentionally public.
router = APIRouter()


@router.post("/register", response_model=MartDaysRegisterResponse)
async def register_mart_days_visitor(payload: MartDaysRegisterRequest):
    """
    Public registration for the Mart Days event. Anyone with the link
    (once "sir" makes it public) can submit this — no login involved.
    """
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
        "event": "IEML Sourcing Mart Days",
    }

    try:
        master_store.insert_visitor(urn, row_data, source="mart_days")
    except Exception:
        logger.exception("Failed to save Mart Days registration for %s", payload.email)
        raise HTTPException(
            status_code=500,
            detail="Registration could not be saved right now. Please try again.",
        )

    # ------------------------------------------------------------
    # TODO (Step 2): trigger confirmation email here, e.g.
    #   await email_service.send_mart_days_confirmation(urn, payload)
    # Intentionally not called yet — email approach not decided.
    # ------------------------------------------------------------

    return MartDaysRegisterResponse(
        urn=urn,
        full_name=payload.full_name,
        buyer_type=payload.buyer_type,
        email=payload.email,
    )