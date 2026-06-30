"""
Reads property inventory directly from the same Google Sheet that the
CRM's Property Gallery writes to — no CRM API, no Firebase auth needed.
This is simpler and means there's exactly one source of truth: whatever
you add in the CRM's Property Gallery shows up here within the cache
window below.

Sheet schema (must match the CRM's PROPERTIES_COLUMNS exactly):
  id | name | location | propertyType | furnishing | priceRange |
  description | createdBy | createdAt

Each row is ONE listing at ONE furnishing tier (the CRM doesn't store
raw/semi/fully as three columns — you add three separate rows for the
same project if you want all three tiers represented). This module
groups rows by (location, propertyType) when building a teaser so a
customer asking about "Sector 70, 2BHK" sees all furnishing tiers found
across matching rows.
"""

import logging
import time

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_cache: dict = {"rows": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 120  # re-fetch at most every 2 minutes


def _normalize_private_key(raw: str) -> str:
    """
    Defensive cleanup for common copy-paste artifacts when a PEM private
    key passes through an env var UI: surrounding quotes, literal \\n
    escape sequences, and Windows-style \\r\\n line endings.
    """
    key = raw.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in ("'", '"'):
        key = key[1:-1]
    key = key.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")
    if not key.endswith("\n"):
        key += "\n"
    return key


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": settings.GOOGLE_SERVICE_ACCOUNT_EMAIL.strip(),
            "private_key": _normalize_private_key(settings.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY),
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=_SCOPES,
    )
    return gspread.authorize(creds)


def _fetch_rows() -> list[dict]:
    client = _get_client()
    sheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    ws = sheet.worksheet(settings.SHEET_TAB_PROPERTIES)
    records = ws.get_all_records()  # uses row 1 as headers automatically
    # Only keep rows that actually have an id (skips blank trailing rows)
    return [r for r in records if str(r.get("id", "")).strip()]


def get_all_properties() -> list[dict]:
    """Cached read of the Properties tab. Cache exists purely to avoid
    hammering the Sheets API on every WhatsApp message — 2 minutes is a
    reasonable staleness window for inventory that doesn't change by the
    minute."""
    now = time.monotonic()
    if _cache["rows"] is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["rows"]

    try:
        rows = _fetch_rows()
        _cache["rows"] = rows
        _cache["fetched_at"] = now
        return rows
    except Exception:
        logger.exception("Failed to fetch properties from Google Sheet.")
        # Serve stale cache rather than nothing, if we have it
        return _cache["rows"] or []
