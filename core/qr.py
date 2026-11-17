import segno
from django.utils.safestring import mark_safe


def qr_svg(text: str) -> str:
    """An inline, scalable SVG QR code (no image files, no inline styles: CSP-safe)."""
    code = segno.make(text, error="m")
    return mark_safe(code.svg_inline(scale=4, border=2, omitsize=True))  # noqa: S308 - segno output


def card_payload(qr_code: str) -> str:
    return f"TALA:{qr_code}"
