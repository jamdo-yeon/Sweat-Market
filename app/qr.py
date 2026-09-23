from io import BytesIO

import qrcode
from itsdangerous import URLSafeTimedSerializer

from .config import get_secret_key


QR_SECRET = get_secret_key()
QR_SALT = "workout-checkin"


def qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=4,
    )

    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def create_checkin_token(offer_id: int) -> str:
    serializer = URLSafeTimedSerializer(QR_SECRET)

    return serializer.dumps(
        {"offer_id": offer_id},
        salt=QR_SALT,
    )


def verify_checkin_token(
    token: str,
    max_age_seconds: int = 15 * 60,
):
    serializer = URLSafeTimedSerializer(QR_SECRET)

    return serializer.loads(
        token,
        salt=QR_SALT,
        max_age=max_age_seconds,
    )