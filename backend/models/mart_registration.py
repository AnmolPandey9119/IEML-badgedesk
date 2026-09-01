"""
models/mart_registration.py
Schemas for the NEW public "Mart Days" registration form only.

Deliberately kept in its own file, separate from models/visitor.py —
nothing in the existing (already-live) request/response models is
touched by this feature. This is an independent, additive module.

Field names here match exactly what "sir" described:
  Type of Buyer, Full Name, Company Name, Designation, Email,
  Phone Number, Address, District, State, Country, Pincode
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# The three buyer types sir specified. Kept as plain string constants
# (not a hard DB enum) so adding a 4th type later is a one-line change
# here, no database migration needed.
BUYER_TYPES = [
    "Overseas buyers",
    "Domestic volume buyers",
    "Buying/Sourcing consultants",
]

# Slug version of each buyer type, stored in the visitor's `category`
# column (same column every other visitor already uses for
# visitor/exhibitor/delegate/etc) so the master console can filter/
# group Mart Days registrants the same way it already groups everyone
# else — no new column, no special-casing needed there.
_BUYER_TYPE_SLUGS = {
    "Overseas buyers": "overseas_buyer",
    "Domestic volume buyers": "domestic_volume_buyer",
    "Buying/Sourcing consultants": "sourcing_consultant",
}


class MartDaysRegisterRequest(BaseModel):
    """Body for POST /api/mart-days/register — the public form's submission."""

    buyer_type: str = Field(..., description="One of BUYER_TYPES exactly")
    full_name: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    designation: Optional[str] = Field(None, max_length=200)
    email: EmailStr
    phone_number: str = Field(..., min_length=6, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    district: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)

    @field_validator("buyer_type")
    @classmethod
    def buyer_type_must_be_valid(cls, v: str) -> str:
        if v not in BUYER_TYPES:
            raise ValueError(f"buyer_type must be one of: {', '.join(BUYER_TYPES)}")
        return v

    def to_category_slug(self) -> str:
        return _BUYER_TYPE_SLUGS[self.buyer_type]


class MartDaysRegisterResponse(BaseModel):
    """
    Returned by POST /api/mart-days/register. urn is shown to the
    registrant immediately on the confirmation screen — useful now
    while email sending isn't wired up yet (Step 2), and stays useful
    afterwards as an on-screen backup in case the email is delayed.
    """

    urn: str
    full_name: str
    buyer_type: str
    email: EmailStr