"""
Two distinct security checks live here:

1. Admin API key — protects /admin/* routes (pause/resume leads, import
   inventory). Simple shared-secret header, fine for a single-operator
   tool. Upgrade to real JWT/RBAC if you ever add multiple staff users.

2. Meta webhook signature — Meta signs every webhook POST body with your
   app secret (HMAC-SHA256, header `X-Hub-Signature-256`). Verifying this
   is the *real* protection against someone spamming fake messages at
   your webhook URL — much stronger than a fixed shared secret, since the
   signature changes per request body.
"""

import hashlib
import hmac

from fastapi import Header, HTTPException, status

from app.config import settings


def verify_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


def verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    `signature_header` is the value of X-Hub-Signature-256, formatted as
    'sha256=<hex digest>'. Returns True only if it matches what we
    compute from the raw request body using META_APP_SECRET.
    """
    if not signature_header or not settings.META_APP_SECRET:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = signature_header.split("sha256=", 1)[1]
    computed = hmac.new(
        settings.META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, computed)
