"""
routers/mart_registration.py
The public-facing "Mart Days" registration endpoint.

CRITICAL DIFFERENCE from every other router in this backend:
this one has NO `Depends(get_current_admin)` — it must be reachable
by any visitor filling the public form, with no login. Every other
router (registration.py, master.py, sync.py, export.py) stays exactly
as it was; this file doesn't import or touch any of them.

Data lands ONLY in mart_days_registrations (see
master_store.insert_mart_days_visitor) — never in the `visitors`
table. This is what keeps the two event buckets genuinely separate:
visitors = every other event; mart_days_registrations = Mart Days
only. The onsite counter's own Mart Days path (registration.py's
POST /register-mart-days, used when staff register someone in person)
writes to the exact same table through the exact same function, so
search/print/scan for a Mart Days registrant always looks in
mart_days_registrations regardless of whether they registered
through this public form or at the counter.

EMAIL:
Confirmation email + e-badge attachment is sent via
services/email_service.py (Mailchimp Transactional / Mandrill), as a
BackgroundTask — added AFTER the response is built, so a slow/failed
email never delays or breaks the registration itself. The URN is
also still returned directly in the response, so the on-screen
confirmation never depends on the email succeeding.
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

    # The full public-form submission — every field sir asked for,
    # each its own real column in mart_days_registrations (see
    # master_store.py). Mart Days registrants live ONLY in this table
    # now — no matching visitors row is created, exactly like the
    # onsite counter's /register-mart-days route in registration.py.
    # This is what keeps the two event buckets genuinely separate:
    # visitors = everything except Mart Days; mart_days_registrations
    # = Mart Days only.
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