"""
BulkWave Pro - Phone Number & Data Validators
"""

import re


def validate_phone_number(phone: str, country_code: str = "") -> tuple[bool, str]:
    """
    Validate and normalize a phone number.
    Returns (is_valid, normalized_number).
    Normalized number is in international format without the '+'.

    Rules:
    - Strip all non-digits (and leading +).
    - Remove leading zeros (local format like 09876543210 → 9876543210).
    - If a country code is configured AND the number does not already start
      with that code, prepend it (local 10-digit → international 12-digit).
    - Final length must be 10–15 digits (WhatsApp requires at least 10).
    - Numbers shorter than 10 digits are always rejected.
    """
    if not phone:
        return False, ""

    # Keep only digits (and the leading + so we can detect international format)
    cleaned = re.sub(r"[^\d+]", "", str(phone).strip())

    # Drop the leading + — we work with raw digit strings
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Remove leading zeros (e.g. 09876543210 → 9876543210)
    cleaned = cleaned.lstrip("0") or cleaned

    # Normalise country code to digits only (handles "91", "+91", " 91")
    cc_digits = re.sub(r"\D", "", country_code) if country_code else ""

    if cc_digits:
        # If the number already carries the country code and is long enough,
        # do NOT prepend again (e.g. "919876543210" with cc "91").
        already_has_cc = (
            cleaned.startswith(cc_digits)
            and len(cleaned) > len(cc_digits) + 6
        )
        if not already_has_cc:
            # The local part (digits before adding country code) must be
            # exactly 10 digits.  Anything shorter is incomplete / a typo
            # — a 9-digit local number would silently become 11 digits after
            # prepending and pass a simple length check, so we catch it here.
            if len(cleaned) < 10:
                return False, cleaned
            cleaned = cc_digits + cleaned

    # Final length: 10–15 digits (ITU-T E.164 max = 15).
    if len(cleaned) < 10 or len(cleaned) > 15:
        return False, cleaned

    if not cleaned.isdigit():
        return False, cleaned

    return True, cleaned


def validate_message(message: str) -> tuple[bool, str]:
    """Validate that a message is not empty and within WhatsApp limits."""
    if not message or not message.strip():
        return False, "Message cannot be empty"
    if len(message) > 65536:
        return False, "Message exceeds maximum length (65536 characters)"
    return True, ""


def validate_excel_file(path: str) -> tuple[bool, str]:
    """Check that the given path points to a valid Excel or CSV file."""
    if not path:
        return False, "No file selected"
    lower = path.lower()
    if not (lower.endswith(".xlsx") or lower.endswith(".xls") or lower.endswith(".csv")):
        return False, "File must be .xlsx, .xls, or .csv"
    import os
    if not os.path.isfile(path):
        return False, "File does not exist"
    return True, ""


def sanitize_phone(phone: str) -> str:
    """Return only digits from a phone string."""
    return re.sub(r"\D", "", str(phone))


def format_phone_display(phone: str) -> str:
    """Return a human-readable phone with a leading +."""
    digits = sanitize_phone(phone)
    return f"+{digits}" if digits else phone
