"""
main.py
FastAPI application entry point.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

(host/port also come from .env via config.py -- the command above
just needs to match what's in APP_HOST / APP_PORT if you override)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from services import edition_store, master_store, sheet_sync

# Without this, the root logger has no handler, so every logger.info()
# call across the app (email_service, sheet_sync, etc.) is silently
# swallowed -- only WARNING/ERROR show up via Python's default
# "last resort" stderr handler. This makes INFO logs (like
# "Confirmation email sent") visible in Render's log stream too.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("main")


async def _auto_sync_loop() -> None:
    """
    Background task: calls the exact same sync function the "Sync
    Now" button uses, every SHEET_SYNC_INTERVAL_MINUTES. Runs for
    the lifetime of the server. Any single failed sync (sheet
    temporarily unreachable, etc.) is logged and skipped -- it just
    tries again on the next interval, never crashes the server.
    """
    interval_seconds = max(settings.sheet_sync_interval_minutes, 1) * 60
    while True:
        if settings.sheet_sync_enabled:
            try:
                summary = await sheet_sync.run_sync()
                logger.info("Auto-sync: %s", summary)
            except Exception:
                logger.exception("Auto-sync failed, will retry next interval")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    master_store.init_db()
    # Mart Days-only settings table. Wrapped so a problem here can NEVER stop the
    # backend from starting -- the normal IEML BadgeDesk shares this server.
    try:
        edition_store.init_table()
    except Exception:
        logger.exception("Mart Days edition table setup failed -- Mart Days will use built-in defaults")
    sync_task = asyncio.create_task(_auto_sync_loop())

    yield

    # ---- shutdown ----
    sync_task.cancel()


app = FastAPI(
    title="IEML BadgeDesk API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allows the frontend (served from a different origin -- the
# custom domain's frontend, or a counter laptop) to call this API.
# Origins list comes from .env, never hardcoded here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Simple liveness check used by the frontend's topbar to show Online/Offline."""
    return {
        "status": "ok",
        "event": settings.event_name,
        "sheet_sync_enabled": settings.sheet_sync_enabled,
        "visitor_count": master_store.count(),
    }


# ----------------------------------------------------------------
# Routers
# ----------------------------------------------------------------
# NOTE: auth router stays PUBLIC (no login required to reach /login
# itself, obviously). Every other router is login-gated via
# Depends(get_current_admin) declared inside each router file.
# `master` is its own -- its own routes are gated further, down
# to Depends(get_current_master), declared inside routers/master.py.
#
# mart_registration -- the public /api/mart-days/register and
# /api/mart-days/badge-download endpoints. Still live in production.
# `external` stays too -- that's the POST /api/external/save-data
# push endpoint.
#
# `mart_desk` -- the NEW separate onsite Mart Days registration +
# print desk (its own login, role="mart_desk", reads/writes the
# mart_days_registrations table). Added in this commit alongside
# routers/mart_desk.py -- must be included here or its routes
# (/api/mart-desk/...) 404 even though the router file exists.
from routers import (  # noqa: E402
    auth,
    export,
    external,
    mart_desk,
    mart_edition,
    mart_registration,
    master,
    registration,
    sync,
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(registration.router, prefix="/api/visitors", tags=["visitors"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(master.router, prefix="/api/master", tags=["master"])
app.include_router(external.router, prefix="/api/external", tags=["external"])
app.include_router(mart_registration.router, prefix="/api/mart-days", tags=["mart-days"])
app.include_router(mart_desk.router, prefix="/api/mart-desk", tags=["mart-desk"])
app.include_router(mart_edition.router, prefix="/api/mart-edition", tags=["mart-edition"])