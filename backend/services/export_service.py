"""
services/export_service.py
Builds the downloadable Excel file the manager uses to get URNs and
send them to registrants. URN is always the first column, followed
by the core visitor fields, followed by any extra columns the sheet
happened to have (so nothing ever silently gets left out even if the
real spreadsheet later has more columns than name/org/city/category/
status/email/mobile).

Built fresh from services/master_store.py every time it's requested
(GET /api/export/excel) — always reflects whatever has been synced
in / registered onsite up to that exact moment. Nothing is cached.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from services import master_store

# Core columns always shown in this fixed order, URN always first.
_CORE_COLUMNS = ["urn", "name", "org", "city", "category", "status", "email", "mobile"]

_HEADER_LABELS = {
    "urn": "URN",
    "name": "Name",
    "org": "Organization",
    "city": "City",
    "category": "Category",
    "status": "Status",
    "email": "Email",
    "mobile": "Mobile",
}


def _collect_extra_columns(visitors: list[dict]) -> list[str]:
    """Any keys beyond the core columns (e.g. new sheet columns added later), sorted for a stable column order."""
    extra_keys: set[str] = set()
    for visitor in visitors:
        extra_keys.update(k for k in visitor.keys() if k not in _CORE_COLUMNS)
    return sorted(extra_keys)


def build_excel_bytes() -> bytes:
    """Returns the finished .xlsx file as raw bytes, ready to stream as a download."""
    visitors = master_store.get_all()
    extra_columns = _collect_extra_columns(visitors)
    columns = _CORE_COLUMNS + extra_columns

    wb = Workbook()
    ws = wb.active
    ws.title = "Visitors"

    # ---- header row ----
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    for col_idx, key in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=_HEADER_LABELS.get(key, key))
        cell.font = header_font
        cell.fill = header_fill

    # ---- data rows ----
    for row_idx, visitor in enumerate(visitors, start=2):
        for col_idx, key in enumerate(columns, start=1):
            ws.cell(row=row_idx, column=col_idx, value=visitor.get(key, ""))

    # ---- column widths (rough auto-fit based on content length) ----
    for col_idx, key in enumerate(columns, start=1):
        header_len = len(_HEADER_LABELS.get(key, key))
        max_content_len = max(
            (len(str(v.get(key, ""))) for v in visitors), default=0
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(header_len, max_content_len) + 4, 45
        )

    ws.freeze_panes = "A2"  # keep header visible while scrolling

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_filename() -> str:
    """e.g. 'ieml-visitors-2026-08-18-1432.xlsx' — unique per export, so re-downloads never overwrite each other."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    return f"ieml-visitors-{timestamp}.xlsx"