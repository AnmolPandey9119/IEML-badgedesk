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

NEW in this file (master console update):
  - POST /{urn}/print-log  — any logged-in user (operator or master)
    can call this; it's what every counter calls after a real print
    succeeds.
  - DELETE /{urn}          — MASTER ONLY. Extra Depends(get_current_master)
    on top of the router-level Depends(get_current_admin) is what
    actually restricts this one route.

FIXED (Mart Days separation for the badge desk / counter app):
Every route below now knows there are TWO tables a URN can live in —
`visitors` (Other Events) and `mart_days_registrations` (Mart Days).
The service layer for the Mart Days side (search_mart_days,
insert_mart_days_visitor, update_mart_days_visitor, log_mart_days_print,
log_mart_days_scan, delete_mart_days_visitor) already existed in
services/master_store.py — this file just never called into it. That
was the whole bug: the counter's EventGate correctly switched the UI
into "Mart Days" mode and correctly sent `?event=mart_days` / called
`registerMartDaysVisitor()`, but every one of those calls landed on
plain `visitors`-table functions here, so Mart Days walk-ins were
either invisible in search, saved into the wrong table, or 404'd on
print/edit/delete. Nothing about the ALREADY-WORKING Other Events
flow changes — that code path is untouched, same functions, same
behaviour.

  - GET /search now takes ?event=other|mart_days (defaults to
    "other" so anything that doesn't send it — e.g. an old cached
    frontend build — keeps working exactly as before).
  - POST /register-mart-days is NEW — this is the endpoint api.js's
    registerMartDaysVisitor() has been calling all along; it simply
    didn't exist on the backend before.
  - PUT /{urn}, POST /{urn}/print-log, POST /{urn}/scan-log, and
    DELETE /{urn} now try the `visitors` table first and fall back to
    `mart_days_registrations` if the URN isn't found there. A URN is
    globally unique across both tables (see master_store.get_all_urns()),
    so this fallback can never accidentally match the wrong record —
    it just means the frontend (counter AND master console, which
    calls these same shared routes for its Mart Days tab) never has
    to tell the backend which table to look in.
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
from typing import Optional

from services import master_store
from utils.auth import get_current_admin, get_current_master, get_current_operator_event, get_current_staff
from utils.urn import generate_urn

# Every route in this router requires a valid login token — see
# utils/auth.get_current_admin. Stops outsiders from searching,
# registering, or editing visitors without logging in first.
router = APIRouter(dependencies=[Depends(get_current_admin)])


def _row_to_visitor(row: dict) -> Visitor:
    """master_store `visitors`-table row (org, ...) -> API's Visitor shape (organization, ...)."""
    data = dict(row)
    data["organization"] = data.pop("org", None)
    return Visitor(**data)


def _mart_row_to_visitor(row: dict) -> Visitor:
    """
    master_store's Mart Days helpers (search_mart_days, insert_mart_days_visitor,
    update_mart_days_visitor, log_mart_days_print, log_mart_days_scan) already
    return dicts in Visitor shape via _mart_days_row_to_visitor_shape() — no
    org/organization translation needed here, unlike _row_to_visitor above.
    """
    return Visitor(**row)


def _payload_to_row(payload: dict) -> dict:
    """API payload (organization, ...) -> master_store's row shape (org, ...)."""
    data = dict(payload)
    data["org"] = data.pop("organization", None)
    return data


@router.get("/search", response_model=SearchResponse)
async def search_visitors(
    q: str = Query(..., min_length=1, description="URN, QR value, name, mobile, or organization"),
    event: str = Query("other", description="'other' searches the regular visitors table, 'mart_days' searches Mart Days registrants only"),
    event_claim: Optional[str] = Depends(get_current_operator_event),
):
    """
    Realtime visitor search — hit by the frontend's search box,
    whether the operator typed into it or a QR scanner "typed" a
    scanned URN into it (scanners act as keyboard input, so both
    land here the exact same way, no special scanner integration
    needed).

    FIXED: `event` now actually does something. Previously this param
    was sent by the frontend but silently ignored here, so Mart Days
    mode still searched the regular `visitors` table (and missed
    every Mart Days registrant, sheet-synced or onsite). Now it
    genuinely scopes the query to the right table.

    `event_claim` (NEW) takes priority when present: the badge desk's
    two operator logins (Other Events / Mart Days) each bake their
    event straight into the JWT at login, so for those tokens the
    backend trusts the TOKEN over whatever `?event=` the frontend
    sent — a badge desk operator can never end up searching the other
    event's data no matter what the client sends. Master/scanner
    tokens carry no event claim, so they fall through to the `event`
    query param exactly as before (this is how the master console's
    Mart Days tab keeps working — it explicitly passes ?event=mart_days
    per call since one master login covers both events).
    """
    effective_event = event_claim or event

    if effective_event == "mart_days":
        results = master_store.search_mart_days(q)
        return SearchResponse(query=q, results=[_mart_row_to_visitor(r) for r in results])

    results = master_store.search(q)
    return SearchResponse(query=q, results=[_row_to_visitor(r) for r in results])


@router.post("/register", response_model=VisitorRegisterResponse, dependencies=[Depends(get_current_staff)])
async def register_visitor(
    payload: VisitorRegisterRequest,
    event_claim: Optional[str] = Depends(get_current_operator_event),
):
    """
    New onsite registration for any event OTHER than Mart Days.
    Assigns a fresh URN (unique across the whole store — sheet-synced,
    onsite, or Mart Days, doesn't matter — see generate_urn()), saves
    it into the master store with source="onsite", and returns the
    visitor so the frontend can immediately trigger a badge print.
    OPERATOR/MASTER ONLY — extra Depends(get_current_staff) on top of
    the router-level Depends(get_current_admin) rejects a scanner
    token here, same pattern as the delete route's get_current_master.

    NEW: a badge desk operator logged in on the Mart Days account
    (event_claim == "mart_days") is rejected here with 403 — that
    operator's token is only supposed to reach /register-mart-days.
    Master tokens carry no event_claim, so this never affects the
    master console.
    """
    if event_claim == "mart_days":
        raise HTTPException(
            status_code=403,
            detail="This login is scoped to Mart Days — use the Mart Days registration form.",
        )
    urn = generate_urn()
    row = master_store.insert_visitor(urn, _payload_to_row(payload.model_dump()), source="onsite")
    return VisitorRegisterResponse(visitor=_row_to_visitor(row))


@router.post("/register-mart-days", response_model=VisitorRegisterResponse, dependencies=[Depends(get_current_staff)])
async def register_mart_days_visitor_onsite(
    payload: MartDaysRegisterRequest,
    event_claim: Optional[str] = Depends(get_current_operator_event),
):
    """
    NEW. New onsite Mart Days registration — used only when the
    counter (or master console) is in Mart Days mode. This is the
    endpoint the frontend's API.registerMartDaysVisitor() has been
    pointed at from day one; it simply never existed here before,
    which was the actual bug the operator was hitting.

    Writes ONLY to mart_days_registrations (via
    master_store.insert_mart_days_visitor) — never to the regular
    visitors table, so Mart Days walk-ins can never get mixed into
    Other Events data. Same duplicate-email/duplicate-mobile guard as
    the public Mart Days form (routers/mart_registration.py), so the
    counter can't accidentally create two badges for the same person.
    OPERATOR/MASTER ONLY, same reasoning as /register above.

    NEW: mirror check of /register above — a badge desk operator
    logged in on the regular Other Events account (event_claim ==
    "other") is rejected here with 403.
    """
    if event_claim == "other":
        raise HTTPException(
            status_code=403,
            detail="This login is scoped to Other Events — Mart Days registration isn't available here.",
        )

    existing = master_store.find_mart_days_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This email is already registered for Mart Days (URN: {existing['urn']}).",
        )

    existing = master_store.find_mart_days_by_mobile(payload.phone_number)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This phone number is already registered for Mart Days (URN: {existing['urn']}).",
        )

    urn = generate_urn()
    row = master_store.insert_mart_days_visitor(urn, payload.model_dump())
    return VisitorRegisterResponse(visitor=_mart_row_to_visitor(row))


@router.put("/{urn}", response_model=VisitorUpdateResponse, dependencies=[Depends(get_current_staff)])
async def update_visitor(urn: str, payload: VisitorUpdateRequest):
    """
    Edits an already-registered visitor's details (operator fixing a
    typo before printing, etc). URN itself comes from the path and
    is never editable — it's the permanent identifier already used
    as the QR value. OPERATOR/MASTER ONLY — same
    Depends(get_current_staff) reasoning as /register above.

    FIXED: tries the regular `visitors` table first, then falls back
    to `mart_days_registrations` if the URN lives there instead — so
    editing a Mart Days registrant (from the counter or the master
    console) no longer 404s.
    """
    row = master_store.update_visitor(urn, _payload_to_row(payload.model_dump()))
    if row is not None:
        return VisitorUpdateResponse(visitor=_row_to_visitor(row))

    row = master_store.update_mart_days_visitor(urn, payload.model_dump())
    if row is not None:
        return VisitorUpdateResponse(visitor=_mart_row_to_visitor(row))

    raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")


@router.post("/{urn}/print-log", response_model=PrintLogResponse)
async def log_print(urn: str, payload: PrintLogRequest):
    """
    NEW. Called once from the frontend, right after a browser print
    for this visitor has genuinely succeeded — never before, never
    speculatively. Increments this visitor's print_count. For Other
    Events this also records one row in print_log tagged with the
    device_name (per-device stats); Mart Days keeps just the running
    total on the row itself, by design (see master_store.log_mart_days_print).

    FIXED: tries `visitors` first, falls back to
    `mart_days_registrations` — a Mart Days badge print used to 404
    here every single time.
    """
    row = master_store.log_print(urn, payload.device_name)
    if row is not None:
        return PrintLogResponse(visitor=_row_to_visitor(row))

    row = master_store.log_mart_days_print(urn, payload.device_name)
    if row is not None:
        return PrintLogResponse(visitor=_mart_row_to_visitor(row))

    raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")


@router.post("/{urn}/scan-log", response_model=ScanLogResponse)
async def log_scan(urn: str, payload: ScanLogRequest):
    """
    NEW. Called once from the entrance-scanning app right after a
    QR/RFID read resolves to a real visitor — never speculatively.
    Increments this visitor's scan_count. Any logged-in user
    (operator, master, OR scanner) can call this, same as print-log
    above — the router-level Depends(get_current_admin) already
    covers that.

    FIXED: tries `visitors` first, falls back to
    `mart_days_registrations` — so a Mart Days badge scanned at the
    gate is recognized too, not just Other Events badges.
    """
    row = master_store.log_scan(urn, payload.scanner_name)
    if row is not None:
        return ScanLogResponse(visitor=_row_to_visitor(row))

    row = master_store.log_mart_days_scan(urn, payload.scanner_name)
    if row is not None:
        return ScanLogResponse(visitor=_mart_row_to_visitor(row))

    raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")


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

    FIXED: tries `visitors` first, falls back to
    `mart_days_registrations` — the master console's Mart Days tab
    calls this exact same shared route to delete a registrant, which
    used to 404 every time.
    """
    deleted = master_store.delete_visitor(urn)
    if not deleted:
        deleted = master_store.delete_mart_days_visitor(urn)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return DeleteVisitorResponse(urn=urn, deleted=True)