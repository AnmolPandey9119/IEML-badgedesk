"""
routers/registration.py
Search + registration + update endpoints. Backed by the local master
store (services/master_store.py) — the one SQLite file that holds
every visitor, whether they arrived via the Google Sheet sync or an
onsite walk-in registration at the counter.

The master store's internal field names (org, category, status ...)
differ slightly from the API/frontend's field names (organization,
designation ...) that were already in place — the two small helpers
below translate between them so nothing on the frontend has to
change. "designation" isn't a core master_store column, so it just
rides along in extra_json automatically and round-trips fine.

  - POST /{urn}/print-log  — any logged-in user (operator or master)
    can call this; it's what every counter calls after a real print
    succeeds.
  - DELETE /{urn}          — MASTER ONLY. Extra Depends(get_current_master)
    on top of the router-level Depends(get_current_admin) is what
    actually restricts this one route.

--------------------------------------------------------------------
CHANGED — Mart Days is now a fully separate event bucket
--------------------------------------------------------------------
Mart Days registrants live ONLY in mart_days_registrations now, never
in `visitors`. That means the SAME URN might belong to either table
— never both, since master_store.existing_urns() checks both when
minting a new one, so they can never collide.

Two different strategies handle this, depending on the endpoint:

  - GET /search takes an explicit ?event=mart_days|other query param
    (defaults to "other" for safety), because a free-text search
    genuinely needs to know WHICH table to look in — there's no URN
    yet to look up. The operator app's sticky "current event" toggle
    is what supplies this.

  - Everything else that's already keyed by a specific URN
    (print-log, scan-log, PUT update, DELETE) is "URN-smart" instead:
    it tries `visitors` first, and only falls back to
    mart_days_registrations if that URN isn't found there. Since a
    URN can only ever exist in one table, this always resolves
    correctly with zero ambiguity — the frontend doesn't need to
    pass an event flag on these calls at all, they just keep working
    exactly as before for BOTH event buckets.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from models.mart_registration import MartDaysRegisterRequest
from models.visitor import (
    DeleteVisitorResponse,
    PrintLogRequest,
    PrintLogResponse,
    ScanLogRequest,
    ScanLogResponse,
    SearchResponse,
    Visitor,
    VisitorRegisterRequest,
    VisitorRegisterResponse,
    VisitorUpdateRequest,
    VisitorUpdateResponse,
)
from services import master_store
from utils.auth import get_current_admin, get_current_master, get_current_staff
from utils.urn import generate_urn

# Every route in this router requires a valid login token — see
# utils/auth.get_current_admin. Stops outsiders from searching,
# registering, or editing visitors without logging in first.
router = APIRouter(dependencies=[Depends(get_current_admin)])


def _row_to_visitor(row: dict) -> Visitor:
    """master_store row (org, ...) -> API's Visitor shape (organization, ...)."""
    data = dict(row)
    data["organization"] = data.pop("org", None)
    return Visitor(**data)


def _payload_to_row(payload: dict) -> dict:
    """API payload (organization, ...) -> master_store's row shape (org, ...)."""
    data = dict(payload)
    data["org"] = data.pop("organization", None)
    return data


@router.get("/search", response_model=SearchResponse)
async def search_visitors(
    q: str = Query(..., min_length=1, description="URN, QR value, name, mobile, or organization"),
    event: str = Query("other", description="'mart_days' or 'other' — which table to search"),
):
    """
    Realtime visitor search — hit by the frontend's search box,
    whether the operator typed into it or a QR scanner "typed" a
    scanned URN into it (scanners act as keyboard input, so both
    land here the exact same way, no special scanner integration
    needed).

    CHANGED: now takes ?event=mart_days|other. The operator app's
    sticky "current event" toggle decides which one gets sent — this
    is what keeps the two buckets from ever mixing in search results.
    """
    if event == "mart_days":
        results = master_store.search_mart_days(q)
    else:
        results = master_store.search(q)
    return SearchResponse(query=q, results=[Visitor(**r) if event == "mart_days" else _row_to_visitor(r) for r in results])


@router.post("/register", response_model=VisitorRegisterResponse, dependencies=[Depends(get_current_staff)])
async def register_visitor(payload: VisitorRegisterRequest):
    """
    New onsite registration for any event OTHER than Mart Days.
    Assigns a fresh URN (unique across visitors AND
    mart_days_registrations combined — see utils/urn.py), saves it
    into `visitors` with source="onsite", and returns the visitor so
    the frontend can immediately trigger a badge print.
    OPERATOR/MASTER ONLY — extra Depends(get_current_staff) on top of
    the router-level Depends(get_current_admin) rejects a scanner
    token here, same pattern as the delete route's get_current_master.
    """
    urn = generate_urn()
    row = master_store.insert_visitor(urn, _payload_to_row(payload.model_dump()), source="onsite")
    return VisitorRegisterResponse(visitor=_row_to_visitor(row))


@router.post("/register-mart-days", response_model=VisitorRegisterResponse, dependencies=[Depends(get_current_staff)])
async def register_mart_days_visitor_onsite(payload: MartDaysRegisterRequest):
    """
    NEW — onsite Mart Days registration, used when the operator has
    "Mart Days" selected in the counter app. Same request shape as
    the public form (models/mart_registration.py) so the onsite form
    and the public form ask for identical fields. Writes ONLY to
    mart_days_registrations (see master_store.insert_mart_days_visitor)
    — never touches `visitors`. Returns the same Visitor-shaped
    response as /register so the frontend's print flow doesn't need
    to know or care which table this registrant actually lives in.

    Deliberately does NOT run the public form's email-confirmation
    background task — this is someone standing at the counter right
    now, about to get a physical badge printed immediately; an email
    isn't the relevant confirmation here. Also does NOT run the
    public form's duplicate check — an operator manually registering
    someone onsite is a deliberate action, not a public form that
    needs abuse protection.
    """
    urn = generate_urn()
    row = master_store.insert_mart_days_visitor(urn, payload.model_dump())
    return VisitorRegisterResponse(visitor=Visitor(**row))


@router.put("/{urn}", response_model=VisitorUpdateResponse, dependencies=[Depends(get_current_staff)])
async def update_visitor(urn: str, payload: VisitorUpdateRequest):
    """
    Edits an already-registered visitor's details (operator fixing a
    typo before printing, etc). URN itself comes from the path and
    is never editable — it's the permanent identifier already used
    as the QR value. OPERATOR/MASTER ONLY — same
    Depends(get_current_staff) reasoning as /register above.

    CHANGED: URN-smart — tries `visitors` first; if the URN isn't
    found there, it must be a Mart Days registrant, so falls back to
    mart_days_registrations. The frontend calls this exact same
    endpoint either way, no event flag needed.
    """
    row = master_store.update_visitor(urn, _payload_to_row(payload.model_dump()))
    if row is not None:
        return VisitorUpdateResponse(visitor=_row_to_visitor(row))

    mart_row = master_store.update_mart_days_visitor(urn, payload.model_dump())
    if mart_row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return VisitorUpdateResponse(visitor=Visitor(**mart_row))


@router.post("/{urn}/print-log", response_model=PrintLogResponse)
async def log_print(urn: str, payload: PrintLogRequest):
    """
    NEW. Called once from the frontend, right after a browser print
    for this visitor has genuinely succeeded — never before, never
    speculatively. Increments this visitor's print_count and records
    one row in print_log tagged with the device_name the operator
    chose at login. This is the ONLY thing that feeds the master
    console's print stats — nothing else writes to print_log.

    CHANGED: URN-smart — see update_visitor() above for the pattern.
    A Mart Days print increments mart_days_registrations.print_count
    directly (no print_log row — see master_store.log_mart_days_print
    for why); everything else still writes the full print_log entry
    exactly as before.
    """
    row = master_store.log_print(urn, payload.device_name)
    if row is not None:
        return PrintLogResponse(visitor=_row_to_visitor(row))

    mart_row = master_store.log_mart_days_print(urn, payload.device_name)
    if mart_row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return PrintLogResponse(visitor=Visitor(**mart_row))


@router.post("/{urn}/scan-log", response_model=ScanLogResponse)
async def log_scan(urn: str, payload: ScanLogRequest):
    """
    NEW. Called once from the entrance-scanning app right after a
    QR/RFID read resolves to a real visitor — never speculatively.
    Increments this visitor's scan_count and records one row in
    scan_log tagged with the scanner_name that gate chose at login.
    This is the ONLY thing that feeds the master console's Scan
    Monitoring tab — nothing else writes to scan_log. Any logged-in
    user (operator, master, OR scanner) can call this, same as
    print-log above — the router-level Depends(get_current_admin)
    already covers that.

    CHANGED: URN-smart, same pattern as log_print() above. This is
    exactly why scanning "just keeps working" for Mart Days badges
    with ZERO changes needed in the scanning app itself — it was
    never told to know or care which table a URN lives in.
    """
    row = master_store.log_scan(urn, payload.scanner_name)
    if row is not None:
        return ScanLogResponse(visitor=_row_to_visitor(row))

    mart_row = master_store.log_mart_days_scan(urn, payload.scanner_name)
    if mart_row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return ScanLogResponse(visitor=Visitor(**mart_row))


@router.delete("/{urn}", response_model=DeleteVisitorResponse, dependencies=[Depends(get_current_master)])
async def delete_visitor(urn: str):
    """
    NEW. MASTER CONSOLE ONLY. Permanently deletes a visitor record —
    their print_log history goes with it automatically. The router-
    level Depends(get_current_admin) above already confirmed "some
    valid login" before this function is even reached; the extra
    Depends(get_current_master) declared on this specific route is
    what then checks the token's role is actually "master" — a
    regular counter operator's token gets a 403 here, they never even
    see a delete option in the operator UI in the first place.

    CHANGED: URN-smart, same pattern as the routes above — tries
    deleting from `visitors` first, falls back to
    mart_days_registrations if the URN isn't found there.
    """
    deleted = master_store.delete_visitor(urn)
    if not deleted:
        deleted = master_store.delete_mart_days_visitor(urn)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return DeleteVisitorResponse(urn=urn, deleted=True)