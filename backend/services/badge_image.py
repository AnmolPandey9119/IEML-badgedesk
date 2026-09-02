"""
services/badge_image.py
Composes the e-badge PNG attached to the Mart Days confirmation email.

This does NOT invent a new design. It takes the ACTUAL badge card image
(assets/badge_templates/mart_days_card.png -- exported from the same
PDF used for physical printing, front + back both, exactly as supplied)
and overlays only what the physical printer overlays on the pre-printed
card: Name, Company, QR code, URN. Same order top-to-bottom as
frontend/js/print.js + frontend/css/print.css use for the physical
badge: Name -> Organization -> QR -> URN.

The back side of the card (rules/visitor-category panel) is part of
the same template image and is left completely untouched -- it just
rides along below the overlaid front section.

POSITIONING: all coordinates are stored as FRACTIONS of the template
image's width/height (not fixed pixel numbers). This means the exact
same code keeps working correctly even if the template PNG is ever
re-exported at a different resolution -- nobody has to touch the
numbers here again for that. These fractions were measured directly
against the current mart_days_card.png; if IEML changes the badge
artwork/layout, re-measure and update ONLY the constants below.
"""

import logging
import os
from io import BytesIO
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("badge_image")

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "badge_templates")
TEMPLATE_PATH = os.path.join(_ASSETS_DIR, "mart_days_card.png")

# ---------------------------------------------------------------
# Layout, as fractions of the template's (width, height).
# Measured against the front white-space area of mart_days_card.png.
# ---------------------------------------------------------------
NAME_Y_FRAC = 0.1901
COMPANY_Y_FRAC = 0.2057
QR_TOP_FRAC = 0.2183
QR_SIZE_FRAC = 0.2538          # relative to width (QR box is square)
URN_GAP_FRAC = 0.0125          # extra gap below QR before URN line
CENTER_X_FRAC = 0.5

NAME_FONT_FRAC = 0.0288        # relative to width
COMPANY_FONT_FRAC = 0.0220
URN_FONT_FRAC = 0.0237

TEXT_COLOR = (20, 20, 20)
SUBTEXT_COLOR = (40, 40, 40)

_template_cache: Optional[Image.Image] = None


def _load_template() -> Image.Image:
    """Loads the template once and reuses it for every badge (it's
    read-only -- we always .copy() before drawing on it)."""
    global _template_cache
    if _template_cache is None:
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(
                f"Badge template not found at {TEMPLATE_PATH}. "
                "Make sure assets/badge_templates/mart_days_card.png "
                "is present in the deployed backend."
            )
        _template_cache = Image.open(TEMPLATE_PATH).convert("RGB")
    return _template_cache


def _font(size_px: float) -> ImageFont.ImageFont:
    size_px = max(int(size_px), 1)
    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:
        # Older Pillow without the `size` kwarg on load_default().
        return ImageFont.load_default()


def build_ebadge_png(urn: str, name: str, company: str, mobile: Optional[str] = None, email: Optional[str] = None) -> bytes:
    """
    Returns PNG bytes of the composed e-badge: the real card template
    with Name / Company / QR / URN overlaid in the same positions the
    physical printer uses. QR content matches frontend/js/print.js and
    email_service.py exactly (URN first line, then Name/Mobile/Email
    if present) so this and a physical-counter badge always scan to
    the identical thing.
    """
    template = _load_template().copy()
    draw = ImageDraw.Draw(template)
    W, H = template.size
    cx = int(W * CENTER_X_FRAC)

    display_name = (name or "").strip().upper()
    display_company = (company or "").strip().upper()

    draw.text((cx, int(H * NAME_Y_FRAC)), display_name, font=_font(W * NAME_FONT_FRAC), fill=TEXT_COLOR, anchor="mm")
    if display_company:
        draw.text((cx, int(H * COMPANY_Y_FRAC)), display_company, font=_font(W * COMPANY_FONT_FRAC), fill=SUBTEXT_COLOR, anchor="mm")

    qr_lines = [f"URN: {urn}"]
    if name:
        qr_lines.append(f"Name: {name}")
    if mobile:
        qr_lines.append(f"Mobile: {mobile}")
    if email:
        qr_lines.append(f"Email: {email}")
    qr_text = "\n".join(qr_lines)

    qr_size = int(W * QR_SIZE_FRAC)
    qr_top = int(H * QR_TOP_FRAC)
    qr_img = qrcode.make(qr_text).convert("RGB").resize((qr_size, qr_size))
    template.paste(qr_img, (cx - qr_size // 2, qr_top))

    urn_y = qr_top + qr_size + int(H * URN_GAP_FRAC)
    draw.text((cx, urn_y), f"URN: {urn}", font=_font(W * URN_FONT_FRAC), fill=TEXT_COLOR, anchor="mm")

    buffer = BytesIO()
    template.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()