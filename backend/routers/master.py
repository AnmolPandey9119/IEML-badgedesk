"""
routers/master.py
NEW FILE — endpoints only the master console calls. Every route here
is gated by Depends(get_current_master) at the router level, so a
regular counter operator's token (role="operator") gets a 403 on
all of them automatically — there's no per-route repetition needed.

  - GET /api/master/visitors     -> every visitor on file, full
                                     details + how many times each
                                     one's badge has been printed.
  - GET /api/master/print-stats  -> overall print total + a
                                     breakdown by device name.

Nothing here writes anything — reads only. Add/edit/print-log/delete
all stay in routers/registration.py (add/edit/print-log are shared
with counter operators; delete is master-only but lives there next
to the other URN-keyed actions for consistency).
"""

from fastapi import APIRouter, Depends, Query

from models.visitor import (
    DeviceCount,
    MasterVisitor,
    MasterVisitorListResponse,
    PrintStatsResponse,
    RecentScanEntry,
    RecentScansResponse,
    ScannerCount,
    ScanStatsResponse,
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
    """Overall print total across every device, plus a per-device breakdown."""
    stats = master_store.print_stats()
    return PrintStatsResponse(
        overall_total=stats["overall_total"],
        by_device=[DeviceCount(**d) for d in stats["by_device"]],
    )


@router.get("/scan-stats", response_model=ScanStatsResponse)
async def get_scan_stats():
    """Overall entrance-scan total across every gate, plus a per-scanner breakdown."""
    stats = master_store.scan_stats()
    return ScanStatsResponse(
        overall_total=stats["overall_total"],
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