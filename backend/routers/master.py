"""
routers/master.py
NEW FILE — endpoints only the master console calls. Every route here
is gated by Depends(get_current_master) at the router level, so a
regular counter operator's token (role="operator") gets a 403 on
all of them automatically — there's no per-route repetition needed.

  - GET /api/master/visitors     -> every visitor on file, full
                                     details + how many times each
                                     one's badge has been printed.
  - GET /api/master/print-stats  -> overall + unique print totals +
                                     a breakdown by device name.
  - GET /api/master/scan-stats   -> overall + unique scan totals +
                                     a breakdown by scanner/gate name.
  - GET /api/master/recent-scans -> live feed of recent entrance scans.
  - GET /api/master/unscanned    -> NEW: visitors printed but never
                                     scanned at any gate.
  - POST /api/master/clear-history -> NEW: end-of-event reset — wipes
                                     print/scan history + counts only,
                                     never touches visitor records.

Add/edit/print-log all stay in routers/registration.py (shared with
counter operators); delete and clear-history are master-only writes
that live here since they're master-console-only actions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from models.visitor import (
    ClearHistoryRequest,
    ClearHistoryResponse,
    DeviceCount,
    MartDaysHomeStatsResponse,
    MartDaysVisitor,
    MartDaysVisitorListResponse,
    MasterVisitor,
    MasterVisitorListResponse,
    PrintStatsResponse,
    PurgeAllRequest,
    PurgeAllResponse,
    RecentScanEntry,
    RecentScansResponse,
    ScannerCount,
    ScanStatsResponse,
    UnscannedEntry,
    UnscannedListResponse,
    _PURGE_CONFIRM_PHRASE,
)
from services import master_store
from utils.auth import get_current_master

router = APIRouter(dependencies=[Depends(get_current_master)])


def _row_to_master_visitor(row: dict) -> MasterVisitor:
    """
    Same org -> organization rename used everywhere else in this API,
    for consistency. Everything beyond the named fields (city, status,
    and any future sheet columns) rides along automatically since
    MasterVisitor allows extra fields.
    """
    data = dict(row)
    data["organization"] = data.pop("org", None)
    return MasterVisitor(**data)


@router.get("/visitors", response_model=MasterVisitorListResponse)
async def list_all_visitors():
    """
    Every visitor currently in the master store, full details, most
    recently added first isn't required here — master_store.get_all()
    returns oldest-first, which is fine for an admin table view (the
    frontend can sort/filter client-side).
    """
    rows = master_store.get_all()
    visitors = [_row_to_master_visitor(r) for r in rows]
    return MasterVisitorListResponse(visitors=visitors, total=len(visitors))


@router.get("/print-stats", response_model=PrintStatsResponse)
async def get_print_stats():
    """Overall + unique print totals across every device, plus a per-device breakdown."""
    stats = master_store.print_stats()
    return PrintStatsResponse(
        overall_total=stats["overall_total"],
        unique_total=stats["unique_total"],
        by_device=[DeviceCount(**d) for d in stats["by_device"]],
    )


@router.get("/scan-stats", response_model=ScanStatsResponse)
async def get_scan_stats():
    """Overall + unique entrance-scan totals across every gate, plus a per-scanner breakdown."""
    stats = master_store.scan_stats()
    return ScanStatsResponse(
        overall_total=stats["overall_total"],
        unique_total=stats["unique_total"],
        by_scanner=[ScannerCount(**s) for s in stats["by_scanner"]],
    )


@router.get("/recent-scans", response_model=RecentScansResponse)
async def get_recent_scans(limit: int = Query(100, ge=1, le=500)):
    """
    NEW. Most recent entrance-gate scans, newest first, each with the
    visitor's current name/organization/category — this is what the
    master console's Scan Monitoring tab polls to show scans as they
    happen. Default 100 rows is plenty for a live feed; capped at 500
    so a runaway poll interval can never pull the whole table.
    """
    rows = master_store.recent_scans(limit=limit)
    return RecentScansResponse(scans=[RecentScanEntry(**row) for row in rows])


@router.get("/unscanned", response_model=UnscannedListResponse)
async def get_unscanned_entries(limit: int = Query(5000, ge=1, le=20000)):
    """
    NEW. Powers the master console's "Unscanned Entries" tab —
    visitors whose badge was printed at least once but who were never
    scanned at any entrance gate. Read-only, same pattern as
    get_recent_scans() above.
    """
    rows = master_store.unscanned_entries(limit=limit)
    entries = [UnscannedEntry(**row) for row in rows]
    return UnscannedListResponse(entries=entries, total=len(entries))


@router.get("/mart-days/visitors", response_model=MartDaysVisitorListResponse)
async def list_mart_days_visitors():
    """
    NEW — powers the master console's Mart Days Home tab table. Every
    Mart Days registrant on file (public form + onsite alike), full
    details, oldest-first — same read-only style as list_all_visitors()
    above, just pointed at mart_days_registrations instead.
    """
    rows = master_store.get_all_mart_days()
    visitors = [MartDaysVisitor(**r) for r in rows]
    return MartDaysVisitorListResponse(visitors=visitors, total=len(visitors))


@router.get("/mart-days/stats", response_model=MartDaysHomeStatsResponse)
async def get_mart_days_stats():
    """NEW — the two stat cards (Total Registered, Total Prints) on the master console's Mart Days Home tab."""
    stats = master_store.mart_days_home_stats()
    return MartDaysHomeStatsResponse(**stats)


@router.post("/clear-history", response_model=ClearHistoryResponse)
async def clear_history(body: ClearHistoryRequest):
    """
    NEW. End-of-event reset — wipes print/scan counters ready for the
    next event. CHANGED: now scope-aware — body.scope picks which
    event's counters get reset ("mart_days", "other_events", or
    "both"; see master_store.clear_history() for exactly what each
    scope does and does not affect). Visitor/registration identity
    records (name/URN/org/etc.) are never touched by any scope.
    Gated by get_current_master like every route in this router — a
    counter operator's token can never reach this.
    """
    result = master_store.clear_history(scope=body.scope)
    return ClearHistoryResponse(**result)


@router.post("/purge-all", response_model=PurgeAllResponse)
async def purge_all(body: PurgeAllRequest):
    """
    NEW. Full database wipe — deletes EVERY visitor row (their
    print_log/scan_log go with them automatically). Unlike
    clear_history() above, this also removes visitor identity itself
    (name/URN/org/etc.) — a true "start completely fresh" reset for
    a brand new event.

    Requires body {"confirm_phrase": "DELETE EVERYTHING"} — exact,
    case-sensitive match — or this returns 400 and deletes nothing.
    This is a SECOND gate, purely server-side, on top of whatever the
    master console's own hidden-unlock + typed-confirmation UI
    already requires before it even shows this button. Already
    master-only via this router's Depends(get_current_master).
    """
    if body.confirm_phrase != _PURGE_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Send {{"confirm_phrase": "{_PURGE_CONFIRM_PHRASE}"}} to confirm — this permanently deletes ALL data and cannot be undone.',
        )
    result = master_store.purge_everything(scope=body.scope)
    return PurgeAllResponse(**result)