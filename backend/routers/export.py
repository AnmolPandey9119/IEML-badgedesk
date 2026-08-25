"""
routers/export.py
Single endpoint: GET /api/export/excel
MASTER ONLY. Only the master console (frontend-admin) exposes an
Export Excel button that calls this — the operator app's own export
button/handler was removed, and this route now rejects an operator
or scanner token with a 403, same pattern as the delete-visitor route.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from services import export_service
from utils.auth import get_current_master

router = APIRouter(dependencies=[Depends(get_current_master)])


@router.get("/excel")
async def export_excel():
    """
    Builds the URN-first Excel file from every visitor currently in
    the master store (synced from the sheet + onsite registrations)
    and streams it back as a downloadable .xlsx file.
    """
    file_bytes = export_service.build_excel_bytes()
    filename = export_service.export_filename()

    return StreamingResponse(
        iter([file_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )