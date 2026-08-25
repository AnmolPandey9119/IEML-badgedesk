"""
services/sheet_sync.py
Pulls new registrants in from the Google Sheet and saves them into
the local master store (services/master_store.py) with a freshly
assigned URN — but ONLY the truly new ones.

How it stays "realtime" without any Google API key / service account:
  - GOOGLE_SHEET_URL (config.py -> settings.google_sheet_csv_url)
    is converted to the sheet's plain CSV export link.
  - As long as the sheet is shared "Anyone with the link: Viewer",
    a normal HTTP GET returns the current data as CSV — no auth.

--------------------------------------------------------------------
WHY A ROW IS "NEW" (fixed: URN must never change once assigned)
--------------------------------------------------------------------
A row's exact content is hashed (source_hash) purely as a fast path
to skip rows that are byte-for-byte identical to what we already
have — nothing to do this run.

But WHETHER SOMEONE ALREADY HAS A URN is decided separately, by the
row's POSITION in the sheet (row 2, 3, 4, ... — a Google Form-linked
sheet only ever appends new responses at the bottom, so a row's
position never changes once it exists). This is what actually fixes
the bug:

  - This row position already has a URN -> we NEVER generate a new
    one for it. If the row's content changed (status, city, a fixed
    typo, etc.) we just refresh the stored details — URN stays
    exactly as it was, so it keeps matching what was already sent
    out on WhatsApp.
  - Row position never seen before -> genuinely new registrant,
    appended since the last sync. Only now do we call generate_urn()
    and create a new record.

Called from two places:
  - routers/sync.py  -> the dashboard's "Sync Now" button (on demand)
  - main.py           -> a background task that calls this every
                         SHEET_SYNC_INTERVAL_MINUTES automatically
Both call the exact same function, so manual and auto sync always
behave identically.
"""

import csv
import hashlib
import io
import logging

import httpx

from config import settings
from services import master_store
from utils.urn import generate_urn

logger = logging.getLogger("sheet_sync")

# Sheet column headers (case-insensitive, spaces/underscores ignored)
# mapped to our core master_store fields. Add more aliases here any
# time the real sheet uses a slightly different header name — no
# other code needs to change.
_HEADER_ALIASES = {
    "name": "name",
    "fullname": "name",
    "org": "org",
    "organisation": "org",
    "organization": "org",
    "company": "org",
    "companyname": "org",       # "Company Name" column
    "city": "city",
    "category": "category",
    "typeofbuyer": "category",  # "Type of Buyer" column — this sheet's visitor category
    "designation": "designation",
    "status": "status",
    "email": "email",
    "emailid": "email",
    "emailaddress": "email",
    "mobile": "mobile",
    "mobileno": "mobile",
    "mobilenumber": "mobile",
    "phone": "mobile",
    "phonenumber": "mobile",
    "contact": "mobile",
    "contactnumber": "mobile",
}


def _normalize_header(header: str) -> str:
    return "".join(ch for ch in header.strip().lower() if ch.isalnum())


def _map_row(raw_row: dict) -> dict:
    """
    Converts a raw CSV row (original sheet header names -> values)
    into our normalized field names. Any sheet column that doesn't
    match a known alias is kept as-is (original header) so it lands
    in extra_json in the master store — nothing from the sheet is
    ever silently dropped.
    """
    mapped: dict = {}
    for raw_header, value in raw_row.items():
        if raw_header is None:
            continue
        key = _HEADER_ALIASES.get(_normalize_header(raw_header))
        if key:
            mapped[key] = (value or "").strip()
        else:
            mapped[raw_header.strip()] = (value or "").strip()
    return mapped


def _row_hash(raw_row: dict) -> str:
    """Stable hash of a row's exact contents — used only to skip rows that are unchanged since last sync."""
    canonical = "|".join(f"{k}={v}" for k, v in sorted(raw_row.items()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_blank_row(raw_row: dict) -> bool:
    return not any((v or "").strip() for v in raw_row.values())


async def fetch_sheet_rows() -> list[dict]:
    """Downloads the sheet's current contents as a list of raw {header: value} dicts."""
    csv_url = settings.google_sheet_csv_url
    if not csv_url:
        raise RuntimeError(
            "GOOGLE_SHEET_URL isn't set in .env yet — paste the sheet link "
            "before running a sync."
        )

    # Google's CSV export URL responds with a 307 redirect to the
    # actual file location (a googleusercontent.com URL) — without
    # follow_redirects=True, httpx raises instead of following it.
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(csv_url)
        resp.raise_for_status()
        resp.encoding = "utf-8"

    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


async def run_sync() -> dict:
    """
    Fetches the sheet and, for each row:
      - skips it if nothing changed since last sync (source_hash match)
      - if this row position already has a URN, refreshes that
        visitor's details WITHOUT touching their URN
      - only if this row position has genuinely never been seen
        before does it assign a new URN
    Returns a small summary dict used by the "Sync Now" endpoint and
    logged by the background job.

    "unchanged" (already synced, nothing new) is the normal, expected
    bucket on any re-sync — it's not a problem. "blank" rows (a fully
    empty spacer row) are the only rows genuinely skipped entirely.
    "no_name" is NOT a skip — those rows still get a URN, just with a
    fallback name (their email/mobile/org, or "Unnamed Visitor") since
    every submitted row should end up registered.
    """
    if not settings.sheet_sync_enabled:
        return {"enabled": False, "fetched": 0, "new": 0, "updated": 0, "unchanged": 0, "blank": 0, "no_name": 0}

    raw_rows = await fetch_sheet_rows()
    already_synced_hashes = master_store.existing_source_hashes()
    urn_by_row = master_store.existing_urns_by_sheet_row()

    new_count = 0
    updated_count = 0
    unchanged_count = 0
    blank_count = 0
    no_name_count = 0

    for row_num, raw_row in enumerate(raw_rows, start=2):  # +2: header is row 1, data starts row 2
        if _is_blank_row(raw_row):
            blank_count += 1
            continue

        mapped = _map_row(raw_row)
        if not mapped.get("name"):
            # No name given — still register them (everyone who submitted
            # a row gets a URN), just fall back to whatever identifying
            # info IS present so they're not a blank row on the dashboard.
            fallback = mapped.get("email") or mapped.get("mobile") or mapped.get("org")
            mapped["name"] = fallback or "Unnamed Visitor"
            logger.info("Sheet row %d has no Full Name — using fallback '%s'.", row_num, mapped["name"])
            no_name_count += 1

        row_hash = _row_hash(raw_row)
        existing_urn = urn_by_row.get(row_num)

        if existing_urn:
            # This row position already has a URN — it must NEVER change here.
            if row_hash in already_synced_hashes:
                unchanged_count += 1
                continue
            # Something else about them changed on the sheet (status,
            # city, a corrected spelling, etc.) — refresh their details,
            # keep their URN exactly as it was.
            master_store.sync_update_visitor(existing_urn, mapped, source_hash=row_hash)
            already_synced_hashes.add(row_hash)
            updated_count += 1
            continue

        # Genuinely new row position — never seen before. Only now do
        # we mint a new URN.
        urn = generate_urn()
        master_store.insert_visitor(
            urn, mapped, source="sheet", source_hash=row_hash, sheet_row=row_num
        )
        already_synced_hashes.add(row_hash)
        urn_by_row[row_num] = urn
        new_count += 1

    logger.info(
        "Sheet sync done: %d new, %d updated, %d unchanged, %d blank, %d no_name (fetched %d)",
        new_count, updated_count, unchanged_count, blank_count, no_name_count, len(raw_rows),
    )
    return {
        "enabled": True,
        "fetched": len(raw_rows),
        "new": new_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "blank": blank_count,
        "no_name": no_name_count,
    }