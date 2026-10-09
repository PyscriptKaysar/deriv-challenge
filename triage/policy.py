"""Safety flags, confidence and escalation. Plain rules, no API.

Runs after retrieval and before generation, because the reply's closing line
depends on whether the ticket is escalated. Every decision also records a
human-readable reason for the debug report.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from triage.classify import Classification
from triage.retrieval import Hit

LOW_CONFIDENCE = 0.6
# A top TF-IDF score at or above this counts as full lexical support.
STRONG_SCORE = 0.3

# The ticket asks about something only a check of their own account can answer:
# why a decision was made, the status of a specific item, or their details.
_ACCOUNT_SPECIFIC = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwhy (?:was|is|did|has|have|were|are)\b.*\bmy\b",
        r"\b(?:status of|where is|where's) my\b",
        r"\bhow long (?:until|till|before) my\b",
        r"\b(?:send|show|tell|give) me my\b",
    )
]


@dataclass(frozen=True)
class Assessment:
    grounded: bool
    confidence: float
    escalate: bool
    flags: tuple[str, ...]
    reasons: tuple[str, ...]


def assess(text: str, classification: Classification, hits: Sequence[Hit]) -> Assessment:
    intent = classification.intent
    grounded = bool(hits) and hits[0].on_intent
    confidence = _confidence(classification, hits)

    flags: list[str] = []
    reasons: list[str] = []
    if intent == "trading_advice_request":
        flags.append("advice_request")
    if not grounded:
        flags.append("insufficient_grounding")
        reasons.append("no help article covers this intent")
    if "withdrawal_issue" in classification.matches:
        flags.append("policy_sensitive")
        reasons.append("withdrawals are policy-sensitive and need an account check")
    if any(p.search(text) for p in _ACCOUNT_SPECIFIC):
        flags.append("account_specific_request")
        reasons.append("asks about their own account, which only an agent can check")
    if confidence < LOW_CONFIDENCE:
        flags.append("low_confidence")
        reasons.append(f"confidence {confidence} is below {LOW_CONFIDENCE}")

    if intent == "trading_advice_request":
        # The refusal is the complete answer; a human adds nothing.
        escalate = False
        reasons = ["trading advice is refused, so no human is needed"]
    else:
        escalate = bool(reasons)
        if not escalate:
            reasons.append("answered from the help article with no risk signals")

    return Assessment(grounded, confidence, escalate, tuple(flags), tuple(reasons))


def _confidence(classification: Classification, hits: Sequence[Hit]) -> float:
    """A simple, documented score in 0..1. Plan 03 tunes the weights.

    40% how sure the classifier is (one intent matched / several / none),
    40% whether an on-intent article was found,
    20% how many words the ticket shares with that article (TF-IDF score).
    """
    certainty = {"single": 1.0, "conflict": 0.7, "none": 0.0}[classification.certainty]
    on_intent = bool(hits) and hits[0].on_intent
    lexical = min(1.0, hits[0].score / STRONG_SCORE) if hits else 0.0
    return round(0.4 * certainty + 0.4 * on_intent + 0.2 * lexical, 2)
