"""
routers/export.py
Single endpoint: GET /api/export/excel
This is what the dashboard's "Export Excel" button calls. Since the
route is login-gated (needs the Authorization header), the frontend
fetches it with the admin token attached and turns the response into
a downloadable file — same pattern used for the other authenticated
API calls in api.js, not a plain <a href> link.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from services import export_service
from utils.auth import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


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