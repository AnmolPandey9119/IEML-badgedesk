"""
services/whatsapp_service.py
Sends the Mart Days registration confirmation + e-badge PDF on WhatsApp through AiSensy's
Campaign API (POST https://backend.aisensy.com/campaign/t1/api).

Runs as a FastAPI BackgroundTask right after the registration is saved, exactly
like the confirmation email (see routers/mart_registration.py) -- so a slow or
failing WhatsApp send never delays or breaks a registration. Everything here
returns True/False and NEVER raises.

AiSensy sends only pre-approved TEMPLATE messages, so the wording lives in the
template you create in AiSensy/Meta, not here. This file just fills the
template's {{1}}, {{2}}... in the order given by AISENSY_PARAMS. The number of
values must equal the number of variables in the template, otherwise AiSensy
rejects the request.

Edition / dates / venue come from services/edition_store.py, so the message
updates automatically when the master changes the edition in the admin page.
"""

import logging
import re
from typing import Optional

import httpx

from config import settings
from services import edition_store

logger = logging.getLogger("whatsapp_service")


def normalize_phone(raw: Optional[str]) -> str:
    """
    '+91 98765 43210' / '91-9876543210' / '9876543210' -> '+919876543210'.
    The public form stores '<dial code> <number>', so it normally already has
    a '+'. A bare 10-digit number is treated as Indian (+91), matching
    AiSensy's own default. Returns '' if nothing usable.
    """
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if raw.startswith("+"):
        return f"+{digits}"
    if raw.startswith("00"):
        return f"+{digits[2:]}"
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"
    return f"+{digits}"


def _param_values(full_name: str, urn: str, edition: dict) -> dict:
    return {
        "name": (full_name or "").strip() or "Guest",
        "event": f"{edition['event_name']} ({edition['edition_label']})",
        "edition": edition["edition_label"],
        "dates": edition["dates_long"],
        "timing": edition.get("timing") or "",
        "venue": edition["venue"],
        "co_located": edition.get("co_located_with") or "",
        "urn": urn,
        "badge_link": settings.badge_download_page_url or "",
    }


def build_payload(urn: str, full_name: str, phone: str, edition: Optional[dict] = None) -> dict:
    ed = edition or edition_store.get_edition()
    values = _param_values(full_name, urn, ed)
    # "none" (or blank) = the template has no {{variables}} at all.
    keys = [k.strip() for k in settings.aisensy_params.split(",") if k.strip() and k.strip().lower() != "none"]
    unknown = [k for k in keys if k not in values]
    if unknown:
        raise ValueError(f"AISENSY_PARAMS has unknown name(s): {', '.join(unknown)}")
    # AiSensy rejects empty template values, so fall back to a dash.
    template_params = [values[k] or "-" for k in keys]

    payload = {
        "apiKey": settings.aisensy_api_key,
        "campaignName": settings.aisensy_campaign_name,
        "destination": phone,
        "userName": values["name"],
        "source": "Mart Days Registration",
        "templateParams": template_params,
    }
    if settings.aisensy_attach_badge and settings.backend_public_url:
        base = settings.backend_public_url.rstrip("/")
        payload["media"] = {
            "url": f"{base}/api/mart-days/ebadge/{urn}.pdf",
            "filename": f"{urn}-ebadge.pdf",
        }
    return payload


async def send_mart_days_whatsapp(urn: str, full_name: str, phone: Optional[str]) -> bool:
    missing = []
    if not settings.aisensy_api_key:
        missing.append("AISENSY_API_KEY")
    if not settings.aisensy_campaign_name:
        missing.append("AISENSY_CAMPAIGN_NAME")
    if missing:
        logger.info("%s not set -- WhatsApp is off, skipping (URN %s).", " and ".join(missing), urn)
        return False

    destination = normalize_phone(phone)
    if not destination:
        logger.warning("No usable phone number for URN %s -- WhatsApp skipped.", urn)
        return False

    try:
        payload = build_payload(urn, full_name, destination)
    except Exception:
        logger.exception("Could not build the AiSensy payload for URN %s", urn)
        return False

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(settings.aisensy_api_url, json=payload)
        if resp.status_code >= 400:
            logger.error("AiSensy send failed for URN %s (HTTP %s): %s", urn, resp.status_code, resp.text[:500])
            return False
        logger.info("WhatsApp queued via AiSensy for URN %s to %s", urn, destination)
        return True
    except Exception:
        logger.exception("AiSensy send raised an exception for URN %s", urn)
        return False