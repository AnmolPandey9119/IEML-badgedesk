"""
services/edition_store.py
The ONE place that knows "which Mart Days edition is running right now".

Edition number, dates, timing, venue, co-located show etc. used to be
hardcoded in 5 different files (email template, registration page,
badge-download page, desk header...). Now they live in a single row in
the `mart_days_edition` table, edited by the master from the admin page
(martdays-admin). Every consumer reads from here:

  - services/email_templates.py   -> confirmation email text + subject
  - routers/mart_edition.py       -> GET /api/mart-edition (public),
                                     used by frontend-martdays,
                                     martdays-badge and martdays-desk to
                                     fill in their headers/chips
  - routers/mart_registration.py  -> tags each registration with the
                                     edition number (so a buyer who came
                                     last month can register again)

If the database is unreachable, get_edition() falls back to DEFAULTS so a
confirmation email or a page load never crashes because of this.
"""

import logging
from datetime import date
from typing import Optional

from services import master_store

logger = logging.getLogger("edition_store")

DEFAULTS = {
    "edition_number": 30,
    "start_date": date(2026, 10, 22),
    "end_date": date(2026, 10, 23),
    "event_name": "IEML Mart Sourcing Days",
    "timing": "11 AM–5 PM",
    "venue": "India Expo Centre & Mart, Greater Noida, Uttar Pradesh",
    "co_located_with": "Renewable Energy India 2026 / Battery India Expo 2026",
    "badge_tag": "Mega Mart",
    "email_note": "",
}

_EDITABLE = tuple(DEFAULTS.keys())
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def ordinal(n: int) -> str:
    """30 -> '30th', 31 -> '31st', 32 -> '32nd', 33 -> '33rd', 11 -> '11th'."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_dates(start: date, end: date, short: bool = False) -> str:
    """
    22-23 Oct 2026 / 22-23 October 2026 (same month),
    30 Oct - 1 Nov 2026 (across months), 31 Dec 2026 - 1 Jan 2027 (across
    years), or a single day if start == end. En dash is used.
    """
    def mon(d: date) -> str:
        name = _MONTHS[d.month - 1]
        return name[:3] if short else name

    if start == end:
        return f"{start.day} {mon(start)} {start.year}"
    if start.year != end.year:
        return f"{start.day} {mon(start)} {start.year} – {end.day} {mon(end)} {end.year}"
    if start.month != end.month:
        return f"{start.day} {mon(start)} – {end.day} {mon(end)} {end.year}"
    return f"{start.day}–{end.day} {mon(end)} {end.year}"


def _with_derived(edition: dict) -> dict:
    """Adds the display strings every consumer needs, computed from the stored fields."""
    out = dict(edition)
    out["edition_label"] = f"{ordinal(out['edition_number'])} Edition"
    out["dates_long"] = format_dates(out["start_date"], out["end_date"])
    out["dates_short"] = format_dates(out["start_date"], out["end_date"], short=True)
    out["start_date"] = out["start_date"].isoformat()
    out["end_date"] = out["end_date"].isoformat()
    if out.get("updated_at") is not None:
        out["updated_at"] = out["updated_at"].isoformat()
    return out


def init_table() -> None:
    """Creates the single-row settings table and seeds it with DEFAULTS the first time only."""
    with master_store._connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mart_days_edition (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                edition_number  INTEGER NOT NULL,
                start_date      DATE NOT NULL,
                end_date        DATE NOT NULL,
                event_name      TEXT NOT NULL,
                timing          TEXT NOT NULL DEFAULT '',
                venue           TEXT NOT NULL DEFAULT '',
                co_located_with TEXT NOT NULL DEFAULT '',
                badge_tag       TEXT NOT NULL DEFAULT '',
                email_note      TEXT NOT NULL DEFAULT '',
                updated_at      TIMESTAMPTZ DEFAULT NOW(),
                updated_by      TEXT
            )
            """
        )
        cur.execute(
            """
            INSERT INTO mart_days_edition
                (id, edition_number, start_date, end_date, event_name, timing,
                 venue, co_located_with, badge_tag, email_note, updated_by)
            VALUES (1, %(edition_number)s, %(start_date)s, %(end_date)s, %(event_name)s, %(timing)s,
                    %(venue)s, %(co_located_with)s, %(badge_tag)s, %(email_note)s, 'seed')
            ON CONFLICT (id) DO NOTHING
            """,
            DEFAULTS,
        )
        # Registrations carry the edition they were made for, so someone who came
        # last month isn't blocked as a "duplicate" when they register again.
        cur.execute("ALTER TABLE mart_days_registrations ADD COLUMN IF NOT EXISTS edition_number INTEGER")


def get_edition() -> dict:
    """Current edition incl. derived display strings. Never raises: falls back to DEFAULTS."""
    try:
        with master_store._connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM mart_days_edition WHERE id = 1")
            row = cur.fetchone()
        if row:
            return _with_derived(dict(row))
    except Exception:
        logger.exception("Could not read mart_days_edition -- using built-in defaults")
    return _with_derived(dict(DEFAULTS))


def current_edition_number() -> int:
    return get_edition()["edition_number"]


def save_edition(data: dict, updated_by: Optional[str] = None) -> dict:
    """Overwrites the single settings row with the editable fields in `data`."""
    values = {k: data[k] for k in _EDITABLE}
    values["updated_by"] = updated_by
    with master_store._connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE mart_days_edition SET
                edition_number = %(edition_number)s, start_date = %(start_date)s,
                end_date = %(end_date)s, event_name = %(event_name)s, timing = %(timing)s,
                venue = %(venue)s, co_located_with = %(co_located_with)s,
                badge_tag = %(badge_tag)s, email_note = %(email_note)s,
                updated_at = NOW(), updated_by = %(updated_by)s
            WHERE id = 1
            """,
            values,
        )
    return get_edition()