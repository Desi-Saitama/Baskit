"""
parser.py — Uses Google Gemini Vision to extract structured order data
from screenshots (JPG/PNG) and PDF invoices from Indian delivery apps.
"""

import io
import json
import re
import os
import pdfplumber
from PIL import Image
from google import genai
from google.genai import types

# ── App metadata ──────────────────────────────────────────────────────────────

APP_CATEGORIES = {
    "zepto":      "groceries",
    "blinkit":    "groceries",
    "instamart":  "groceries",
    "bigbasket":  "groceries",
    "jiomart":    "groceries",
    "swiggy":     "food",
    "zomato":     "food",
}

APP_NAMES = list(APP_CATEGORIES.keys())

# ── Local auto-detection patterns ─────────────────────────────────────────────
# Each app can be identified by seller/GSTIN text appearing in the extracted
# PDF text, and/or by a filename pattern. Order matters: text patterns are far
# more reliable than filenames, so text matches are checked first.
APP_PATTERNS: dict[str, dict] = {
    "zepto": {
        "text":     ["geddit convenience", "geddit convenience private limited"],
        "filename": r"zepto_invoice",
    },
    "blinkit": {
        "text":     ["blink commerce", "blink commerce private limited", "blinkit"],
        "filename": r"forwardinvoice",
    },
    "instamart": {
        "text":     ["kwickbox retail", "instamart", "jiomart instamart"],
        "filename": r"^\d+$",   # purely numeric filename
    },
    "jiomart": {
        "text":     ["reliance retail", "jio mart", "jiomart"],
        "filename": r"^invoice_\d+$",
    },
    "bigbasket": {
        "text":     ["bigbasket", "innovation retail concepts", "supermarket grocery"],
        "filename": r"bigbasket|bb_",
    },
    "swiggy": {
        "text":     ["swiggy", "bundl technologies"],
        "filename": r"swiggy",
    },
    "zomato": {
        "text":     ["zomato"],
        "filename": r"order_id_|^order_id",
    },
}


def detect_app(filename: str, pdf_text: str | None = None) -> str | None:
    """
    Identify which delivery app a file belongs to — WITHOUT any API call.

    Inspects, in order of reliability:
      1. Extracted PDF text (seller/GSTIN patterns).
      2. The filename / stem.

    Returns one of APP_NAMES, or None if no confident match.
    """
    fname = (filename or "").lower()
    stem = fname.rsplit(".", 1)[0] if "." in fname else fname
    text = (pdf_text or "").lower()

    # 1 — text patterns (most reliable)
    if text:
        for app, pat in APP_PATTERNS.items():
            for needle in pat.get("text", []):
                if needle in text:
                    return app

    # 2 — filename patterns
    for app, pat in APP_PATTERNS.items():
        rx = pat.get("filename")
        if not rx:
            continue
        # Match against both full lowercase name and the stem
        if re.search(rx, fname) or re.search(rx, stem):
            return app

    return None


# Special key returned by the model when it cannot identify the app.
UNKNOWN_APP = "unknown"


SYSTEM_PROMPT = """
You are an expert receipt/invoice parser for Indian grocery and food delivery apps.
Extract structured order data from the image or text provided.

Return ONLY a valid JSON object (no markdown, no extra text) with this exact schema:
{
  "detected_app":  "one of: zepto, blinkit, instamart, bigbasket, jiomart, swiggy, zomato, unknown",
  "order_date": "YYYY-MM-DD",          // date of the order; use today if unsure
  "order_id":   "string or null",
  "total_amount": number,              // final amount paid (grand total / bill total)
  "delivery_fee": number,              // 0 if free
  "discount":     number,              // total discount/savings (positive number)
  "items": [
    {
      "name":        "product name",
      "brand":       "brand name or empty string",
      "category":    "one of: Fruits & Vegetables, Dairy & Eggs, Grains & Pulses, Snacks, Beverages, Personal Care, Household, Meat & Seafood, Bakery, Spices & Condiments, Ready to Eat, Restaurant Food, Other",
      "quantity":    "e.g. 1 kg / 2 pcs / 500 g",
      "unit_price":  number,
      "total_price": number
    }
  ]
}

Rules:
- All prices must be numbers (not strings). Strip the ₹ symbol.
- If a field cannot be determined, use null or 0.
- Infer brand from product name if not explicitly stated.
- For restaurant food orders (Swiggy/Zomato), category = "Restaurant Food".
- Dates must be YYYY-MM-DD. If the screenshot says "May 14", use the year from context or current year.
- detected_app: identify the delivery app from the seller name, branding, or
  layout. Use "unknown" only if you genuinely cannot tell. Valid values are
  exactly: zepto, blinkit, instamart, bigbasket, jiomart, swiggy, zomato, unknown.
"""


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set. Please add it in Settings.")
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _annotate_detected_app(data: dict, app_name: str | None, filename: str = "",
                           pdf_text: str | None = None) -> dict:
    """
    Attach a `_detected_app` key to the parsed data dict.

    Resolution order:
      1. Explicitly provided app_name (caller already knew).
      2. Local heuristic detection on text/filename.
      3. The model's `detected_app` field (if present and not unknown).
    Returns the (possibly same) dict with `_detected_app` set (str or None).
    """
    resolved = app_name
    if not resolved:
        resolved = detect_app(filename, pdf_text)
    if not resolved:
        model_app = (data.get("detected_app") or "").strip().lower()
        if model_app and model_app != UNKNOWN_APP and model_app in APP_CATEGORIES:
            resolved = model_app
    data["_detected_app"] = resolved
    return data


def parse_images(image_bytes_list: list[bytes], app_name: str | None = None,
                 filename: str = "") -> dict:
    """Parse one or more screenshot images (bytes) for a single order."""
    client = _get_client()

    if app_name:
        app_line = f"App: {app_name.upper()}\n\n"
    else:
        app_line = (
            "App: UNKNOWN — you must identify the delivery app yourself from the "
            "screenshot and report it in detected_app.\n\n"
        )

    prompt_text = (
        f"{app_line}{SYSTEM_PROMPT}\n\n"
        "Extract all order details from the screenshot(s) below:"
    )

    parts = [prompt_text]
    for img_bytes in image_bytes_list:
        img = Image.open(io.BytesIO(img_bytes))
        # Convert to bytes for the new SDK
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        parts.append(
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")
        )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=parts,
    )
    data = _extract_json(response.text)
    return _annotate_detected_app(data, app_name, filename)


def parse_pdf(pdf_bytes: bytes, app_name: str | None = None,
              filename: str = "") -> dict:
    """Extract text from PDF via pdfplumber, then send to Gemini."""
    client = _get_client()

    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(text_pages)

    # Try local detection first — saves nothing here but lets us tell the model.
    detected = app_name or detect_app(filename, full_text)
    if detected:
        app_line = f"App: {detected.upper()}\n\n"
    else:
        app_line = (
            "App: UNKNOWN — you must identify the delivery app yourself from the "
            "invoice and report it in detected_app.\n\n"
        )

    prompt = (
        f"{app_line}"
        f"{SYSTEM_PROMPT}\n\n"
        f"Invoice text extracted from PDF:\n\n{full_text}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    data = _extract_json(response.text)
    return _annotate_detected_app(data, detected or app_name, filename, full_text)


def parse_mixed(
    image_bytes_list: list[bytes],
    pdf_bytes_list: list[bytes],
    app_name: str | None = None,
    pdf_filename: str = "",
) -> dict:
    """
    Parse a combination of screenshots + PDFs for a single order.
    Prefers PDF if available (more structured), supplements with screenshots.
    """
    if pdf_bytes_list:
        result = parse_pdf(pdf_bytes_list[0], app_name, pdf_filename)
        if image_bytes_list and (not result.get("items")):
            result = parse_images(image_bytes_list, app_name, pdf_filename)
        return result
    return parse_images(image_bytes_list, app_name, pdf_filename)
