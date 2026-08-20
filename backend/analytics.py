"""
analytics.py

Post-conversation analytics extraction.

Strategy:
1. Load deterministic backend state (CustomerContext + BookingResult) — always accurate.
2. Call the LLM with the full transcript to extract fields the backend doesn't track
   deterministically (name, interest_level, conversation_outcome, summary, etc.).
3. Merge: backend state wins on any field it has. LLM fills the gaps.
4. Validate and return as a ConversationAnalytics Pydantic model.

This approach means the analytics are never wrong about booking status, site visit
dates, or communication status — those come from ground truth, not LLM inference.
"""

from __future__ import annotations
import logging

import conversation as conv
from llm import generate_analytics
from models import ConversationAnalytics, BookingResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transcript builder
# ---------------------------------------------------------------------------

def _build_transcript(messages: list[dict]) -> str:
    """Convert message list into a readable plain-text transcript."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Outcome derivation — deterministic from backend state
# ---------------------------------------------------------------------------

def _derive_outcome(ctx_dict: dict, booking_result: BookingResult | None) -> str | None:
    """
    Derive conversation_outcome from backend state.
    Returns one of: visit_booked / follow_up_scheduled / not_interested /
                    stopped / escalated / in_progress
    """
    comm = ctx_dict.get("communication_status", "active")
    if comm == "requested_stop":
        return "stopped"

    if ctx_dict.get("human_escalation"):
        return "escalated"

    visit_status = ctx_dict.get("site_visit_status", "not_requested")
    if visit_status == "cancelled":
        return "cancelled"
    
    if visit_status == "confirmed" or (visit_status == "confirmed" and booking_result and booking_result.success):
        return "visit_booked"

    if ctx_dict.get("follow_up_required"):
        return "follow_up_scheduled"

    interest = ctx_dict.get("interest_level")
    if interest == "low":
        return "not_interested"

    return "in_progress"


# ---------------------------------------------------------------------------
# Main analytics function
# ---------------------------------------------------------------------------

def get_analytics(session_id: str) -> ConversationAnalytics:
    """
    Generate structured analytics for a session.

    Args:
        session_id: An existing session ID.

    Returns:
        ConversationAnalytics with all fields populated where known.

    Raises:
        KeyError:     If session does not exist.
        ValueError:   If the LLM returns invalid JSON.
        RuntimeError: On LLM API errors.
    """
    session = conv.get_session(session_id)
    if session is None:
        raise KeyError(f"Session not found: {session_id}")

    messages = conv.get_messages(session_id)
    ctx = conv.get_customer_context(session_id)
    booking_result = conv.get_booking_result(session_id)
    ctx_dict = ctx.to_prompt_dict()

    logger.info(
        "Generating analytics | session_id=%s | messages=%d",
        session_id, len(messages),
    )

    # ── Step 1: LLM extraction from transcript ────────────────────────────
    llm_data: dict = {}
    if messages:
        transcript = _build_transcript(messages)
        try:
            llm_data = generate_analytics(transcript)
        except Exception as exc:
            # LLM failure is non-fatal — we still return backend state
            logger.warning(
                "LLM analytics failed, falling back to backend state only | "
                "session_id=%s | error=%s",
                session_id, exc,
            )

    # ── Step 2: Build analytics — backend state wins, LLM fills gaps ─────
    # Helper: prefer backend value, fall back to LLM, fall back to default
    def pick(backend_key: str, llm_key: str | None = None, default=None):
        v = ctx_dict.get(backend_key)
        if v not in (None, "", [], False) or backend_key in (
            "site_visit_requested", "follow_up_required", "human_escalation"
        ):
            # For booleans, trust backend even if False
            if v is not None:
                return v
        if llm_key:
            lv = llm_data.get(llm_key)
            if lv not in (None, "", []):
                return lv
        return default

    # Booking ID comes from booking_result (authoritative), not LLM
    booking_id: str | None = None
    if booking_result and booking_result.success and booking_result.booking_id:
        booking_id = booking_result.booking_id
    elif llm_data.get("booking_id"):
        # Only accept LLM booking_id if backend has no record (shouldn't happen normally)
        booking_id = llm_data.get("booking_id")

    # Conversation outcome — derive from backend, use LLM as fallback
    outcome = _derive_outcome(ctx_dict, booking_result)
    if outcome is None:
        outcome = llm_data.get("conversation_outcome")

    analytics = ConversationAnalytics(
        # Identity — LLM only (backend doesn't parse names)
        name=llm_data.get("name"),
        # Language — backend wins (regex-detected), LLM fills if missing
        language=pick("language", "language"),
        # Qualification — backend wins
        configuration=pick("configuration", "configuration"),
        budget=pick("budget", "budget"),
        purpose=pick("purpose", "purpose"),
        location_preference=pick("location_preference", "location_preference"),
        timeline=pick("timeline", "timeline"),
        # Interest level — LLM is better here (tone/engagement)
        interest_level=llm_data.get("interest_level") or ctx_dict.get("interest_level"),
        # Lead quality — backend scoring wins
        lead_quality=pick("lead_quality", "lead_quality"),
        # Objections — merge both lists, deduplicate
        objections=_merge_objections(
            ctx_dict.get("objections", []),
            llm_data.get("objections", []),
        ),
        # Site visit — all from backend (authoritative)
        site_visit_requested=bool(ctx_dict.get("site_visit_requested", False)),
        site_visit_status=ctx_dict.get("site_visit_status") or llm_data.get("site_visit_status"),
        site_visit_date=pick("site_visit_date", "site_visit_date"),
        site_visit_time=pick("site_visit_time", "site_visit_time"),
        booking_id=booking_id,
        # Follow-up
        follow_up_required=bool(ctx_dict.get("follow_up_required", False)),
        follow_up_time=pick("follow_up_time", "follow_up_time"),
        # Escalation / communication — backend wins
        human_escalation=bool(ctx_dict.get("human_escalation", False)),
        communication_status=pick("communication_status", "communication_status"),
        # Outcome + summary — derived/LLM
        conversation_outcome=outcome,
        summary=llm_data.get("summary"),
    )

    logger.info(
        "Analytics complete | session_id=%s | outcome=%s | lead_quality=%s",
        session_id, analytics.conversation_outcome, analytics.lead_quality,
    )
    return analytics


# ---------------------------------------------------------------------------
# Objection label normalization
# ---------------------------------------------------------------------------
# Maps legacy backend labels (produced by older intent.py) to the current
# controlled-vocabulary labels used by the analytics prompt and frontend.
# This ensures that if any session has residual old-style objection labels
# in its CustomerContext, they merge correctly with LLM output and don't
# appear as duplicates.
_OBJECTION_LABEL_ALIASES: dict[str, str] = {
    "price_too_high": "price",
    "location_concern": "location",
    "not_decided": "undecided",
}

# The complete set of valid objection labels. Anything outside this set
# (raw customer sentences, fabricated labels) is dropped during merge.
_VALID_OBJECTION_LABELS: frozenset[str] = frozenset([
    "price",
    "location",
    "family_decision",
    "timing",
    "undecided",
    "comparison",
])


def _normalize_objection(label: str) -> str | None:
    """
    Normalize an objection label to the canonical controlled vocabulary.
    Returns None if the label is not recognizable (raw sentence, etc.).
    """
    if not label or not isinstance(label, str):
        return None
    normalized = _OBJECTION_LABEL_ALIASES.get(label.strip(), label.strip())
    return normalized if normalized in _VALID_OBJECTION_LABELS else None


def _merge_objections(backend: list, llm: list) -> list[str]:
    """
    Merge and normalize two objection lists, deduplicated, backend first.

    Both lists are normalized through the controlled vocabulary so that
    legacy labels (e.g. "price_too_high") and current labels (e.g. "price")
    are recognized as the same item and not duplicated. Invalid labels
    (raw customer sentences, unknown values) are silently dropped.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw_item in list(backend) + list(llm):
        item = _normalize_objection(raw_item)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
