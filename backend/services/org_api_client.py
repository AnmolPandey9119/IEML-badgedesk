"""
services/org_api_client.py
The ONLY place in this backend that decides between:
  - DEMO_MODE=true  -> realistic in-memory mock data
  - DEMO_MODE=false -> real HTTP calls to the organization's server

Routers never talk to httpx or mock data directly — they always go
through the functions in this file. That means switching from demo
to production later is a one-line .env change, nothing else in the
codebase needs to know.

The org server is the ONLY data store for this system. There is no
local database here — every search hits the org server live, and
every registration/update is saved there directly. If the org server
is unreachable, the request fails and the operator retries; nothing
is queued locally.
"""

import random
import string

import httpx

from config import settings
from models.visitor import Visitor


# ==========================================================
# DEMO MODE: in-memory mock dataset
# ==========================================================
# Pre-seeded sample visitors so search has something to find while
# building/demoing, before real ORG_API_BASE_URL + ORG_API_KEY exist.
# New registrations in demo mode also get appended here (resets when
# the server restarts).
_MOCK_VISITORS: list[dict] = [
    {
        "urn": "FQFKRQ",
        "name": "Anmol Pandey",
        "organization": "India Expo Mart Ltd.",
        "designation": "Event Partner",
        "mobile": "9990000001",
        "email": "anmol.pandey@example.com",
        "category": "exhibitor",
    },
    {
        "urn": "GXTP2M",
        "name": "Riya Sharma",
        "organization": "Trident Group",
        "designation": "Marketing Manager",
        "mobile": "9990000002",
        "email": "riya.sharma@example.com",
        "category": "delegate",
    },
    {
        "urn": "KLM901",
        "name": "Arjun Mehta",
        "organization": "Vardhman Textiles",
        "designation": "Visitor",
        "mobile": "9990000003",
        "email": "arjun.mehta@example.com",
        "category": "visitor",
    },
    {
        "urn": "PQR773",
        "name": "Sana Khan",
        "organization": "The Hindu Business Line",
        "designation": "Correspondent",
        "mobile": "9990000004",
        "email": "sana.khan@example.com",
        "category": "media",
    },
]


def _generate_urn() -> str:
    """Generates a 6-character alphanumeric URN, matching the badge format. Demo mode only — the real org server assigns real URNs."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


def _matches(visitor: dict, query: str) -> bool:
    q = query.strip().lower()
    return (
        q in visitor["urn"].lower()
        or q in visitor["name"].lower()
        or q in (visitor.get("mobile") or "").lower()
        or q in (visitor.get("organization") or "").lower()
    )


def _find_mock_by_urn(urn: str) -> dict | None:
    for v in _MOCK_VISITORS:
        if v["urn"].lower() == urn.strip().lower():
            return v
    return None


# ==========================================================
# Public functions used by routers
# ==========================================================

async def search_visitor(query: str) -> list[Visitor]:
    """Realtime search by URN / QR value / name / mobile / organization. Also what a QR scan resolves through, since the scanner just types the URN into the search box."""
    if settings.demo_mode:
        matches = [v for v in _MOCK_VISITORS if _matches(v, query)]
        return [Visitor(**v) for v in matches]

    # ---------- Real org server ----------
    url = f"{settings.org_api_base_url}/visitors/search"
    headers = {"Authorization": f"Bearer {settings.org_api_key}"}

    async with httpx.AsyncClient(timeout=settings.org_api_timeout_seconds) as client:
        resp = await client.get(url, headers=headers, params={"q": query})
        resp.raise_for_status()
        data = resp.json()
        return [Visitor(**item) for item in data.get("results", [])]


async def register_visitor(payload: dict) -> Visitor:
    """
    Registers a new onsite visitor directly on the org server and
    returns the assigned URN so the frontend can immediately trigger
    a badge print. Raises on failure — there's no local fallback, so
    the frontend shows the error and the operator retries.
    """
    if settings.demo_mode:
        urn = _generate_urn()
        visitor_dict = {"urn": urn, **payload}
        _MOCK_VISITORS.append(visitor_dict)
        return Visitor(**visitor_dict)

    # ---------- Real org server ----------
    url = f"{settings.org_api_base_url}/visitors/register"
    headers = {"Authorization": f"Bearer {settings.org_api_key}"}

    async with httpx.AsyncClient(timeout=settings.org_api_timeout_seconds) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return Visitor(**data)


async def update_visitor(urn: str, payload: dict) -> Visitor:
    """
    Updates an already-registered visitor's editable details (name,
    organization, designation, mobile, email, category) on the org
    server. URN never changes — it's the path identifier, not part
    of the editable payload. Raises on failure (including "URN not
    found") — there's no local fallback, so the frontend shows the
    error and the operator retries.
    """
    if settings.demo_mode:
        visitor_dict = _find_mock_by_urn(urn)
        if visitor_dict is None:
            raise ValueError(f"No visitor found with URN '{urn}'")
        visitor_dict.update(payload)
        return Visitor(**visitor_dict)

    # ---------- Real org server ----------
    url = f"{settings.org_api_base_url}/visitors/{urn}"
    headers = {"Authorization": f"Bearer {settings.org_api_key}"}

    async with httpx.AsyncClient(timeout=settings.org_api_timeout_seconds) as client:
        resp = await client.put(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return Visitor(**data)