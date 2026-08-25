"""
models/visitor.py
Pydantic schemas — the shape of every visitor-related request/response
this API handles. Routers always accept/return these, never raw dicts,
so the frontend's expectations and the backend's actual behavior
can't silently drift apart.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class VisitorCategory:
    VISITOR = "visitor"
    EXHIBITOR = "exhibitor"
    DELEGATE = "delegate"
    MEDIA = "media"
    VIP = "vip"


class Visitor(BaseModel):
    """A visitor record as returned by search / registration / update."""
    urn: str = Field(..., description="Unique registration number, printed as QR + text on the badge")
    name: str
    organization: Optional[str] = None
    designation: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    category: Optional[str] = "visitor"
    # NEW — total times this visitor's badge has been printed, across
    # every counter combined. Optional/defaulted so nothing existing
    # that builds a Visitor without this field breaks.
    print_count: Optional[int] = 0
    # NEW — total times this visitor has been scanned at entry gates,
    # across every scanner combined. Same optional/defaulted pattern.
    scan_count: Optional[int] = 0
    # NEW — timestamp of this visitor's most recent entry-gate scan.
    # None until their first scan.
    last_scanned_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    """Returned by GET /api/visitors/search"""
    query: str
    results: list[Visitor] = Field(default_factory=list)


class VisitorRegisterRequest(BaseModel):
    """Body for POST /api/visitors/register — new onsite registration."""
    name: str = Field(..., min_length=1)
    organization: str = Field(..., min_length=1)
    designation: Optional[str] = None
    mobile: str = Field(..., min_length=6)
    email: Optional[str] = None
    category: Optional[str] = "visitor"


class VisitorRegisterResponse(BaseModel):
    """Returned by POST /api/visitors/register — includes the newly assigned URN."""
    visitor: Visitor


class VisitorUpdateRequest(BaseModel):
    """
    Body for PUT /api/visitors/{urn} — editing an already-registered
    visitor's details (e.g. operator fixes a typo'd name/mobile before
    printing). URN itself is NEVER editable — it's the permanent
    identifier already printed as the QR value, so it's taken from
    the URL path, not from this body.
    """
    name: str = Field(..., min_length=1)
    organization: str = Field(..., min_length=1)
    designation: Optional[str] = None
    mobile: str = Field(..., min_length=6)
    email: Optional[str] = None
    category: Optional[str] = "visitor"


class VisitorUpdateResponse(BaseModel):
    """Returned by PUT /api/visitors/{urn} — the updated visitor record."""
    visitor: Visitor


# ----------------------------------------------------------------
# NEW — print logging (used by every counter, not master-only)
# ----------------------------------------------------------------

class PrintLogRequest(BaseModel):
    """
    Body for POST /api/visitors/{urn}/print-log — sent once from the
    frontend right after a browser print genuinely succeeds.
    device_name is whatever the operator named their counter/laptop
    at login (e.g. "Counter 1") — that's what the master console's
    per-device stats group by.
    """
    device_name: str = Field(..., min_length=1)


class PrintLogResponse(BaseModel):
    """Returned by POST /api/visitors/{urn}/print-log — the visitor with updated print_count."""
    visitor: Visitor


# ----------------------------------------------------------------
# NEW — scan logging (used by the entrance-scanning app)
# ----------------------------------------------------------------

class ScanLogRequest(BaseModel):
    """
    Body for POST /api/visitors/{urn}/scan-log — sent once from the
    scanning app right after a QR/RFID scan is read at an entry gate.
    scanner_name is whatever that gate's device was named at login
    (e.g. "Gate 1") — that's what the master console's per-scanner
    stats group by. Mirrors PrintLogRequest exactly, just named for
    scanning instead of printing so the two are never confused.
    """
    scanner_name: str = Field(..., min_length=1)


class ScanLogResponse(BaseModel):
    """Returned by POST /api/visitors/{urn}/scan-log — the visitor with updated scan_count."""
    visitor: Visitor


# ----------------------------------------------------------------
# NEW — master console only (all gated by get_current_master)
# ----------------------------------------------------------------

class DeleteVisitorResponse(BaseModel):
    """Returned by DELETE /api/visitors/{urn}"""
    urn: str
    deleted: bool


class MasterVisitor(BaseModel):
    """
    Full visitor record for the master console. Unlike the regular
    Visitor model above, this one allows extra fields to pass through
    as-is (model_config extra="allow") — the master console is meant
    to show EVERY detail on file for a person (city, status, and any
    future sheet columns), not just the fixed set the counter UI
    cares about.
    """
    model_config = ConfigDict(extra="allow")

    urn: str
    name: str
    organization: Optional[str] = None
    print_count: int = 0
    scan_count: int = 0
    last_scanned_at: Optional[datetime] = None


class MasterVisitorListResponse(BaseModel):
    """Returned by GET /api/master/visitors — every visitor on file, full details + print counts."""
    visitors: list[MasterVisitor] = Field(default_factory=list)
    total: int


class DeviceCount(BaseModel):
    device_name: str
    count: int


class PrintStatsResponse(BaseModel):
    """Returned by GET /api/master/print-stats"""
    overall_total: int
    by_device: list[DeviceCount] = Field(default_factory=list)


class ScannerCount(BaseModel):
    scanner_name: str
    count: int


class ScanStatsResponse(BaseModel):
    """Returned by GET /api/master/scan-stats"""
    overall_total: int
    by_scanner: list[ScannerCount] = Field(default_factory=list)


class RecentScanEntry(BaseModel):
    """
    One row in the master console's live Scan Monitoring feed — a
    single scan_log entry joined with that visitor's current details,
    so the frontend can render "who / where / when" without a second
    lookup per row.
    """
    id: int
    urn: str
    name: str
    organization: Optional[str] = None
    category: Optional[str] = None
    scanner_name: str
    scanned_at: datetime


class RecentScansResponse(BaseModel):
    """Returned by GET /api/master/recent-scans"""
    scans: list[RecentScanEntry] = Field(default_factory=list)