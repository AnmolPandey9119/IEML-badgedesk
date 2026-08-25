"""
utils/urn.py
Generates the unique URN every visitor gets — printed as text + QR
on their badge, and the code they show/tell at the event to get
their badge printed.

One function, used from two places:
  - services/sheet_sync.py    -> new rows synced in from the Google Sheet
  - routers/registration.py   -> onsite walk-in registrations
Both go through this so URNs are guaranteed unique across the whole
system regardless of where the visitor came from.
"""

import random
import string

from services import master_store

_CHARS = string.ascii_uppercase + string.digits


def generate_urn() -> str:
    """
    Generates a 6-character alphanumeric URN (e.g. 'FQFKRQ') that
    isn't already used by anyone in the master store. Collisions are
    astronomically rare at 6 chars (36^6 = ~2.1 billion combos), but
    we check anyway since it costs nothing and guarantees safety.
    """
    used = master_store.existing_urns()
    while True:
        urn = "".join(random.choices(_CHARS, k=6))
        if urn not in used:
            return urn