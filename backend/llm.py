"""
llm.py

OpenAI integration layer. Uses the stable Chat Completions API
(client.chat.completions.create), which is available across all
recent openai-python versions.

Exposes:
    generate_agent_response(...)  — chat turn for the customer-facing agent
    generate_analytics(...)       — offline analytics extraction from a transcript
"""

from __future__ import annotations
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq, APIError as GroqAPIError, RateLimitError

from prompt import build_agent_prompt, build_analytics_prompt

# Load .env as early as possible — safe to call multiple times
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client — initialised from environment
# ---------------------------------------------------------------------------

def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")
    return Groq(api_key=api_key)


def _get_model() -> str:
    return os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"


# ---------------------------------------------------------------------------
# Agent response (live customer-facing turn)
# ---------------------------------------------------------------------------

def generate_agent_response(
    messages: list[dict],
    customer_context: dict | None = None,
    tool_context: Optional[str] = None,
) -> str:
    """
    Generate the next agent reply for an ongoing conversation.

    Args:
        messages:          Full conversation history as [{"role": ..., "content": ...}].
                           Should NOT include the system message — we build that here.
        customer_context:  Known customer state (only non-null fields).
        tool_context:      Optional string with booking/tool result for this turn.

    Returns:
        Agent reply string.
    """
    system_prompt = build_agent_prompt(
        customer_context=customer_context,
        tool_context=tool_context,
    )

    # System message prepended to the conversation history
    input_messages = [{"role": "system", "content": system_prompt}] + messages

    logger.info(
        "LLM request | model=%s | turns=%d | tool_context=%s",
        _get_model(),
        len(messages),
        bool(tool_context),
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=_get_model(),
            messages=input_messages,  # type: ignore[arg-type]
        )
        reply = response.choices[0].message.content or ""
        logger.info("LLM response received | chars=%d", len(reply))
        return reply
    except RateLimitError as exc:
        logger.warning("Groq rate limit hit: %s", exc)
        raise RateLimitError(exc.message, response=exc.response, body=exc.body) from exc
    except GroqAPIError as exc:
        logger.error("Groq API error: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Analytics (offline, post-conversation)
# ---------------------------------------------------------------------------

def generate_analytics(transcript: str) -> dict:
    """
    Extract structured lead analytics from a full conversation transcript.

    Args:
        transcript: Plain-text conversation transcript.

    Returns:
        Parsed JSON dict matching the analytics schema.

    Raises:
        ValueError: If the model's response is not valid JSON.
        RuntimeError: On OpenAI API errors.
    """
    prompt_text = build_analytics_prompt(transcript)

    logger.info("Analytics LLM request | transcript_chars=%d", len(transcript))

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt_text}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        logger.info("Analytics LLM response received | chars=%d", len(raw))
    except GroqAPIError as exc:
        logger.error("Groq API error during analytics: %s", exc)
        raise RuntimeError(f"Groq error: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Analytics response was not valid JSON: %s", raw[:200])
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc
