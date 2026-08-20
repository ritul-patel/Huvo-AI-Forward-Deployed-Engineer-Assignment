"""
booking.py

Deterministic site-visit booking simulation for Northstar One, Sector 79 Gurugram.

This is NOT a real external service. It exists so the backend can give the LLM
an authoritative, trustworthy result to relay to the customer.

Design principles:
- The backend decides success/failure. The LLM only relays the result.
- Outcomes are deterministic so tests are repeatable.
- Slot availability is simulated with simple rules (no real calendar).
"""

from __future__ import annotations
import logging
import re
from datetime import datetime, date as date_type

from models import BookingResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Test failure slot — always returns failure; used in tests
# ---------------------------------------------------------------------------
FAIL_DATE = "2099-01-01"
FAIL_TIME = "00:00"

# Sequential booking ID counter (resets on restart — fine for demo)
_booking_counter = 1000

# ---------------------------------------------------------------------------
# Day-of-week name → weekday number map
# Weekdays 0–4 = Mon–Fri; 5–6 = Sat–Sun
# ---------------------------------------------------------------------------
_DAY_NAME_MAP: dict[str, int] = {
    # English
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
    # Hindi transliterated
    "somvar": 0, "mangalvar": 1, "budhvar": 2,
    "guruvar": 3, "shukravar": 4, "shanivar": 5, "ravivar": 6,
    # Common short forms
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}

_RELATIVE_DAY_MAP: dict[str, list[int]] = {
    "tomorrow": [],        # resolved at runtime
    "kal": [],
    "today": [],
    "aaj": [],
    "parso": [],           # day after tomorrow
}

def _resolve_weekday(date_str: str) -> int | None:
    """
    Try to resolve a date string to a weekday number (0=Mon … 6=Sun).
    Returns None if the date string cannot be resolved.
    """
    normalized = date_str.strip().lower()

    # Direct day-name lookup
    if normalized in _DAY_NAME_MAP:
        return _DAY_NAME_MAP[normalized]

    # Relative days
    today = datetime.now().weekday()
    if normalized in ("today", "aaj"):
        return today
    if normalized in ("tomorrow", "kal"):
        return (today + 1) % 7
    if normalized == "parso":
        return (today + 2) % 7

    # Try to parse as an ISO or common date
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            return parsed.weekday()
        except ValueError:
            continue

    # Try extracting a day name from the string (e.g. "this Saturday")
    for day_name, day_num in _DAY_NAME_MAP.items():
        if re.search(r'\b' + day_name + r'\b', normalized):
            return day_num

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def book_site_visit(
    date: str,
    time: str,
    customer_context: dict | None = None,
) -> BookingResult:
    """
    Simulate a site-visit booking.

    Args:
        date:             Requested visit date string (e.g. "Saturday", "2024-08-24")
        time:             Requested visit time string (e.g. "4 PM", "16:00")
        customer_context: Optional customer info (used for logging only)

    Returns:
        BookingResult(success=True, booking_id=...) on success
        BookingResult(success=False, reason=...) on failure
    """
    global _booking_counter

    customer_name = (customer_context or {}).get("name", "unknown")
    logger.info(
        "Booking attempt | customer=%s | date=%s | time=%s",
        customer_name, date, time,
    )

    # ── Deterministic test-failure slot ─────────────────────────────────
    if date.strip() == FAIL_DATE and time.strip() == FAIL_TIME:
        logger.info(
            "Booking FAILED (test slot) | date=%s | time=%s", date, time
        )
        return BookingResult(success=False, reason="slot_unavailable")

    # ── Validity rule ──────────────────────────────────────────────────
    weekday = _resolve_weekday(date)

    if weekday is None:
        # Could not resolve the date — treat as invalid
        logger.warning(
            "Booking FAILED (unresolvable date) | date=%s | time=%s", date, time
        )
        return BookingResult(success=False, reason="invalid_slot")

    # ── Success ──────────────────────────────────────────────────────────
    _booking_counter += 1
    booking_id = f"NS-{_booking_counter}"
    logger.info(
        "Booking SUCCESS | booking_id=%s | date=%s | time=%s",
        booking_id, date, time,
    )
    return BookingResult(
        success=True,
        booking_id=booking_id,
        date=date,
        time=time,
    )


def get_available_slots_hint() -> str:
    """
    Return a natural-language hint about when site visits are available.
    Used by the agent to guide customers toward valid slots.
    """
    return "Site visits at Northstar One are available throughout the week, subject to slot availability."

def cancel_site_visit(booking_id: str) -> bool:
    """
    Simulate cancelling an existing site-visit booking.
    Always returns True for simulation purposes.
    """
    logger.info("Cancellation SUCCESS | booking_id=%s", booking_id)
    return True
