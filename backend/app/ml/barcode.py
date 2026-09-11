"""
Barcode lookup: the most reliable way to read a packaged food.

WHY THIS IS THE PRIMARY INPUT

Barcodes are designed to be machine-read. Shops scan millions a day off
curved, glossy, badly-lit packaging. Read reliability is ~99%, against
~72% for OCR on the same products, and what comes back was transcribed by
a human rather than guessed from pixels.

THE CATCH, WHICH THE UI MUST SURFACE

The ingredients are whatever a contributor recorded, possibly years ago.
Manufacturers reformulate without changing the barcode. So a lookup tells
you what the database HAS ON FILE, not what is in the packet in someone's
hand - and for a severe allergy that gap matters.

This module therefore returns the data age and product name alongside the
ingredients, so the caller can ask the user to confirm rather than
presenting a database record as fact.
"""

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

OFF_API = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
# Open Food Facts asks API clients to identify themselves.
USER_AGENT = "Pona/0.1 (food sensitivity checker)"
TIMEOUT = 12

# Fields we need. Requesting only these keeps the response small.
FIELDS = ",".join([
    "product_name", "brands", "ingredients_text", "ingredients_text_en",
    "allergens_tags", "traces_tags", "last_modified_t", "quantity",
])


class BarcodeNotFound(LookupError):
    """No product for this barcode. Not an error - just unknown."""


@dataclass
class Product:
    code: str
    name: str
    brand: str
    ingredients_text: str
    # Allergen tags the database already holds, in its own taxonomy. Kept
    # as a cross-check against our matcher, never as a replacement: their
    # taxonomy is EU-14 and ours follows the FDA majors.
    declared_allergens: List[str] = field(default_factory=list)
    declared_traces: List[str] = field(default_factory=list)
    last_modified: Optional[str] = None
    source: str = "Open Food Facts"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "brand": self.brand,
            "ingredients_text": self.ingredients_text,
            "declared_allergens": self.declared_allergens,
            "declared_traces": self.declared_traces,
            "last_modified": self.last_modified,
            "source": self.source,
        }


def normalise(code: str) -> str:
    """Strip everything but digits. Scanners emit spaces and dashes."""
    return re.sub(r"\D", "", code or "")


def valid_barcode(code: str) -> bool:
    """EAN-8, UPC-A, EAN-13 and a couple of neighbours."""
    return len(normalise(code)) in (8, 12, 13, 14)


def _clean_tags(tags) -> List[str]:
    """'en:milk' -> 'milk'. Drop language prefixes for display."""
    out = []
    for t in tags or []:
        t = str(t)
        out.append(t.split(":", 1)[1] if ":" in t else t)
    return out


def lookup(code: str) -> Product:
    """
    Fetch a product by barcode.

    Raises BarcodeNotFound when the database has no record - which is
    common and expected, not a failure. Roughly half of catalogued
    products lack usable ingredient text, and fresh or local food has no
    entry at all. The caller falls back to photo or paste.
    """
    code = normalise(code)
    if not valid_barcode(code):
        raise ValueError(f"{code!r} is not a barcode (expected 8-14 digits).")

    url = OFF_API.format(code=urllib.parse.quote(code)) + f"?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            payload = json.loads(r.read())
    except Exception as e:
        raise BarcodeNotFound(f"Could not reach the product database: {e}") from e

    if payload.get("status") != 1 or not payload.get("product"):
        raise BarcodeNotFound(f"No product found for barcode {code}.")

    p = payload["product"]

    # Prefer an explicitly English transcription. Our knowledge base is
    # English-only, so a French ingredient list would silently match
    # almost nothing - better to be honest about what we received.
    text = (p.get("ingredients_text_en") or p.get("ingredients_text") or "").strip()

    ts = p.get("last_modified_t")
    when = None
    if ts:
        try:
            from datetime import datetime, timezone
            when = datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            when = None

    return Product(
        code=code,
        name=(p.get("product_name") or "").strip() or "Unnamed product",
        brand=(p.get("brands") or "").strip(),
        ingredients_text=text,
        declared_allergens=_clean_tags(p.get("allergens_tags")),
        declared_traces=_clean_tags(p.get("traces_tags")),
        last_modified=when,
    )
