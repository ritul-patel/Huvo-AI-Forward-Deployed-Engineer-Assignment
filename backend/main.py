"""
main.py

FastAPI application entry point.

Endpoints:
    GET  /health
    POST /chat
    POST /book
    POST /sessions/{session_id}/end
    POST /analytics/{session_id}

Run with:
    uvicorn main:app --reload
"""

from __future__ import annotations
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from groq import RateLimitError

import conversation as conv
from models import (
    ChatRequest,
    ChatResponse,
    BookingRequest,
    BookingResult,
    AnalyticsResponse,
    ConversationAnalytics,
)
from booking import book_site_visit, get_available_slots_hint
from llm import generate_agent_response
from analytics import get_analytics
from intent import extract_intents, extract_entities, score_lead_quality

# ---------------------------------------------------------------------------
# Config & logging
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Northstar One AI Sales Agent",
    description="FastAPI backend for the Huvo AI Forward Deployed Engineer assignment.",
    version="1.0.0",
)

# CORS — allow the dev frontend during local development
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Flow:
        1.  Resolve / create session
        2.  Stop-communication guard — short-circuit if customer opted out
        3.  Extract intents and entities from the message (deterministic, no LLM)
        4.  Apply entity updates to customer context immediately
        5.  Apply intent-driven state updates (stop, escalation, visit interest)
        6.  Detect booking intent → attempt booking → build tool_context
        7.  Call LLM with full system prompt + conversation history
        8.  Store assistant reply
        9.  Update lead quality score
        10. Return structured response
    """
    # 1. Resolve session ------------------------------------------------
    session_id = request.session_id
    if not session_id or not conv.session_exists(session_id):
        session_id = conv.create_session()
        logger.info("New session | session_id=%s", session_id)
    else:
        logger.info("Existing session | session_id=%s", session_id)

    # 2. Stop-communication guard ---------------------------------------
    if conv.is_communication_stopped(session_id):
        logger.info("Message blocked — communication stopped | session_id=%s", session_id)
        ctx = conv.get_customer_context(session_id)
        return ChatResponse(
            session_id=session_id,
            message=(
                "You've previously asked us not to contact you. We respect that. "
                "If you ever change your mind, feel free to reach out."
            ),
            customer_state=ctx,
            communication_active=False,
        )

    # 3. Extract intents and entities (deterministic, zero-latency) -----
    intents = extract_intents(request.message)
    entities = extract_entities(request.message)

    logger.info(
        "Intents | session=%s | stop=%s | visit=%s | confirm=%s | escalate=%s",
        session_id,
        intents.stop_communication,
        intents.site_visit_interest,
        intents.booking_confirmation,
        intents.human_escalation,
    )
    logger.info(
        "Entities | session=%s | lang=%s | config=%s | budget=%s | date=%s | time=%s",
        session_id,
        entities.language,
        entities.configuration,
        entities.budget,
        entities.site_visit_date,
        entities.site_visit_time,
    )

    # 4. Apply entity updates to customer context -----------------------
    entity_updates: dict = {}
    if entities.language:
        entity_updates["language"] = entities.language
    if entities.configuration:
        entity_updates["configuration"] = entities.configuration
    if entities.budget:
        entity_updates["budget"] = entities.budget
    if entities.purpose:
        entity_updates["purpose"] = entities.purpose
    if entities.timeline:
        entity_updates["timeline"] = entities.timeline
    if entities.site_visit_date:
        entity_updates["site_visit_date"] = entities.site_visit_date
    if entities.site_visit_time:
        entity_updates["site_visit_time"] = entities.site_visit_time
    if entities.objections:
        entity_updates["objections"] = entities.objections

    # If the customer provided both date AND time, they clearly want a visit —
    # treat as implicit visit intent even without an explicit visit keyword.
    if entities.site_visit_date and entities.site_visit_time:
        intents.site_visit_interest = True

    if entity_updates:
        conv.update_customer_context(session_id, entity_updates)

    tool_context: str | None = None
    booking_status: str | None = None

    # 5. Intent-driven state updates ------------------------------------
    if intents.stop_communication:
        conv.update_customer_context(session_id, {"communication_status": "requested_stop"})
        conv.set_status(session_id, "stopped")
        logger.info("Communication stopped by customer | session_id=%s", session_id)

    if intents.site_visit_refused:
        ctx_now = conv.get_customer_context(session_id)
        from booking import cancel_site_visit
        booking_res = conv.get_booking_result(session_id)
        
        # If there is ANY existing booking, treat refusal as a cancellation
        if ctx_now.site_visit_status in ("confirmed", "cancelled") or (booking_res and booking_res.booking_id):
            if booking_res and booking_res.booking_id:
                if cancel_site_visit(booking_res.booking_id):
                    conv.update_customer_context(session_id, {
                        "site_visit_status": "cancelled",
                    })
                    tool_context = (
                        "BOOKING CANCELLED.\n"
                        f"Booking ID {booking_res.booking_id} has been cancelled successfully.\n"
                        "Acknowledge the cancellation to the customer."
                    )
        else:
            # Only reset to not_requested if no booking ever existed
            conv.update_customer_context(session_id, {
                "site_visit_requested": False,
                "site_visit_status": "not_requested",
            })
    elif intents.site_visit_interest:
        ctx_now = conv.get_customer_context(session_id)
        # Only advance if not already in a later state
        if ctx_now.site_visit_status == "not_requested":
            new_status = _advance_booking_state(ctx_now)
            conv.update_customer_context(session_id, {
                "site_visit_requested": True,
                "site_visit_status": new_status,
            })

    if intents.human_escalation:
        conv.update_customer_context(session_id, {"human_escalation": True})

    if intents.follow_up_request:
        conv.update_customer_context(session_id, {"follow_up_required": True})

    # 6. Add user message to history AFTER state updates ---------------
    # (So the system prompt built in step 7 reflects the latest context)
    conv.add_message(session_id, "user", request.message)

    # 7. Booking intent → simulation → tool_context --------------------

    if not intents.stop_communication:
        # Re-evaluate state after entity updates
        ctx_latest = conv.get_customer_context(session_id)
        new_status = _advance_booking_state(ctx_latest)
        if new_status != ctx_latest.site_visit_status:
            conv.update_customer_context(session_id, {"site_visit_status": new_status})
            logger.info(
                "Booking state → %s | session=%s", new_status, session_id
            )

        booking_result = _maybe_book(session_id, intents)
        if booking_result is not None:
            conv.set_booking_result(session_id, booking_result)
            if booking_result.success:
                tool_context = (
                    f"BOOKING SUCCEEDED.\n"
                    f"Booking ID: {booking_result.booking_id}\n"
                    f"Date: {booking_result.date}\n"
                    f"Time: {booking_result.time}\n"
                    "Confirm the booking to the customer using exactly these details. "
                    "Do not alter the booking ID, date, or time."
                )
                conv.update_customer_context(session_id, {
                    "site_visit_status": "confirmed",
                    "site_visit_date": booking_result.date,
                    "site_visit_time": booking_result.time,
                })
                booking_status = f"confirmed:{booking_result.booking_id}"
                logger.info(
                    "Booking confirmed | session_id=%s | id=%s",
                    session_id, booking_result.booking_id,
                )
            else:
                slots_hint = get_available_slots_hint()
                tool_context = (
                    f"BOOKING FAILED.\n"
                    f"Reason: {booking_result.reason}\n"
                    f"Available slots hint: {slots_hint}\n"
                    "Do NOT tell the customer the slot is confirmed. "
                    "Explain politely that it could not be booked. "
                    "If the reason is slot_unavailable, mention that site visits "
                    "are only available on weekends (Saturday and Sunday) and ask "
                    "the customer to pick a weekend slot. "
                    "If the reason is invalid_slot, ask the customer to share a "
                    "specific date or day."
                )
                conv.update_customer_context(session_id, {
                    "site_visit_status": "failed",
                })
                booking_status = f"failed:{booking_result.reason}"
                logger.info(
                    "Booking failed | session_id=%s | reason=%s",
                    session_id, booking_result.reason,
                )

    # 8. Call LLM -------------------------------------------------------
    customer_ctx = conv.get_customer_context(session_id)
    messages = conv.get_messages(session_id)

    try:
        reply = generate_agent_response(
            messages=messages,
            customer_context=customer_ctx.to_prompt_dict(),
            tool_context=tool_context,
        )
    except RateLimitError:
        logger.warning("Rate limit hit | session_id=%s", session_id)
        raise HTTPException(
            status_code=429,
            detail="The AI service is temporarily rate-limited. Please wait a moment and try again.",
        )
    except Exception as exc:
        logger.error("LLM call failed | session_id=%s | error=%s", session_id, exc)
        raise HTTPException(status_code=502, detail="LLM service unavailable. Please try again.")

    # 9. Store assistant reply ------------------------------------------
    conv.add_message(session_id, "assistant", reply)

    # 10. Update lead quality ------------------------------------------
    ctx = conv.get_customer_context(session_id)
    quality = score_lead_quality(ctx.to_prompt_dict())
    conv.update_customer_context(session_id, {"lead_quality": quality})

    # 11. Return --------------------------------------------------------
    ctx = conv.get_customer_context(session_id)
    return ChatResponse(
        session_id=session_id,
        message=reply,
        customer_state=ctx,
        booking_status=booking_status,
        communication_active=not conv.is_communication_stopped(session_id),
    )


# ---------------------------------------------------------------------------
# Direct booking endpoint — for explicit / test booking calls
# ---------------------------------------------------------------------------

@app.post("/book", response_model=BookingResult)
def book(request: BookingRequest):
    """
    Directly attempt a site-visit booking for a session.
    Useful for testing the booking simulation independently.
    """
    if not conv.session_exists(request.session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    ctx = conv.get_customer_context(request.session_id)
    result = book_site_visit(
        date=request.date,
        time=request.time,
        customer_context=ctx.to_prompt_dict(),
    )
    conv.set_booking_result(request.session_id, result)
    if result.success:
        conv.update_customer_context(request.session_id, {
            "site_visit_status": "confirmed",
            "site_visit_date": result.date,
            "site_visit_time": result.time,
        })
    else:
        conv.update_customer_context(request.session_id, {"site_visit_status": "failed"})

    return result


# ---------------------------------------------------------------------------
# End session
# ---------------------------------------------------------------------------

@app.post("/sessions/{session_id}/end")
def end_session(session_id: str, include_analytics: bool = False):
    """Mark a session as ended. Optionally return analytics."""
    if not conv.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    conv.end_session(session_id)
    logger.info("Session ended | session_id=%s", session_id)

    response: dict = {"session_id": session_id, "status": "ended"}

    if include_analytics:
        try:
            result: ConversationAnalytics = get_analytics(session_id)
            response["analytics"] = result.model_dump()
        except Exception as exc:
            logger.error("Analytics failed at end | session_id=%s | error=%s", session_id, exc)
            response["analytics_error"] = str(exc)

    return response


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.post("/analytics/{session_id}", response_model=AnalyticsResponse)
def analytics(session_id: str):
    """
    Generate structured lead analytics from a session's conversation history.
    Can be called at any point after at least one exchange, or after /end.
    """
    if not conv.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        result: ConversationAnalytics = get_analytics(session_id)
        return AnalyticsResponse(session_id=session_id, analytics=result)
    except ValueError as exc:
        logger.error("Analytics parse error | session_id=%s | error=%s", session_id, exc)
        raise HTTPException(status_code=502, detail=f"Analytics model error: {exc}")
    except RuntimeError as exc:
        logger.error("Analytics LLM error | session_id=%s | error=%s", session_id, exc)
        raise HTTPException(status_code=502, detail="LLM service unavailable.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _advance_booking_state(ctx) -> str:
    """
    Pure function: given the current customer context, return what the
    booking state SHOULD be right now.

    State machine:
        not_requested
            ↓  (site_visit_requested=True)
        requested
            ↓  (date known)
        awaiting_time
            ↓  (time also known)
        ready_to_book
            ↓  (confirmation signal received → _maybe_book runs)
        booking_attempted → confirmed | failed
    """
    status = ctx.site_visit_status

    # Terminal states — don't change
    if status in ("confirmed", "cancelled"):
        return status

    # Not yet expressed interest
    if not ctx.site_visit_requested and status == "not_requested":
        return "not_requested"

    has_date = bool(ctx.site_visit_date)
    has_time = bool(ctx.site_visit_time)

    if has_date and has_time:
        # Both pieces in hand — only move forward, not backward
        if status in ("not_requested", "requested", "awaiting_date", "awaiting_time", "failed"):
            return "ready_to_book"
        return status

    if has_date and not has_time:
        if status in ("not_requested", "requested", "awaiting_date"):
            return "awaiting_time"
        return status

    if not has_date:
        if status in ("not_requested",):
            return "requested"
        if status in ("requested",):
            return "awaiting_date"
        return status

    return status


def _maybe_book(session_id: str, intents) -> BookingResult | None:
    """
    Attempt a booking when all conditions are met:
    - State is ready_to_book (both date and time known)
    - Customer sent a confirmation signal
    - Not already confirmed

    The booking simulation result is authoritative. The LLM only relays it.
    """
    ctx = conv.get_customer_context(session_id)

    # Don't re-book if already confirmed
    if ctx.site_visit_status == "confirmed":
        return None

    has_confirmation = intents.booking_confirmation
    ready = ctx.site_visit_status == "ready_to_book"
    has_date = bool(ctx.site_visit_date)
    has_time = bool(ctx.site_visit_time)

    if ready and has_date and has_time:
        conv.update_customer_context(session_id, {"site_visit_status": "booking_attempted"})
        logger.info(
            "Booking attempt triggered | session=%s | date=%s | time=%s",
            session_id, ctx.site_visit_date, ctx.site_visit_time,
        )
        return book_site_visit(
            date=ctx.site_visit_date,        # type: ignore[arg-type]
            time=ctx.site_visit_time,        # type: ignore[arg-type]
            customer_context=ctx.to_prompt_dict(),
        )

    return None
