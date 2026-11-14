"""
routers/mart_owner.py
PUBLIC "Mart Owner" consent form endpoint (martdays-owner frontend).

Completely separate from the buyer flow:
  - writes ONLY to the existing `mart_owners` table (never to
    mart_days_registrations), so owner data can never mix with buyer data
  - NO email / WhatsApp / badge / URN (record-keeping form only)
  - duplicate check = email and mobile must be UNIQUE within mart_owners

Existing table columns used:
  full_name (First + Last), company_name, category, mobile_number, email,
  notes (Mart No. + the two consent answers), created_at.
  `urn` is left NULL on purpose (no badge for owners). `id` is left to the
  table's own default/sequence when it has one.

No Depends() on purpose: this router is intentionally public, like
routers/mart_registration.py.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from services import master_store

logger = logging.getLogger("mart_owner")
router = APIRouter()

OWNER_CATEGORY = "Mart Owner"
_LOCK_KEY = 7310420  # arbitrary constant: serialises owner inserts so two
                     # simultaneous submits can't both pass the duplicate check


class MartOwnerRequest(BaseModel):
    mart_no: str = Field(..., min_length=1, max_length=50)  # alphanumeric + special chars allowed
    company_name: str = Field(..., min_length=1, max_length=200)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    mobile_number: str = Field(..., min_length=10, max_length=20)
    email: EmailStr
    open_mart: str = Field(..., description="Yes / No")
    domestic_interest: str = Field(..., max_length=50)

    @field_validator("open_mart")
    @classmethod
    def _yes_no(cls, v: str) -> str:
        if v not in ("Yes", "No"):
            raise ValueError("open_mart must be Yes or No")
        return v

    @field_validator("mart_no", "company_name", "first_name", "last_name", "domestic_interest")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class MartOwnerResponse(BaseModel):
    full_name: str


def _mobile_last10(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else None


@router.post("/register", response_model=MartOwnerResponse)
async def register_mart_owner(payload: MartOwnerRequest):
    mobile10 = _mobile_last10(payload.mobile_number)
    if not mobile10:
        raise HTTPException(status_code=422, detail="Please enter a valid 10-digit Mobile Number.")

    email = payload.email.strip()
    full_name = f"{payload.first_name} {payload.last_name}".strip()
    notes = (
        f"Mart No: {payload.mart_no} | "
        f"Open Mart during Mart Sourcing Days: {payload.open_mart} | "
        f"Interested in Domestic Volume Buyers: {payload.domestic_interest}"
    )

    try:
        with master_store._connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))

            # --- uniqueness: only against OTHER MART OWNERS ---
            cur.execute("SELECT id FROM mart_owners WHERE LOWER(email) = LOWER(%s) LIMIT 1", (email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="This Email ID is already registered as a Mart Owner. Each email can be used only once.",
                )
            cur.execute(
                """
                SELECT id FROM mart_owners
                WHERE RIGHT(REGEXP_REPLACE(COALESCE(mobile_number, ''), '\\D', '', 'g'), 10) = %s
                LIMIT 1
                """,
                (mobile10,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="This Mobile Number is already registered as a Mart Owner. Each mobile number can be used only once.",
                )

            # Does `id` generate itself (serial / identity / any default)?
            cur.execute(
                """
                SELECT column_default, is_identity
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'mart_owners' AND column_name = 'id'
                """
            )
            col = cur.fetchone() or {}
            id_is_auto = bool(col.get("column_default")) or col.get("is_identity") == "YES"

            values = {
                "full_name": full_name,
                "company_name": payload.company_name,
                "category": OWNER_CATEGORY,
                "mobile_number": "+91 " + mobile10,
                "email": email,
                "notes": notes,
            }
            if id_is_auto:
                cur.execute(
                    """
                    INSERT INTO mart_owners
                        (full_name, company_name, category, mobile_number, email, notes, created_at)
                    VALUES
                        (%(full_name)s, %(company_name)s, %(category)s, %(mobile_number)s, %(email)s, %(notes)s, NOW())
                    """,
                    values,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO mart_owners
                        (id, full_name, company_name, category, mobile_number, email, notes, created_at)
                    VALUES
                        ((SELECT COALESCE(MAX(id), 0) + 1 FROM mart_owners),
                         %(full_name)s, %(company_name)s, %(category)s, %(mobile_number)s, %(email)s, %(notes)s, NOW())
                    """,
                    values,
                )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save Mart Owner consent for %s", email)
        raise HTTPException(status_code=500, detail="Your response could not be saved right now. Please try again.")

    return MartOwnerResponse(full_name=full_name)