"""
conversation.py

In-memory session store and conversation state management.

Each session holds:
- messages: full conversation history (role + content dicts)
- customer_context: CustomerContext instance
- status: "active" | "ended" | "stopped"
- booking_result: last booking attempt result (or None)

Sessions are keyed by UUID strings. This is intentionally simple — the
assignment does not require persistence.
"""

from __future__ import annotations
import uuid
import logging
from typing import Optional
from models import CustomerContext, BookingResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session store — plain dict, lives for the process lifetime
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_session_data() -> dict:
    return {
        "messages": [],            # list of {"role": ..., "content": ...}
        "customer_context": CustomerContext(),
        "status": "active",        # "active" | "ended" | "stopped"
        "booking_result": None,    # BookingResult | None
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_session() -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = _new_session_data()
    logger.info("Session created | session_id=%s", session_id)
    return session_id


def get_session(session_id: str) -> dict | None:
    """Return session data dict or None if not found."""
    return _sessions.get(session_id)


def session_exists(session_id: str) -> bool:
    return session_id in _sessions


def add_message(session_id: str, role: str, content: str) -> None:
    """Append a message to the conversation history."""
    _sessions[session_id]["messages"].append({"role": role, "content": content})


def get_messages(session_id: str) -> list[dict]:
    return _sessions[session_id]["messages"]


def get_customer_context(session_id: str) -> CustomerContext:
    return _sessions[session_id]["customer_context"]


def update_customer_context(session_id: str, updates: dict) -> None:
    """
    Merge explicit updates into customer context using the safe merge method.
    Never overwrites a real value with None.
    """
    ctx = _sessions[session_id]["customer_context"]
    ctx.merge(updates)


def get_status(session_id: str) -> str:
    return _sessions[session_id]["status"]


def set_status(session_id: str, status: str) -> None:
    """Set session status. Valid values: 'active', 'ended', 'stopped'."""
    _sessions[session_id]["status"] = status
    logger.info("Session status updated | session_id=%s | status=%s", session_id, status)


def set_booking_result(session_id: str, result: BookingResult) -> None:
    _sessions[session_id]["booking_result"] = result


def get_booking_result(session_id: str) -> Optional[BookingResult]:
    return _sessions[session_id].get("booking_result")


def is_communication_stopped(session_id: str) -> bool:
    ctx = _sessions[session_id]["customer_context"]
    return ctx.communication_status == "requested_stop"


def end_session(session_id: str) -> None:
    """Mark session as ended (still readable for analytics)."""
    set_status(session_id, "ended")
