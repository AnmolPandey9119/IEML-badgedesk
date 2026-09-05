"""
routers/registration.py
Search + registration + update endpoints. Backed by the local master
store (services/master_store.py) — the one database that holds every
visitor, whether they arrived via the Google Sheet sync, an onsite
walk-in registration at the counter, or the external portal push
(sir's POST /api/external/save-data).

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

REVERTED (Mart Days removed): this file used to branch every route
between the regular `visitors` table and a separate
`mart_days_registrations` table (two-event support for the badge
desk). Mart Days now runs on its own separate portal, so that
branching, the `?event=` param, /register-mart-days, and the
mart_days_registrations fallbacks are all gone — every route here
goes straight to the one `visitors` table again, same as before Mart
Days was ever added.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

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
    """master_store `visitors`-table row (org, ...) -> API's Visitor shape (organization, ...)."""
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
):
    """
    Realtime visitor search — hit by the frontend's search box,
    whether the operator typed into it or a QR scanner "typed" a
    scanned URN into it (scanners act as keyboard input, so both
    land here the exact same way, no special scanner integration
    needed).
    """
    results = master_store.search(q)
    return SearchResponse(query=q, results=[_row_to_visitor(r) for r in results])


@router.post("/register", response_model=VisitorRegisterResponse, dependencies=[Depends(get_current_staff)])
async def register_visitor(payload: VisitorRegisterRequest):
    """
    New onsite registration. Assigns a fresh URN (unique across the
    whole store — see generate_urn()), saves it into the master store
    with source="onsite", and returns the visitor so the frontend can
    immediately trigger a badge print. OPERATOR/MASTER ONLY — extra
    Depends(get_current_staff) on top of the router-level
    Depends(get_current_admin) rejects a scanner token here, same
    pattern as the delete route's get_current_master.
    """
    urn = generate_urn()
    row = master_store.insert_visitor(urn, _payload_to_row(payload.model_dump()), source="onsite")
    return VisitorRegisterResponse(visitor=_row_to_visitor(row))


@router.put("/{urn}", response_model=VisitorUpdateResponse, dependencies=[Depends(get_current_staff)])
async def update_visitor(urn: str, payload: VisitorUpdateRequest):
    """
    Edits an already-registered visitor's details (operator fixing a
    typo before printing, etc). URN itself comes from the path and
    is never editable — it's the permanent identifier already used
    as the QR value. OPERATOR/MASTER ONLY — same
    Depends(get_current_staff) reasoning as /register above.
    """
    row = master_store.update_visitor(urn, _payload_to_row(payload.model_dump()))
    if row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return VisitorUpdateResponse(visitor=_row_to_visitor(row))


@router.post("/{urn}/print-log", response_model=PrintLogResponse)
async def log_print(urn: str, payload: PrintLogRequest):
    """
    Called once from the frontend, right after a browser print for
    this visitor has genuinely succeeded — never before, never
    speculatively. Increments this visitor's print_count and records
    one row in print_log tagged with the device_name (per-device
    stats).
    """
    row = master_store.log_print(urn, payload.device_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return PrintLogResponse(visitor=_row_to_visitor(row))


@router.post("/{urn}/scan-log", response_model=ScanLogResponse)
async def log_scan(urn: str, payload: ScanLogRequest):
    """
    Called once from the entrance-scanning app right after a QR/RFID
    read resolves to a real visitor — never speculatively. Increments
    this visitor's scan_count. Any logged-in user (operator, master,
    OR scanner) can call this, same as print-log above — the
    router-level Depends(get_current_admin) already covers that.
    """
    row = master_store.log_scan(urn, payload.scanner_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return ScanLogResponse(visitor=_row_to_visitor(row))


@router.delete("/{urn}", response_model=DeleteVisitorResponse, dependencies=[Depends(get_current_master)])
async def delete_visitor(urn: str):
    """
    MASTER CONSOLE ONLY. Permanently deletes a visitor record — their
    print_log history goes with it automatically. The router-level
    Depends(get_current_admin) above already confirmed "some valid
    login" before this function is even reached; the extra
    Depends(get_current_master) declared on this specific route is
    what then checks the token's role is actually "master" — a
    regular counter operator's token gets a 403 here, they never even
    see a delete option in the operator UI in the first place.
    """
    deleted = master_store.delete_visitor(urn)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No visitor found with URN '{urn}'")
    return DeleteVisitorResponse(urn=urn, deleted=True)