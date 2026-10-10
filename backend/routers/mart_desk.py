"""
routers/mart_desk.py
NEW — the Mart Days onsite registration + print desk.

This is the second, fully independent "desk" replacing the old
in-app event-toggle idea (frontend's js/event-gate.js, which called a
backend endpoint that no longer exists, plus a badge desk that
crashed on load because of an undefined CURRENT_EVENT reference —
see routers/registration.py and frontend/js/app.js). Instead of one
badge desk with two logins/events sharing the same UI, there are now
two completely separate desks:

  - routers/registration.py  -> logs in with ADMIN_USERNAME, reads/
                                 writes the `visitors` table. Unchanged.
  - routers/mart_desk.py     -> THIS file. Logs in with
                                 MART_DESK_USERNAME (see config.py),
                                 reads/writes mart_days_registrations
                                 only.

Every route here is gated by Depends(get_current_mart_desk) — a
token from the regular operator/master/scanner logins is rejected
here with 403, and a mart_desk token is equally rejected by every
other router's dependency. Two logins, two tables, two desks, no
shared state between them beyond running in the same backend process.

Reuses models.visitor's shapes (Visitor, SearchResponse, ...) instead
of inventing parallel ones — the frontend for this desk
(frontend-martdays-desk/) is a copy of the regular badge desk
frontend with just its API base path changed, so keeping the exact
same JSON shape means app.js/print.js needed zero logic changes on
that side. `category` in the shared shape doubles as this table's
buyer_type.

Deliberately separate from routers/mart_registration.py (the public,
no-login /api/mart-days/register + /badge-download endpoints, used by
frontend-martdays and martdays-badge) — that router is untouched by
this file and stays exactly as it was.
"""

from fastapi import APIRouter, Depends, HTTPException

from models.mart_registration import BUYER_TYPES
from models.visitor import (
    PrintLogRequest,
    PrintLogResponse,
    SearchResponse,
    Visitor,
    VisitorRegisterRequest,
    VisitorRegisterResponse,
    VisitorUpdateRequest,
    VisitorUpdateResponse,
)
from services import edition_store, master_store
from utils.auth import get_current_mart_desk
from utils.urn import generate_urn

# Every route in this router requires a valid mart_desk-role token —
# see utils/auth.get_current_mart_desk. An operator/master/scanner
# token gets a 403 here, same as a mart_desk token gets a 403 on
# routers/registration.py.
router = APIRouter(dependencies=[Depends(get_current_mart_desk)])


def _row_to_visitor(row: dict) -> Visitor:
    """mart_days_registrations row (already shaped by master_store's
    _mart_days_row_to_visitor_shape) -> API's Visitor model."""
    return Visitor(**row)


def _payload_to_mart_days_data(payload: dict) -> dict:
    """API's Visitor-shaped payload (name, organization, ...) -> mart_days_registrations column names."""
    return {
        "full_name": payload.get("name"),
        "company_name": payload.get("organization"),
        "designation": payload.get("designation"),
        "phone_number": payload.get("mobile"),
        "email": payload.get("email"),
        "buyer_type": payload.get("category"),
    }


def _walkin_data(payload: dict) -> dict:
    """Same as above, plus the current edition number, for brand-new walk-in rows only."""
    data = _payload_to_mart_days_data(payload)
    data["edition_number"] = edition_store.current_edition_number()
    return data


@router.get("/search", response_model=SearchResponse)
async def search_mart_days_registrants(q: str):
    """
    Realtime search over mart_days_registrations only — hit by the
    Mart Days desk frontend's search box, same behavior as the other
    desk's /api/visitors/search (URN / QR / name / mobile / company).
    """
    results = master_store.search_mart_days(q)
    return SearchResponse(query=q, results=[_row_to_visitor(r) for r in results])


@router.post("/register", response_model=VisitorRegisterResponse)
async def register_mart_days_walkin(payload: VisitorRegisterRequest):
    """
    Onsite walk-in registration AT THE MART DAYS DESK — separate from
    the public online form (routers/mart_registration.py's
    POST /api/mart-days/register), which is untouched by this route.
    No confirmation email is sent for a walk-in (that's only for the
    public online form); the operator prints the badge right here.
    `category` must be one of BUYER_TYPES — the same values the
    public form uses — so both paths into this table agree on what a
    valid buyer type is.
    """
    buyer_type = (payload.category or "").strip()
    if buyer_type not in BUYER_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of: {', '.join(BUYER_TYPES)}",
        )
    urn = generate_urn()
    row = master_store.insert_mart_days_visitor(urn, _walkin_data(payload.model_dump()))
    return VisitorRegisterResponse(visitor=_row_to_visitor(row))


@router.put("/{urn}", response_model=VisitorUpdateResponse)
async def update_mart_days_registrant(urn: str, payload: VisitorUpdateRequest):
    """
    Edits an already-registered Mart Days registrant's details
    (operator fixing a typo before printing). URN itself comes from
    the path and is never editable, same reasoning as
    routers/registration.py's /update.
    """
    row = master_store.update_mart_days_visitor(urn, _payload_to_mart_days_data(payload.model_dump()))
    if row is None:
        raise HTTPException(status_code=404, detail=f"No Mart Days registrant found with URN '{urn}'")
    return VisitorUpdateResponse(visitor=_row_to_visitor(row))


@router.post("/{urn}/print-log", response_model=PrintLogResponse)
async def log_mart_days_print(urn: str, payload: PrintLogRequest):
    """
    Called once from the Mart Days desk frontend, right after a
    browser print for this registrant has genuinely succeeded.
    Increments print_count on mart_days_registrations.
    """
    row = master_store.log_print_mart_days(urn, payload.device_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No Mart Days registrant found with URN '{urn}'")
    return PrintLogResponse(visitor=_row_to_visitor(row))