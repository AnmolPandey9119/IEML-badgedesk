"""
routers/sync.py
Single endpoint: POST /api/sync/run
This is what the dashboard's "Sync Now" button calls. It runs the
exact same services/sheet_sync.run_sync() function the background
auto-sync loop (main.py) calls every SHEET_SYNC_INTERVAL_MINUTES —
so manual and automatic sync always behave identically, no separate
code path to keep in sync (pun intended).
"""

from fastapi import APIRouter, Depends, HTTPException

from services import sheet_sync
from utils.auth import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.post("/run")
async def run_sync():
    """
    Fetches the Google Sheet right now, saves any new registrants
    into the master store with a fresh URN, and returns a small
    summary: how many rows were fetched, how many were genuinely
    new, how many were already-synced (skipped).
    """
    try:
        summary = await sheet_sync.run_sync()
    except RuntimeError as exc:
        # Raised when GOOGLE_SHEET_URL isn't set in .env yet.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from exc

    return summary