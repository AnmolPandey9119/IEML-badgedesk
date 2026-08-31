"""
routers/external.py
NEW FILE — single endpoint the IEML portal calls to PUSH real-time
registration data into this backend:

    POST /api/external/save-data

Same shape as the reference `saveData` curl the portal team already
uses elsewhere: a plain `apiKey` header, body is a JSON array of
registration records. Deliberately NOT behind Depends(get_current_admin)
/ get_current_master — those are for OUR OWN dashboard's operator/
master logins, and this route is called by an external system that
has no such login. It's gated by its own apiKey check below instead,
against EXTERNAL_API_KEY in .env — a key we generate ourselves and
hand to the portal team, separate from ORG_API_KEY (which is for the
legacy, currently-unused, outbound org_api_client.py).
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status

from config import settings
from models.visitor import ExternalRegistrationRecord, ExternalSyncResponse
from services import external_sync

router = APIRouter()


@router.post("/save-data", response_model=ExternalSyncResponse)
async def save_data(
    records: list[ExternalRegistrationRecord],
    api_key: Optional[str] = Header(None, alias="apiKey"),
):
    """
    Upserts every record in the array by RegID (== URN). Returns a
    summary (received/created/updated/skipped_invalid) so the portal
    side can confirm the push actually landed, same spirit as
    sheet_sync's run_sync() summary that already powers "Sync Now".
    """
    if not settings.external_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EXTERNAL_API_KEY isn't configured on this server yet.",
        )
    if api_key != settings.external_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing apiKey")

    result = external_sync.run_sync([r.model_dump() for r in records])
    return ExternalSyncResponse(**result)