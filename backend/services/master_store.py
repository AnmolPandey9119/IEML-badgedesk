"""
services/master_store.py
Master data store — now backed by Postgres (Neon), not a local
SQLite file. This is the ONE place all visitor data lives, no
matter where it came from:

  - Rows synced in from the Google Sheet (services/sheet_sync.py)
  - Onsite registrations done directly on a counter laptop

Every visitor gets exactly one row here, keyed by URN. Search / print
/ edit in the dashboard all read and write through this database —
never the Google Sheet directly (the sheet is read-only input,
synced in periodically; we never write back to it).

--------------------------------------------------------------------
WHY POSTGRES INSTEAD OF SQLITE
--------------------------------------------------------------------
Render (and most hosting platforms) give a web service an EPHEMERAL
local filesystem — any file it writes, including a SQLite database,
is wiped every time the service redeploys, restarts, or (on free
tiers) spins down from inactivity. That was the root cause of URNs
getting regenerated overnight with zero code changes involved.

Postgres on Neon is a genuinely separate, independently-hosted
service — the backend just connects to it over the network. The
backend container can restart/redeploy/spin down as often as it
wants; the database itself is completely unaffected.

--------------------------------------------------------------------
SHEET_ROW (fixes "URN changes on every sync")
--------------------------------------------------------------------
Simple rule: a Google Form-linked sheet only ever APPENDS new
responses at the bottom — an existing row's position never changes.
So the row's position in the sheet (2, 3, 4, ... — row 1 is the
header) IS a stable, permanent identity for that registration.

  - Row position already seen before -> that person already has a
    URN. We NEVER generate a new one for them — only refresh their
    other details if the row's content changed.
  - Row position never seen before -> a genuinely new registrant,
    appended since the last sync. Only now do we mint a new URN.

--------------------------------------------------------------------
PRINT TRACKING (NEW — for the master console)
--------------------------------------------------------------------
`print_count` on the visitors row is the running total of how many
times that person's badge has been printed, across every counter
laptop combined. `print_log` is a row-per-print history table that
also records WHICH named device (see routers/master.py + log_print()
below) did each print — that's what powers the master console's
"per device" breakdown. Both are populated only by log_print(),
called once from the print flow after a browser print genuinely
succeeds — never guessed or backfilled.
"""

import json
import re
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from config import settings

# Core columns every visitor always has. Anything beyond these
# (extra columns the sheet might grow later) is stored in
# `extra_json` so we never have to touch the schema again.
_CORE_FIELDS = ["name", "org", "city", "category", "status", "email", "mobile"]


def _row_to_visitor(row: dict) -> dict:
    visitor = {field: row[field] for field in _CORE_FIELDS}
    visitor["urn"] = row["urn"]
    visitor["print_count"] = row.get("print_count", 0) or 0
    visitor["scan_count"] = row.get("scan_count", 0) or 0
    # NEW: timestamp of this visitor's most recent entry-gate scan,
    # kept directly on the visitors row (alongside scan_count) so the
    # master console's Scanned Visitors table can show "last scanned"
    # without a separate scan_log lookup per row.
    visitor["last_scanned_at"] = row.get("last_scanned_at")
    # NEW: was stored in the DB but never surfaced before — the master
    # console needs this to tell onsite walk-in registrations apart
    # from the bulk Google Sheet sync. Existing callers that don't
    # care about this field simply ignore the extra key (Visitor/
    # MasterVisitor pydantic models both do this safely).
    visitor["source"] = row.get("source")
    extra = row["extra_json"] if isinstance(row["extra_json"], dict) else json.loads(row["extra_json"] or "{}")
    visitor.update(extra)
    return visitor


@contextmanager
def _connection():
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL isn't set in .env yet — paste your Neon connection "
            "string before running the backend."
        )
    conn = psycopg2.connect(settings.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """
    Creates the visitors table if it doesn't exist yet, and brings an
    EXISTING table (the live one already running in production) up to
    date using ADD COLUMN IF NOT EXISTS — so redeploying this file is
    all that's needed, no manual SQL against the live Neon database.
    Call once at startup.
    """
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS visitors (
                    urn         TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    org         TEXT,
                    city        TEXT,
                    category    TEXT,
                    status      TEXT,
                    email       TEXT,
                    mobile      TEXT,
                    extra_json  JSONB DEFAULT '{}'::jsonb,
                    source      TEXT NOT NULL,   -- 'sheet' or 'onsite'
                    source_hash TEXT,            -- last-seen row hash, for skipping unchanged rows
                    sheet_row   INTEGER,         -- row position in the sheet; WHO this person is, never changes
                    print_count INTEGER NOT NULL DEFAULT 0,  -- NEW: total times this visitor's badge was printed
                    scan_count  INTEGER NOT NULL DEFAULT 0,  -- NEW: total times this visitor was scanned at entry gates
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            # NEW: safe on an already-existing live table — does nothing
            # if the column is already there, adds it (defaulted to 0)
            # if it isn't.
            cur.execute(
                "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS print_count INTEGER NOT NULL DEFAULT 0"
            )
            cur.execute(
                "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS scan_count INTEGER NOT NULL DEFAULT 0"
            )
            # NEW: last time this visitor was scanned at any entry gate —
            # updated by log_scan() alongside scan_count. Lets the master
            # console show "last scanned" per visitor without joining
            # scan_log.
            cur.execute(
                "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS last_scanned_at TIMESTAMPTZ"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_visitors_source_hash "
                "ON visitors(source_hash) WHERE source_hash IS NOT NULL"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_visitors_mobile ON visitors(mobile)")
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_visitors_sheet_row "
                "ON visitors(sheet_row) WHERE sheet_row IS NOT NULL"
            )

            # print history table — one row per successful print,
            # tagged with the operator-chosen device name. This is
            # what the master console's per-device stats read from.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS print_log (
                    id          SERIAL PRIMARY KEY,
                    urn         TEXT NOT NULL REFERENCES visitors(urn) ON DELETE CASCADE,
                    device_name TEXT NOT NULL,
                    printed_at  TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_print_log_urn ON print_log(urn)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_print_log_device ON print_log(device_name)")

            # NEW: scan history table — one row per successful entry-gate
            # scan, tagged with the scanner-app-chosen scanner/gate name.
            # This is what the master console's Scan Monitoring tab reads
            # from — same pattern as print_log above, just for scanning.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_log (
                    id           SERIAL PRIMARY KEY,
                    urn          TEXT NOT NULL REFERENCES visitors(urn) ON DELETE CASCADE,
                    scanner_name TEXT NOT NULL,
                    scanned_at   TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_log_urn ON scan_log(urn)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_scan_log_scanner ON scan_log(scanner_name)")

            # RESTORED: mart_days_registrations bootstrap. The comment
            # that used to sit here said this table was dropped from
            # init_db() because "Mart Days runs on its own separate
            # portal" — but routers/mart_registration.py (public
            # register + badge-download) and now routers/mart_desk.py
            # (the separate onsite Mart Days desk) both read/write this
            # exact table, in THIS backend. That comment was simply
            # stale. CREATE TABLE IF NOT EXISTS is a no-op against the
            # live Neon table (already exists, historical data
            # untouched) and creates a working table from scratch on
            # any fresh/local database.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mart_days_registrations (
                    urn                  TEXT PRIMARY KEY,
                    buyer_type           TEXT,
                    full_name            TEXT,
                    company_name         TEXT,
                    designation          TEXT,
                    email                TEXT,
                    phone_number         TEXT,
                    address              TEXT,
                    district             TEXT,
                    state                TEXT,
                    country              TEXT,
                    pincode              TEXT,
                    nature_of_business   TEXT,
                    annual_turnover      TEXT,
                    known_through        TEXT,
                    online_seller        TEXT,
                    products_of_interest TEXT,
                    print_count          INTEGER NOT NULL DEFAULT 0,
                    scan_count           INTEGER NOT NULL DEFAULT 0,
                    badge_download_count INTEGER NOT NULL DEFAULT 0,
                    created_at           TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            # Safe on an already-existing live table — no-ops if the
            # column is already there. print_count/scan_count are what
            # the NEW Mart Days desk (routers/mart_desk.py) needs to
            # log prints against this table the same way the other-
            # events desk does against `visitors`.
            cur.execute(
                "ALTER TABLE mart_days_registrations ADD COLUMN IF NOT EXISTS print_count INTEGER NOT NULL DEFAULT 0"
            )
            cur.execute(
                "ALTER TABLE mart_days_registrations ADD COLUMN IF NOT EXISTS scan_count INTEGER NOT NULL DEFAULT 0"
            )
            cur.execute(
                "ALTER TABLE mart_days_registrations ADD COLUMN IF NOT EXISTS badge_download_count INTEGER NOT NULL DEFAULT 0"
            )
            # FIX: created_at only existed in the CREATE TABLE clause
            # above, which is a no-op against the live Neon table
            # (already existed from before this feature) — so the
            # column never actually got added there, and
            # search_mart_days()'s "ORDER BY created_at DESC" crashed
            # with psycopg2.errors.UndefinedColumn on every search.
            # Same ADD-COLUMN-IF-NOT-EXISTS pattern as the other
            # columns above fixes it for both existing and fresh DBs.
            cur.execute(
                "ALTER TABLE mart_days_registrations ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_mart_days_registrations_mobile ON mart_days_registrations(phone_number)"
            )


def existing_urns() -> set[str]:
    """
    All URNs currently in use — used to make sure a newly generated
    URN is unique. FIXED: this had been narrowed to check only
    `visitors`, on the (stale, incorrect) assumption that Mart Days
    registrations lived in a separate portal/database. They don't —
    mart_days_registrations is a table in this same database — so a
    URN minted here could theoretically collide with one already used
    over there. Checking both tables restores true uniqueness across
    the whole system, same as before that narrowing.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT urn FROM visitors")
        urns = {row["urn"] for row in cur.fetchall()}
        cur.execute("SELECT urn FROM mart_days_registrations")
        urns.update(row["urn"] for row in cur.fetchall())
        return urns


def existing_source_hashes() -> set[str]:
    """
    All source_hash values already synced from the sheet. sheet_sync.py
    uses this as a fast path to skip rows that are byte-for-byte
    identical to what we already have saved.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_hash FROM visitors WHERE source_hash IS NOT NULL")
        return {row["source_hash"] for row in cur.fetchall()}


def existing_urns_by_sheet_row() -> dict[int, str]:
    """
    Maps sheet_row -> urn for every sheet-synced visitor. sheet_sync.py
    uses this to recognize "this row position already has a URN" so it
    never mints a second one for the same row, no matter what else
    changed in that row's content.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT sheet_row, urn FROM visitors WHERE sheet_row IS NOT NULL")
        return {row["sheet_row"]: row["urn"] for row in cur.fetchall()}


def insert_visitor(
    urn: str,
    data: dict,
    source: str,
    source_hash: Optional[str] = None,
    sheet_row: Optional[int] = None,
) -> dict:
    """
    Inserts one visitor row — used only for genuinely NEW people
    (new sheet_row never seen before, or an onsite registration where
    sheet_row is None). `data` should contain whatever fields are
    known (name, org, city, category, status, email, mobile) — any
    keys beyond the core fields are kept in extra_json automatically,
    so new sheet columns later don't require a code change here.
    """
    core = {field: data.get(field) for field in _CORE_FIELDS}
    extra = {k: v for k, v in data.items() if k not in _CORE_FIELDS and k != "urn"}

    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO visitors
                (urn, name, org, city, category, status, email, mobile,
                 extra_json, source, source_hash, sheet_row)
            VALUES
                (%(urn)s, %(name)s, %(org)s, %(city)s, %(category)s, %(status)s,
                 %(email)s, %(mobile)s, %(extra_json)s, %(source)s, %(source_hash)s, %(sheet_row)s)
            """,
            {
                "urn": urn,
                **core,
                "extra_json": json.dumps(extra),
                "source": source,
                "source_hash": source_hash,
                "sheet_row": sheet_row,
            },
        )

    return {"urn": urn, "print_count": 0, **core, **extra}


def sync_update_visitor(urn: str, data: dict, source_hash: str) -> Optional[dict]:
    """
    Used ONLY by sheet_sync.py, when a row's content changed for a
    row position that ALREADY has a URN. Refreshes their details plus
    source_hash — but the URN itself (the primary key, WHERE clause)
    and sheet_row are never part of the SET here. That's the whole
    point of this fix: once assigned, a URN can only change if an
    admin edits it manually elsewhere.
    """
    core = {field: data.get(field) for field in _CORE_FIELDS}
    extra = {k: v for k, v in data.items() if k not in _CORE_FIELDS and k != "urn"}

    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE visitors
            SET name = %(name)s, org = %(org)s, city = %(city)s, category = %(category)s,
                status = %(status)s, email = %(email)s, mobile = %(mobile)s,
                extra_json = %(extra_json)s, source_hash = %(source_hash)s
            WHERE urn = %(urn)s
            """,
            {
                "urn": urn,
                **core,
                "extra_json": json.dumps(extra),
                "source_hash": source_hash,
            },
        )
        if cur.rowcount == 0:
            return None

    return get_by_urn(urn)


def update_visitor(urn: str, data: dict) -> Optional[dict]:
    """
    Manual/admin edit path (dashboard's Edit Details feature) —
    unchanged by this fix. Updates an existing visitor's editable
    fields directly by URN. Returns None if the URN doesn't exist.
    """
    core = {field: data.get(field) for field in _CORE_FIELDS}
    extra = {k: v for k, v in data.items() if k not in _CORE_FIELDS and k != "urn"}

    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE visitors
            SET name = %(name)s, org = %(org)s, city = %(city)s, category = %(category)s,
                status = %(status)s, email = %(email)s, mobile = %(mobile)s,
                extra_json = %(extra_json)s
            WHERE urn = %(urn)s
            """,
            {"urn": urn, **core, "extra_json": json.dumps(extra)},
        )
        if cur.rowcount == 0:
            return None

    return get_by_urn(urn)


def bulk_upsert_visitors(rows: list[dict]) -> dict:
    """
    NEW — bulk insert/update MANY visitors in ONE database round trip.
    Built for services/external_sync.py's push-API endpoint, which can
    receive thousands of records in a single call.

    WHY THIS EXISTS (instead of just calling insert_visitor()/
    sync_update_visitor() once per record, like sheet_sync.py does):
    those two open a FRESH connection every single call. For a
    handful of records that's fine — for a bulk push of, say, 30,000
    records, that's up to 60,000 sequential connections, which would
    take many minutes and — because it's all synchronous, blocking
    code — freeze the entire server (no printing, no scanning, no
    search for anyone) for that whole time. routers/external.py also
    runs this off the main thread via run_in_threadpool for the same
    reason: even a fast bulk upsert shouldn't block other requests.

    ONE connection, ONE INSERT ... ON CONFLICT statement covering the
    whole batch (via execute_values, chunked internally at page_size)
    — a few seconds even for tens of thousands of rows, instead of
    tens of minutes.

    `rows`: list of dicts with keys urn, name, org, city, category,
    status, email, mobile, extra (dict), source. On conflict (urn
    already exists), OVERWRITES every core field + extra_json with
    the new values — same full-replace semantics as
    sync_update_visitor() above, so behavior matches exactly whether
    a record arrives one-at-a-time or in a bulk batch. source /
    source_hash / sheet_row are only set on first insert — never
    touched on update, same rule sync_update_visitor() already
    follows (a URN's origin and sheet position don't change later).

    Returns {"created": int, "updated": int} — "created" and
    "updated" are computed from which URNs already existed BEFORE
    this call, same meaning external_sync.py's response already had.
    """
    if not rows:
        return {"created": 0, "updated": 0}

    urns = [r["urn"] for r in rows]

    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT urn FROM visitors WHERE urn = ANY(%s)", (urns,))
        existing_before = {row["urn"] for row in cur.fetchall()}

        values = [
            (
                r["urn"],
                r.get("name"),
                r.get("org"),
                r.get("city"),
                r.get("category"),
                r.get("status"),
                r.get("email"),
                r.get("mobile"),
                json.dumps(r.get("extra") or {}),
                r.get("source", "portal"),
            )
            for r in rows
        ]

        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO visitors
                (urn, name, org, city, category, status, email, mobile, extra_json, source)
            VALUES %s
            ON CONFLICT (urn) DO UPDATE SET
                name = EXCLUDED.name,
                org = EXCLUDED.org,
                city = EXCLUDED.city,
                category = EXCLUDED.category,
                status = EXCLUDED.status,
                email = EXCLUDED.email,
                mobile = EXCLUDED.mobile,
                extra_json = EXCLUDED.extra_json
            """,
            values,
            page_size=1000,
        )

    unique_urns = set(urns)
    created = len(unique_urns - existing_before)
    updated = len(unique_urns & existing_before)
    return {"created": created, "updated": updated}


def delete_visitor(urn: str) -> bool:
    """
    NEW — master console only (routers/master.py gates this behind
    get_current_master). Permanently removes a visitor row. Their
    print_log rows go with it automatically (ON DELETE CASCADE above).
    Returns True if a row was actually deleted, False if that URN
    didn't exist.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM visitors WHERE urn = %s", (urn.strip(),))
        return cur.rowcount > 0


def log_print(urn: str, device_name: str) -> Optional[dict]:
    """
    NEW — called once from the print flow right after a browser print
    genuinely succeeds (see routers/registration.py's new
    POST /{urn}/print-log). Increments that visitor's print_count and
    records one row in print_log tagged with the device name the
    operator gave at login. Returns the updated visitor, or None if
    the URN doesn't exist (e.g. a stale/removed record).
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE visitors SET print_count = print_count + 1 WHERE urn = %s",
            (urn.strip(),),
        )
        if cur.rowcount == 0:
            return None
        cur.execute(
            "INSERT INTO print_log (urn, device_name) VALUES (%s, %s)",
            (urn.strip(), device_name.strip() or "Unnamed device"),
        )

    return get_by_urn(urn)


def print_stats() -> dict:
    """
    NEW — powers the master console's print stats view. Returns:
      {
        "overall_total": <int, sum of every print across every device>,
        "unique_total": <int, distinct visitors printed at least once>,
        "by_device": [{"device_name": "Counter 1", "count": 42}, ...]
      }
    unique_total is NEW — added alongside overall_total so a reprinted
    badge (which bumps overall_total every time) doesn't make it look
    like more people were printed than actually were.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM print_log")
        overall_total = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(DISTINCT urn) AS c FROM print_log")
        unique_total = cur.fetchone()["c"]

        cur.execute(
            """
            SELECT device_name, COUNT(*) AS count
            FROM print_log
            GROUP BY device_name
            ORDER BY count DESC
            """
        )
        by_device = [{"device_name": row["device_name"], "count": row["count"]} for row in cur.fetchall()]

    return {"overall_total": overall_total, "unique_total": unique_total, "by_device": by_device}


def log_scan(urn: str, scanner_name: str) -> Optional[dict]:
    """
    NEW — called once from the entrance-scanning app right after a
    QR/RFID read resolves to a real visitor. Increments that
    visitor's scan_count and records one row in scan_log tagged with
    the scanner/gate name given at login. Returns the updated
    visitor, or None if the URN doesn't exist (e.g. a bad/garbled
    scan). Mirrors log_print() exactly.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE visitors SET scan_count = scan_count + 1, last_scanned_at = NOW() WHERE urn = %s",
            (urn.strip(),),
        )
        if cur.rowcount == 0:
            return None
        cur.execute(
            "INSERT INTO scan_log (urn, scanner_name) VALUES (%s, %s)",
            (urn.strip(), scanner_name.strip() or "Unnamed scanner"),
        )

    return get_by_urn(urn)


def scan_stats() -> dict:
    """
    NEW — powers the master console's Scan Monitoring tab. Returns:
      {
        "overall_total": <int, sum of every scan across every gate>,
        "unique_total": <int, distinct visitors scanned at least once>,
        "by_scanner": [{"scanner_name": "Gate 1", "count": 240}, ...]
      }
    unique_total is NEW — mirrors print_stats(). At a multi-day event
    with repeat entry/exit scans, overall_total can be far bigger than
    the actual number of people who walked through the gate.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM scan_log")
        overall_total = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(DISTINCT urn) AS c FROM scan_log")
        unique_total = cur.fetchone()["c"]

        cur.execute(
            """
            SELECT scanner_name, COUNT(*) AS count
            FROM scan_log
            GROUP BY scanner_name
            ORDER BY count DESC
            """
        )
        by_scanner = [{"scanner_name": row["scanner_name"], "count": row["count"]} for row in cur.fetchall()]

    return {"overall_total": overall_total, "unique_total": unique_total, "by_scanner": by_scanner}


def recent_scans(limit: int = 100) -> list[dict]:
    """
    NEW — powers the master console's Scan Monitoring live feed.
    Returns the most recent scan_log rows (newest first), each
    joined with that visitor's current name/organization/category so
    the frontend can render a live "who / where / when" table with
    zero extra lookups. Mirrors search()/get_all()'s read-only style.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT sl.id, sl.scanner_name, sl.scanned_at,
                   v.urn, v.name, v.org AS organization, v.category
            FROM scan_log sl
            JOIN visitors v ON v.urn = sl.urn
            ORDER BY sl.scanned_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_by_urn(urn: str) -> Optional[dict]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM visitors WHERE urn = %s", (urn.strip(),))
        row = cur.fetchone()
        return _row_to_visitor(row) if row else None


def search(query: str, limit: int = 25) -> list[dict]:
    """Search by URN, name, mobile, organization, or email — same box handles typed search and QR-scanner input."""
    q = f"%{query.strip()}%"
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM visitors
            WHERE urn ILIKE %s OR name ILIKE %s OR mobile ILIKE %s OR org ILIKE %s OR email ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (q, q, q, q, q, limit),
        )
        return [_row_to_visitor(row) for row in cur.fetchall()]


_MART_DAYS_LIST_FIELDS = ("nature_of_business", "known_through", "products_of_interest")


def _serialize_mart_days_checkbox_fields(mart_days_data: dict) -> dict:
    """
    Checkbox-group answers arrive as Python lists (from
    payload.model_dump()). Postgres TEXT columns need strings, so any
    list gets JSON-encoded here; None/empty stays None so the column
    is just NULL rather than the string "null" or "[]".
    """
    out = dict(mart_days_data)
    for field in _MART_DAYS_LIST_FIELDS:
        value = out.get(field)
        out[field] = json.dumps(value) if value else None
    return out


def insert_mart_days_visitor(urn: str, mart_days_data: dict) -> dict:
    """
    RESTORED — the public Mart Days registration form
    (routers/mart_registration.py) writes here. Mart Days now mostly
    runs on its own separate portal, but THIS specific endpoint
    (/api/mart-days/register, already circulating publicly) is still
    live and must keep working, so this table + these functions stay.
    Writes ONLY to mart_days_registrations — no matching `visitors`
    row is created.
    """
    data = _serialize_mart_days_checkbox_fields(mart_days_data)
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart_days_registrations
                (urn, buyer_type, full_name, company_name, designation,
                 email, phone_number, address, district, state, country, pincode,
                 nature_of_business, annual_turnover, known_through, online_seller, products_of_interest)
            VALUES
                (%(urn)s, %(buyer_type)s, %(full_name)s, %(company_name)s, %(designation)s,
                 %(email)s, %(phone_number)s, %(address)s, %(district)s, %(state)s, %(country)s, %(pincode)s,
                 %(nature_of_business)s, %(annual_turnover)s, %(known_through)s, %(online_seller)s, %(products_of_interest)s)
            """,
            {
                "urn": urn,
                "buyer_type": data.get("buyer_type"),
                "full_name": data.get("full_name"),
                "company_name": data.get("company_name"),
                "designation": data.get("designation"),
                "email": data.get("email"),
                "phone_number": data.get("phone_number"),
                "address": data.get("address"),
                "district": data.get("district"),
                "state": data.get("state"),
                "country": data.get("country"),
                "pincode": data.get("pincode"),
                "nature_of_business": data.get("nature_of_business"),
                "annual_turnover": data.get("annual_turnover"),
                "known_through": data.get("known_through"),
                "online_seller": data.get("online_seller"),
                "products_of_interest": data.get("products_of_interest"),
            },
        )

    return _mart_days_row_to_visitor_shape({"urn": urn, "print_count": 0, "scan_count": 0, **mart_days_data})


def _mart_days_row_to_visitor_shape(row: dict) -> dict:
    """Maps a mart_days_registrations row onto the same shape badge_image.build_ebadge_pdf() expects."""
    return {
        "urn": row["urn"],
        "name": row["full_name"],
        "organization": row["company_name"],
        "designation": row.get("designation"),
        "mobile": row["phone_number"],
        "email": row["email"],
        "category": row["buyer_type"],
        "print_count": row.get("print_count", 0) or 0,
        "scan_count": row.get("scan_count", 0) or 0,
        "last_scanned_at": row.get("last_scanned_at"),
        "badge_download_count": row.get("badge_download_count", 0) or 0,
    }


def get_mart_days_by_urn(urn: str) -> Optional[dict]:
    """Looks up a single Mart Days registrant by URN — used by the public badge-download lookup."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM mart_days_registrations WHERE urn = %s", (urn,))
        row = cur.fetchone()
        return _mart_days_row_to_visitor_shape(dict(row)) if row else None


def find_mart_days_by_email(email: str) -> Optional[dict]:
    """Case-insensitive email match — used for the public form's duplicate-registration check."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM mart_days_registrations WHERE LOWER(email) = LOWER(%s) LIMIT 1",
            (email.strip(),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def find_mart_days_by_mobile(mobile: str) -> Optional[dict]:
    """
    Mobile match, digits-only comparison so "+91 98765 43210" and
    "9876543210" are treated as the same number.
    """
    mobile_digits = re.sub(r"\D", "", mobile or "")
    if not mobile_digits:
        return None
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM mart_days_registrations
            WHERE REGEXP_REPLACE(COALESCE(phone_number, ''), '\\D', '', 'g') = %s
            LIMIT 1
            """,
            (mobile_digits,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def log_mart_days_badge_download(urn: str) -> Optional[dict]:
    """Increments badge_download_count — called every time the public /badge-download endpoint succeeds."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE mart_days_registrations SET badge_download_count = badge_download_count + 1 WHERE urn = %s",
            (urn,),
        )
        if cur.rowcount == 0:
            return None

    return get_mart_days_by_urn(urn)


def search_mart_days(query: str, limit: int = 25) -> list[dict]:
    """
    NEW — Mart Days desk counterpart to search() above. Same idea
    (URN / name / mobile / company / email), scoped to
    mart_days_registrations instead of visitors, so the two desks
    never see each other's people.
    """
    q = f"%{query.strip()}%"
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM mart_days_registrations
            WHERE urn ILIKE %s OR full_name ILIKE %s OR company_name ILIKE %s
               OR phone_number ILIKE %s OR email ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (q, q, q, q, q, limit),
        )
        return [_mart_days_row_to_visitor_shape(dict(row)) for row in cur.fetchall()]


def update_mart_days_visitor(urn: str, data: dict) -> Optional[dict]:
    """
    NEW — Mart Days desk counterpart to update_visitor() above. Lets
    the Mart Days operator fix a typo'd name/company/mobile/email
    before printing, same as the other-events desk can. buyer_type
    doubles as this table's "category" in the shared Visitor shape.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE mart_days_registrations
            SET full_name = %(full_name)s,
                company_name = %(company_name)s,
                designation = %(designation)s,
                phone_number = %(phone_number)s,
                email = %(email)s,
                buyer_type = %(buyer_type)s
            WHERE urn = %(urn)s
            """,
            {
                "urn": urn,
                "full_name": data.get("full_name"),
                "company_name": data.get("company_name"),
                "designation": data.get("designation"),
                "phone_number": data.get("phone_number"),
                "email": data.get("email"),
                "buyer_type": data.get("buyer_type"),
            },
        )
        if cur.rowcount == 0:
            return None
    return get_mart_days_by_urn(urn)


def log_print_mart_days(urn: str, device_name: str) -> Optional[dict]:
    """
    NEW — Mart Days desk counterpart to log_print() above. Increments
    this registrant's print_count directly on mart_days_registrations.
    device_name isn't written to a per-device print_log table yet
    (there's no such table for this side) — just accepted for
    symmetry with the other desk's API shape. Add a
    mart_days_print_log table later if per-device breakdowns are ever
    needed here too.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE mart_days_registrations SET print_count = print_count + 1 WHERE urn = %s",
            (urn,),
        )
        if cur.rowcount == 0:
            return None
    return get_mart_days_by_urn(urn)


def get_all() -> list[dict]:
    """Every visitor currently in the master store — used by the Excel export and the master console."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM visitors ORDER BY created_at ASC")
        return [_row_to_visitor(row) for row in cur.fetchall()]


def count() -> int:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM visitors")
        return cur.fetchone()["c"]


# ----------------------------------------------------------------
# NEW — Unscanned Entries (printed but never scanned at any gate)
# ----------------------------------------------------------------

def unscanned_entries(limit: int = 5000) -> list[dict]:
    """
    NEW — powers the master console's "Unscanned Entries" tab. A
    visitor lands here if their badge has been printed at least once
    (print_count > 0) but they have never been scanned at any
    entrance gate (scan_count = 0). last_printed_at is pulled from
    print_log (the visitors table itself has no such column, only
    last_scanned_at) via MAX(printed_at) per visitor, same join style
    as recent_scans() above.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.urn, v.name, v.org AS organization, v.category,
                   v.mobile, v.print_count, MAX(pl.printed_at) AS last_printed_at
            FROM visitors v
            JOIN print_log pl ON pl.urn = v.urn
            WHERE v.print_count > 0 AND v.scan_count = 0
            GROUP BY v.urn, v.name, v.org, v.category, v.mobile, v.print_count
            ORDER BY MAX(pl.printed_at) DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


# ----------------------------------------------------------------
# NEW — Clear History (end-of-event reset)
# ----------------------------------------------------------------

def clear_history() -> dict:
    """
    Master console only (routers/master.py gates this behind
    get_current_master, same as delete_visitor()). Wipes print/scan
    HISTORY only, ready for the next event: print_log + scan_log rows
    deleted entirely, and every `visitors` row's print_count/
    scan_count/last_scanned_at reset to 0/0/NULL.

    REVERTED: this used to be scope-aware ("mart_days" / "other_events"
    / "both") for two independent event buckets. There's only the one
    `visitors` bucket again now that Mart Days runs on its own
    separate portal, so this always resets that one bucket — same
    behaviour as before the scope split existed.

    Deliberately does NOT touch name/org/city/category/status/email/
    mobile/extra_json/source/sheet_row — only print/scan activity is
    cleared. Runs as one transaction (the _connection() context
    manager commits only at the end, so if anything here fails,
    nothing is partially cleared).
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM print_log")
        print_logs_cleared = cur.rowcount

        cur.execute("DELETE FROM scan_log")
        scan_logs_cleared = cur.rowcount

        cur.execute(
            """
            UPDATE visitors
            SET print_count = 0, scan_count = 0, last_scanned_at = NULL
            WHERE print_count > 0 OR scan_count > 0
            """
        )
        visitors_reset = cur.rowcount

    return {
        "visitors_reset": visitors_reset,
        "print_logs_cleared": print_logs_cleared,
        "scan_logs_cleared": scan_logs_cleared,
    }


def stats_by_source() -> dict:
    """
    NEW — separate fetching for the two ways data lands in `visitors`:
    Google Sheet sync + onsite counter registration (source in
    'sheet'/'onsite' — the actual event registration flow) vs sir's
    portal push (source='portal', via POST /api/external/save-data).
    Both still live in the SAME visitors table (no new table needed —
    the `source` column already tells them apart); this just groups
    registered/print/scan counts by that column so the master console
    can read each bucket's numbers on its own instead of only ever
    seeing one merged total.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT source,
                   COUNT(*) AS registered,
                   COALESCE(SUM(print_count), 0) AS print_total,
                   COUNT(*) FILTER (WHERE print_count > 0) AS print_unique,
                   COALESCE(SUM(scan_count), 0) AS scan_total,
                   COUNT(*) FILTER (WHERE scan_count > 0) AS scan_unique
            FROM visitors
            GROUP BY source
            """
        )
        by_source = {row["source"]: dict(row) for row in cur.fetchall()}

    def _bucket(*sources: str) -> dict:
        registered = print_total = print_unique = scan_total = scan_unique = 0
        for src in sources:
            row = by_source.get(src)
            if not row:
                continue
            registered += row["registered"]
            print_total += row["print_total"]
            print_unique += row["print_unique"]
            scan_total += row["scan_total"]
            scan_unique += row["scan_unique"]
        return {
            "registered": registered,
            "print_total": print_total,
            "print_unique": print_unique,
            "scan_total": scan_total,
            "scan_unique": scan_unique,
        }

    return {
        "sheet_and_onsite": _bucket("sheet", "onsite"),
        "portal": _bucket("portal"),
    }


def purge_everything() -> dict:
    """
    Master console's hidden "Danger Zone" full wipe (routers/
    master.py's POST /purge-all, master-only + a server-side confirm
    phrase check on top of that). Deletes every `visitors` row (their
    print_log/scan_log go with them via ON DELETE CASCADE).

    REVERTED: this used to be scope-aware ("mart_days" / "other_events"
    / "both") for two independent event buckets to wipe. There's only
    the one `visitors` bucket again now, so this always wipes it —
    the same true "start completely fresh" reset this function did
    before the scope split existed.

    Counts everything BEFORE deleting (since the cascade means
    print_log/scan_log row counts would otherwise be gone by the time
    we could count them), all inside one transaction.
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM visitors")
        visitors_deleted = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM print_log")
        print_logs_deleted = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM scan_log")
        scan_logs_deleted = cur.fetchone()["c"]
        cur.execute("DELETE FROM visitors")  # cascades to print_log + scan_log

    return {
        "visitors_deleted": visitors_deleted,
        "print_logs_deleted": print_logs_deleted,
        "scan_logs_deleted": scan_logs_deleted,
    }