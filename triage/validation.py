"""VALIDATE_OUTPUT: check every result before it's written.

Hard failures (bad schema, unknown article, wrong ticket, advice not refused)
replace the result with a safe fallback, so every ticket still gets exactly one
valid result. Unsupported claims (numbers not in the sources, promise wording)
keep the reply but mark it ungrounded, flag it and escalate it.
"""

import re
from collections.abc import Iterable

from pydantic import ValidationError

from triage.generate import HANDOFF, REFUSAL
from triage.schemas import TicketResult

_REFUSAL = re.compile(r"\b(?:not able to|unable to|can't|cannot|won't) (?:provide|give|offer|tell)\b", re.IGNORECASE)
_ADVICE = re.compile(
    r"\byou should (?:buy|sell|invest)\b|\bwill (?:go up|go down|rise|fall)\b|\bis a good (?:buy|investment)\b|\bbuy now\b",
    re.IGNORECASE,
)
_PROMISE = re.compile(
    r"\bguaranteed\b|\bwe guarantee\b|\bwill be (?:approved|processed|credited|completed|released|refunded)\b|\bdefinitely\b|\bwithin \d+",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def validate_output(raw: dict, ticket_id: str, kb_ids: set[str], source_text: str) -> tuple[TicketResult, list[str]]:
    """Return a valid result and the list of problems found (empty if none)."""
    try:
        result = TicketResult.model_validate(raw)
    except ValidationError as e:
        return _fallback(raw, ticket_id, kb_ids, "schema_invalid"), [f"schema: {e.errors()[0]['msg']}"]

    if result.ticket_id != ticket_id:
        return _fallback(raw, ticket_id, kb_ids, "ticket_mismatch"), [f"ticket_id {result.ticket_id!r} != {ticket_id!r}"]
    unknown = [a for a in result.retrieved_articles if a not in kb_ids]
    if unknown:
        return _fallback(raw, ticket_id, kb_ids, "unknown_article"), [f"unknown article IDs {unknown}"]
    if _ADVICE.search(result.reply_draft):
        return _fallback(raw, ticket_id, kb_ids, "advice_given"), ["reply contains trading-advice wording"]
    if result.intent == "trading_advice_request" and not _REFUSAL.search(result.reply_draft):
        return _fallback(raw, ticket_id, kb_ids, "advice_not_refused"), ["trading-advice request not refused"]

    problems = unsupported_claims(result.reply_draft, source_text)
    if problems:
        flags = list(dict.fromkeys([*result.safety_flags, "insufficient_grounding"]))
        result = result.model_copy(update={"grounded": False, "needs_human_escalation": True, "safety_flags": flags})
    return result, problems


def unsupported_claims(reply: str, source_text: str) -> list[str]:
    """Heuristic: catches common invented facts; it can't prove a reply is grounded."""
    problems = [f"number {n!r} not in the sources" for n in _NUMBER.findall(reply) if n not in source_text]
    problems += [f"promise wording {m.group(0)!r}" for m in _PROMISE.finditer(reply)]
    return problems


def _fallback(raw: dict, ticket_id: str, kb_ids: set[str], flag: str) -> TicketResult:
    is_advice = isinstance(raw, dict) and raw.get("intent") == "trading_advice_request"
    articles = raw.get("retrieved_articles") if isinstance(raw, dict) else None
    known = [a for a in _as_list(articles) if a in kb_ids][:3] or [sorted(kb_ids)[0]]
    return TicketResult(
        ticket_id=ticket_id,
        intent="trading_advice_request" if is_advice else "other",
        retrieved_articles=list(dict.fromkeys(known)),
        reply_draft=REFUSAL if is_advice else HANDOFF,
        grounded=False,
        confidence=0.0,
        needs_human_escalation=True,
        safety_flags=[*(["advice_request"] if is_advice else []), "insufficient_grounding", flag],
    )


def _as_list(value: object) -> Iterable[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
