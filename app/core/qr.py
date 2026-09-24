from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def make_qr_svg(value: str) -> bytes:
    """Build an SVG QR code without requiring a native image library."""

    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
        image_factory=SvgPathImage,
    )
    code.add_data(value)
    code.make(fit=True)

    image = code.make_image()
    output = BytesIO()
    image.save(output)
    return output.getvalue()
