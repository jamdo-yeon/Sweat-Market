from io import BytesIO

import qrcode


def qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=4,
    )

    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()