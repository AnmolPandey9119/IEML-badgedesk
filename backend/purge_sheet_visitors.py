"""
purge_sheet_visitors.py
ONE-TIME script — run this manually, exactly once, at the moment you
switch the data source from Google Sheet Sync to the portal Push API
(after you've set SHEET_SYNC_ENABLED=false and cleared GOOGLE_SHEET_URL
on Render).

Deletes every visitor whose source = 'sheet' (i.e. came in from the
OLD event's Google Sheet) — their print_log / scan_log rows go with
them automatically (ON DELETE CASCADE, same as the master console's
single-visitor delete). Visitors from source='portal' or
source='onsite' are never touched.

HOW TO RUN (safe — dry-run by default):

    cd backend
    python3 purge_sheet_visitors.py

This only SHOWS what would be deleted (count + a sample of names) and
does nothing else. To actually delete, run it with --confirm:

    python3 purge_sheet_visitors.py --confirm

On Render: use the "Shell" tab on your backend service (Render
dashboard -> your service -> Shell) and run the same two commands
there, so it runs against the real production database.
"""

import sys

import psycopg2
import psycopg2.extras

from config import settings


def main() -> None:
    confirm = "--confirm" in sys.argv

    if not settings.database_url:
        print("DATABASE_URL isn't set — check your .env / environment.")
        sys.exit(1)

    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS c FROM visitors WHERE source = 'sheet'")
            total = cur.fetchone()["c"]

            if total == 0:
                print("No source='sheet' visitors found — nothing to do.")
                return

            cur.execute(
                "SELECT urn, name, org FROM visitors WHERE source = 'sheet' ORDER BY created_at LIMIT 10"
            )
            sample = cur.fetchall()

            print(f"Found {total} visitor(s) with source='sheet'.")
            print("Sample (up to 10):")
            for row in sample:
                print(f"  {row['urn']}  —  {row['name']}  ({row['org'] or 'no org'})")

            if not confirm:
                print()
                print(f"DRY RUN — nothing deleted. {total} visitor(s) would be removed,")
                print("along with their print/scan history.")
                print("Re-run with --confirm to actually delete them:")
                print("  python3 purge_sheet_visitors.py --confirm")
                return

            cur.execute("DELETE FROM visitors WHERE source = 'sheet'")
            deleted = cur.rowcount
            conn.commit()
            print()
            print(f"Deleted {deleted} visitor(s) with source='sheet' (and their print/scan history).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()