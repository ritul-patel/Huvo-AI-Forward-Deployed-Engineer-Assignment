"""
models.py

Pydantic request/response models and the CustomerContext data model.
These are shared across routes, conversation, and analytics logic.
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Customer / Lead State
# ---------------------------------------------------------------------------

class CustomerContext(BaseModel):
    """
    Known state about a lead. All fields have sensible defaults.
    None = not yet known. Never set a field to a guessed value.
    """
    name: Optional[str] = None
    language: Optional[str] = None                # "English" / "Hindi" / "Hinglish"
    configuration: Optional[str] = None           # "2 BHK" / "3 BHK"
    budget: Optional[str] = None                  # e.g. "1.8 crore"
    purpose: Optional[str] = None                 # "self-use" / "investment"
    location_preference: Optional[str] = None
    timeline: Optional[str] = None                # e.g. "3 months" / "immediately"
    interest_level: Optional[str] = None          # "high" / "medium" / "low"
    lead_quality: Optional[str] = None            # "hot" / "warm" / "cold"
    objections: List[str] = Field(default_factory=list)
    site_visit_requested: bool = False
    site_visit_date: Optional[str] = None
    site_visit_time: Optional[str] = None
    site_visit_status: str = "not_requested"
    # Booking state machine:
    #   not_requested → requested → awaiting_date → awaiting_time
    #   → ready_to_book → booking_attempted → confirmed
    #                                        → failed
    #                                        → cancelled
    follow_up_required: bool = False
    follow_up_time: Optional[str] = None
    human_escalation: bool = False
    communication_status: str = "active"          # "active" / "requested_stop" / "unresponsive"

    def to_prompt_dict(self) -> dict:
        """Return only fields that have meaningful values (skip None, empty lists, False booleans for optional ones)."""
        result = {}
        for k, v in self.model_dump().items():
            if v is None:
                continue
            if isinstance(v, list) and len(v) == 0:
                continue
            # Always include status fields and booleans that are True
            if isinstance(v, bool) and not v:
                # Skip False booleans unless they're status fields
                if k not in ("site_visit_requested", "follow_up_required", "human_escalation"):
                    continue
            result[k] = v
        return result

    def merge(self, updates: dict) -> None:
        """
        Safely merge a dict of updates into this context.
        - Never overwrites a value with None.
        - For lists (objections), appends new unique items.
        - For strings, only updates if the new value is non-empty.
        """
        for field, value in updates.items():
            if not hasattr(self, field):
                continue
            if value is None or value == "":
                continue
            current = getattr(self, field)
            if isinstance(current, list):
                # Append unique new items
                if isinstance(value, list):
                    for item in value:
                        if item and item not in current:
                            current.append(item)
                elif isinstance(value, str) and value not in current:
                    current.append(value)
            else:
                setattr(self, field, value)


# ---------------------------------------------------------------------------
# API Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Omit to start a new session")
    message: str = Field(..., min_length=1, description="Customer message")


class ChatResponse(BaseModel):
    session_id: str
    message: str                                  # Agent reply
    customer_state: CustomerContext
    booking_status: Optional[str] = None          # populated when a booking attempt occurred
    communication_active: bool = True             # False once stopped
    error: Optional[str] = None


class BookingRequest(BaseModel):
    session_id: str
    date: str
    time: str


class BookingResult(BaseModel):
    success: bool
    booking_id: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    reason: Optional[str] = None                  # e.g. "slot_unavailable"


class AnalyticsResponse(BaseModel):
    session_id: str
    analytics: "ConversationAnalytics"
    error: Optional[str] = None


class ConversationAnalytics(BaseModel):
    """
    Structured lead analytics extracted after a conversation.
    Combines deterministic backend state with LLM-extracted transcript data.
    All fields are None / False / [] when not known — never hallucinated.
    """
    # Lead identity
    name: Optional[str] = None
    language: Optional[str] = None

    # Lead qualification
    configuration: Optional[str] = None           # "2 BHK" / "3 BHK"
    budget: Optional[str] = None
    purpose: Optional[str] = None                 # "self-use" / "investment"
    location_preference: Optional[str] = None
    timeline: Optional[str] = None
    interest_level: Optional[str] = None          # "high" / "medium" / "low"
    lead_quality: Optional[str] = None            # "hot" / "warm" / "cold"
    objections: List[str] = Field(default_factory=list)

    # Site visit
    site_visit_requested: bool = False
    site_visit_status: Optional[str] = None
    site_visit_date: Optional[str] = None
    site_visit_time: Optional[str] = None
    booking_id: Optional[str] = None             # from booking simulation

    # Follow-up
    follow_up_required: bool = False
    follow_up_time: Optional[str] = None

    # Escalation / communication
    human_escalation: bool = False
    communication_status: Optional[str] = None

    # Outcome
    conversation_outcome: Optional[str] = None    # e.g. "visit_booked" / "follow_up" / "not_interested" / "stopped"
    summary: Optional[str] = None
