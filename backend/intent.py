"""
intent.py

Deterministic, rule-based intent and entity extraction from customer messages.

This module does NOT call the LLM. It uses regex and keyword matching to
extract clear, unambiguous signals from text. The LLM handles nuance;
this handles the obvious stuff reliably and cheaply.

Exposed:
    extract_intents(message)       -> IntentResult
    extract_entities(message)      -> EntityResult
    score_lead_quality(ctx)        -> str  ("hot" / "warm" / "cold")
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    stop_communication: bool = False
    site_visit_interest: bool = False
    site_visit_refused: bool = False
    booking_confirmation: bool = False
    human_escalation: bool = False
    follow_up_request: bool = False
    not_interested: bool = False
    busy: bool = False


@dataclass
class EntityResult:
    name: str | None = None
    language: str | None = None
    configuration: str | None = None   # "2 BHK" / "3 BHK"
    budget: str | None = None
    purpose: str | None = None
    timeline: str | None = None
    location_preference: str | None = None
    site_visit_date: str | None = None
    site_visit_time: str | None = None
    objections: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_STOP_PATTERNS = [
    r"don'?t\s+contact",
    r"do\s+not\s+contact",
    r"stop\s+(messaging|contacting|calling|texting)",
    r"remove\s+me",
    r"don'?t\s+call",
    r"do\s+not\s+call",
    r"mujhe\s+contact\s+mat",
    r"contact\s+mat\s+karo",
    r"band\s+karo",
    r"mat\s+karo\s+contact",
    r"unsubscribe",
    r"opt\s+out",
    r"block\s+(me|this)",
]

# Explicit visit REFUSAL patterns — checked FIRST. If any match, the
# message is a refusal and must NOT set site_visit_interest=True.
_VISIT_REFUSAL_PATTERNS = [
    r"(don'?t|do\s+not|not)\s+(want|wish|need|like)\s+(to\s+)?(book|schedule|do|have)?\s*a?\s*(site\s+)?visit",
    r"(don'?t|do\s+not)\s+want\s+(a\s+)?site\s+visit",
    r"no\s+(site\s+)?visit",
    r"visit\s+(nahi|nahin|mat|abhi\s+nahi|abhi\s+nahin)",
    r"site\s+visit\s+(nahi|nahin|abhi\s+nahi|abhi\s+nahin|mat)",
    r"(abhi|pehle)\s+(site\s+visit\s+)?nahi",
    r"not\s+(ready|interested)\s+(for|in)\s+(a\s+)?(site\s+)?visit",
    r"skip\s+(the\s+)?visit",
    r"(maybe|perhaps)\s+later",         # postponing a visit
    r"decide\s+later",
    r"don'?t\s+book",
    r"not\s+now",
    r"not\s+yet",
    r"abhi\s+nahi",
]

_VISIT_PATTERNS = [
    r"site\s+visit",
    r"visit\s+karna",
    r"visit\s+kar(na|na\s+chahta)",
    r"dekhna\s+chahta",
    r"property\s+dekh",
    r"flat\s+dekh",
    r"visit\s+(the\s+)?(property|site|project|flat)",
    r"visit\s+on\b",          # "visit on Monday"
    r"visit\s+(this|next)\b", # "visit this Saturday"
    r"come\s+(and\s+)?see",
    r"aana\s+chahta",
    r"site\s+pe\s+aana",
    r"show\s+me\s+the",
    r"can\s+i\s+(visit|come|see)",
    r"want\s+to\s+visit",
    r"like\s+to\s+visit",
    r"schedule\s+a\s+visit",
    r"plan\s+a\s+visit",
    r"arrange\s+a\s+visit",
    r"book\s+(a\s+)?(site\s+)?visit",
    r"book\s+me\s+for\b",           # "Book me for Saturday"
    r"i'?d\s+like\s+to\s+(visit|come|see|book)",
    r"yes.{0,20}visit",                 # "Yes, I'd like to visit"
]

_BOOKING_CONFIRM_PATTERNS = [
    r"\bconfirm\b",
    r"\bbook\s+(it|the|this|my|a)\b",
    r"\bschedule\s+(it|the|this|my|a)\b",
    r"\bhaan\b",
    r"\bha[n]?\b",
    r"\btheek\s+hai\b",
    r"\btheek\b",
    r"\bok(ay)?\b",
    r"\bsure\b",
    r"\bchalega\b",
    r"\bgo\s+ahead\b",
    r"\bplease\s+book\b",
    r"\bplease\s+confirm\b",
    r"\bfix\s+it\b",
    r"\byes\b",
    r"\bji\b",
    r"\bbilkul\b",
    r"\bzaroor\b",
]

_ESCALATION_PATTERNS = [
    r"\bhuman\b",
    r"\breal\s+person\b",
    r"\breal\s+agent\b",
    r"talk\s+to\s+(a\s+)?(person|agent|someone|representative|manager)",
    r"speak\s+to\s+(a\s+)?(person|agent|someone|representative|manager)",
    r"\brepresentative\b",
    r"\bmanager\b",
    r"\bsales\s+person\b",
    r"connect\s+me\s+(with|to)",
]

_FOLLOW_UP_PATTERNS = [
    r"call\s+(me\s+)?(back|later|tomorrow|next\s+week)",
    r"contact\s+me\s+later",
    r"follow\s+up",
    r"baad\s+mein",
    r"kal\s+(baat|call)",
    r"later\s+contact",
]

_NOT_INTERESTED_PATTERNS = [
    r"\bnot\s+interested\b",
    r"\bno\s+thanks\b",
    r"\bno\s+thank\s+you\b",
    r"don'?t\s+need",
    r"nahi\s+chahiye",
    r"nahi\s+chahie",
    r"nahi\s+chahta",
    r"\bpass\b",
    r"\bnot\s+looking\b",
]

_BUSY_PATTERNS = [
    r"\bbusy\b",
    r"\bcan'?t\s+talk\b",
    r"\bnot\s+a\s+good\s+time\b",
    r"\bbad\s+time\b",
    r"abhi\s+busy",
    r"baad\s+mein",
    r"later\b",
]


def _match_any(text: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def extract_intents(message: str) -> IntentResult:
    """
    Extract intent signals from a customer message.

    IMPORTANT — negation-aware site visit detection:
    A message containing "site visit" is only treated as visit interest if
    it does NOT also match a visit refusal pattern. Refusals are checked
    first and win. This prevents "I don't want a site visit" from setting
    site_visit_interest=True.
    """
    # Refusals win: check them before the positive visit patterns.
    visit_refused = _match_any(message, _VISIT_REFUSAL_PATTERNS)
    visit_interest = (not visit_refused) and _match_any(message, _VISIT_PATTERNS)

    return IntentResult(
        stop_communication=_match_any(message, _STOP_PATTERNS),
        site_visit_interest=visit_interest,
        site_visit_refused=visit_refused,
        booking_confirmation=_match_any(message, _BOOKING_CONFIRM_PATTERNS),
        human_escalation=_match_any(message, _ESCALATION_PATTERNS),
        follow_up_request=_match_any(message, _FOLLOW_UP_PATTERNS),
        not_interested=_match_any(message, _NOT_INTERESTED_PATTERNS),
        busy=_match_any(message, _BUSY_PATTERNS),
    )


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

# Configuration
_CONFIG_RE = re.compile(
    r"\b(2|3|two|three|do|teen)\s*bhk\b",
    re.IGNORECASE,
)
_CONFIG_MAP = {
    "2": "2 BHK", "two": "2 BHK", "do": "2 BHK",
    "3": "3 BHK", "three": "3 BHK", "teen": "3 BHK",
}

# Budget — matches "1.8 crore", "1.8cr", "₹1.8 crore", "180 lakh", "1 crore 80 lakh"
_BUDGET_RE = re.compile(
    r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*(cr(?:ore)?|lakh|l\b)",
    re.IGNORECASE,
)

# Purpose
_PURPOSE_SELF_RE = re.compile(
    r"\b(self[\s-]use|self\s+use|personal\s+use|apne\s+liye|khud\s+ke\s+liye|rehne\s+ke\s+liye|end[\s-]use|family)\b",
    re.IGNORECASE,
)
_PURPOSE_INVEST_RE = re.compile(
    r"\b(invest(?:ment)?|rental|rent\s+out|returns|yield|passive\s+income|nivesh)\b",
    re.IGNORECASE,
)

# Timeline
_TIMELINE_RE = re.compile(
    r"\b(\d+)\s*(month|year|mahine|saal|week)s?\b"
    r"|\b(immediately|asap|urgent(?:ly)?|jaldi|abhi(?!\s+nahi)|as\s+soon\s+as|turant)\b"
    r"|\b(next\s+(month|year|quarter))\b",
    re.IGNORECASE,
)

# Date patterns — simple, won't catch everything but catches the obvious
_DATE_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|somvar|mangalvar|budhvar|guruvar|shukravar|shanivar|ravivar"
    r"|tomorrow|kal|parso|aaj|today"
    r"|\d{1,2}[\s\-/]\w+[\s\-/]\d{2,4}"
    r"|\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b",
    re.IGNORECASE,
)

# Time patterns
_TIME_RE = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)"
    r"|\d{1,2}\s*(?:baje|o'?clock)"
    r"|morning|afternoon|evening|subah|dopahar|shaam"
    r"|noon|midnight)\b",
    re.IGNORECASE,
)

# Language detection — simple heuristic
_HINDI_CHARS_RE = re.compile(r"[\u0900-\u097F]")
_HINGLISH_KEYWORDS = [
    "kya", "hai", "nahi", "haan", "aap", "mujhe", "chahiye", "chahta",
    "kaisa", "kaise", "kitna", "bahut", "accha", "theek", "thoda",
    "lekin", "aur", "bhi", "toh", "woh", "yeh", "iska", "uska",
    "crore", "lakh", "bhk",
]

# Common price objection signals
_OBJECTION_EXPENSIVE_RE = re.compile(
    r"\b(expensive|costly|mahanga|mehnga|zyada|jyada|high\s+price|bahut\s+mehnga"
    r"|too\s+(?:high|expensive|costly)|afford|budget\s+(nahi|nahin|kam))\b",
    re.IGNORECASE,
)
_OBJECTION_LOCATION_RE = re.compile(
    r"\b(too\s+far|bahut\s+door|location\s+(nahi|theek|acchi\s+nahi)"
    r"|sector\s+\d+\s+nahi|not\s+(near|close|convenient))\b",
    re.IGNORECASE,
)
_OBJECTION_UNSURE_RE = re.compile(
    r"\b(not\s+sure|soch\s+raha|think\s+about|consider\s+(?:it|this)"
    r"|dekhna\s+hai|decide\s+nahi|pata\s+nahi)\b",
    re.IGNORECASE,
)


def _detect_language(message: str) -> str | None:
    """Heuristic language detection."""
    if _HINDI_CHARS_RE.search(message):
        # Pure Devanagari script → Hindi
        ascii_ratio = sum(1 for c in message if ord(c) < 128) / max(len(message), 1)
        if ascii_ratio < 0.3:
            return "Hindi"
        return "Hinglish"

    lower = message.lower()
    hinglish_hits = sum(1 for kw in _HINGLISH_KEYWORDS if re.search(r'\b' + kw + r'\b', lower))
    if hinglish_hits >= 2:
        return "Hinglish"

    # If it's clearly English words
    words = lower.split()
    if len(words) >= 2 and hinglish_hits == 0:
        return "English"

    return None


def _extract_budget(message: str) -> str | None:
    """Extract budget as a readable string, e.g. '1.8 crore'."""
    match = _BUDGET_RE.search(message)
    if not match:
        return None
    amount = match.group(1)
    unit = match.group(2).lower()
    if unit.startswith("cr"):
        return f"{amount} crore"
    if unit in ("lakh", "l"):
        # Convert large lakh amounts to crore for readability
        try:
            val = float(amount)
            if val >= 100:
                return f"{val / 100:.2f} crore".rstrip("0").rstrip(".")
        except ValueError:
            pass
        return f"{amount} lakh"
    return f"{amount} {unit}"


def _extract_timeline(message: str) -> str | None:
    match = _TIMELINE_RE.search(message)
    if not match:
        return None
    val = match.group(0).strip().lower()
    val = val.replace("mahine", "months").replace("saal", "years").replace("jaldi", "immediately").replace("abhi", "immediately").replace("turant", "immediately")
    return val


# Family/decision-related objection patterns
_OBJECTION_FAMILY_RE = re.compile(
    r"\b(discuss\s+\w*\s*with\s+(my\s+)?(family|wife|husband|spouse|parents|partner)"
    r"|family\s+(decision|baat|se\s+baat|approval|consent|permission|se\s+pooch)"
    r"|ghar\s+mein\s+baat"
    r"|pehle\s+(family|ghar)\s+se"
    r"|need\s+(my\s+)?(family|wife|husband|spouse|parents|partner|ghar)\s+(approval|consent|permission|opinion|baat)"
    r"|need\s+to\s+(ask|check|consult)\s+my\s+(family|wife|husband|spouse|parents|partner)"
    r"|get\s+(my\s+)?(family|wife|husband|spouse|parents)\s+(approval|opinion|consent))",
    re.IGNORECASE,
)


def _extract_objections(message: str) -> list[str]:
    """
    Extract property/sales objections as normalized category labels.

    Labels are intentionally aligned with the analytics prompt vocabulary:
        "price"           — too expensive, budget concern
        "location"        — location concern
        "family_decision" — needs to discuss with family/spouse
        "undecided"       — not sure, need to think

    NOTE: A site-visit refusal is NOT an objection. It is handled by
    intent detection (visit_refused) and belongs to site_visit_status.
    """
    objections = []
    if _OBJECTION_EXPENSIVE_RE.search(message):
        objections.append("price")
    if _OBJECTION_LOCATION_RE.search(message):
        objections.append("location")
    if _OBJECTION_FAMILY_RE.search(message):
        objections.append("family_decision")
    if _OBJECTION_UNSURE_RE.search(message):
        objections.append("undecided")
    return objections


def extract_entities(message: str) -> EntityResult:
    """Extract structured entities from a customer message."""
    result = EntityResult()

    # Language
    result.language = _detect_language(message)

    # Configuration
    config_match = _CONFIG_RE.search(message)
    if config_match:
        key = config_match.group(1).lower()
        result.configuration = _CONFIG_MAP.get(key, f"{key} BHK".upper())

    # Budget
    result.budget = _extract_budget(message)

    # Purpose
    if _PURPOSE_SELF_RE.search(message):
        result.purpose = "self-use"
    elif _PURPOSE_INVEST_RE.search(message):
        result.purpose = "investment"

    # Timeline
    result.timeline = _extract_timeline(message)

    # Site visit date/time
    date_match = _DATE_RE.search(message)
    if date_match:
        result.site_visit_date = date_match.group(0).strip()

    time_match = _TIME_RE.search(message)
    if time_match:
        result.site_visit_time = time_match.group(0).strip()

    # Objections
    result.objections = _extract_objections(message)

    return result


# ---------------------------------------------------------------------------
# Lead quality scoring
# ---------------------------------------------------------------------------

def score_lead_quality(ctx_dict: dict) -> str:
    """
    Score lead quality based on known context fields.
    Returns "hot", "warm", or "cold".

    Hot:  budget known + configuration known + strong intent signals
    Cold: no useful info or stop-communication
    Warm: everything else
    """
    if ctx_dict.get("communication_status") == "requested_stop":
        return "cold"

    score = 0

    if ctx_dict.get("configuration"):
        score += 2
    if ctx_dict.get("budget"):
        score += 2
    if ctx_dict.get("purpose"):
        score += 1
    if ctx_dict.get("timeline"):
        score += 2
    if ctx_dict.get("site_visit_requested") or ctx_dict.get("site_visit_status") in ("requested", "confirmed"):
        score += 3
    if ctx_dict.get("site_visit_status") == "confirmed":
        score += 2
    if ctx_dict.get("interest_level") == "high":
        score += 2
    elif ctx_dict.get("interest_level") == "medium":
        score += 1

    objections = ctx_dict.get("objections", [])
    score -= len(objections)

    if score >= 7:
        return "hot"
    if score >= 3:
        return "warm"
    return "cold"
