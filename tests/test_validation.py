import pytest

from triage.generate import HANDOFF, REFUSAL
from triage.validation import validate_output

KB_IDS = {"A1", "A2", "A3", "A4", "A5"}
SOURCE = "Card deposits are usually instant, but may be delayed by issuer checks."


def good(**overrides):
    data = {
        "ticket_id": "T1",
        "intent": "deposit_issue",
        "retrieved_articles": ["A1"],
        "reply_draft": "Card deposits are usually instant.",
        "grounded": True,
        "confidence": 0.9,
        "needs_human_escalation": False,
        "safety_flags": [],
    }
    return data | overrides


def check(raw, ticket_id="T1"):
    return validate_output(raw, ticket_id, KB_IDS, SOURCE)


def test_good_result_passes_unchanged():
    result, problems = check(good())
    assert problems == [] and result.model_dump() == good()


@pytest.mark.parametrize(
    ("overrides", "flag"),
    [
        ({"intent": "refund"}, "schema_invalid"),
        ({"confidence": 1.5}, "schema_invalid"),
        ({"retrieved_articles": ["A9"]}, "unknown_article"),
        ({"ticket_id": "T2"}, "ticket_mismatch"),
        ({"reply_draft": "Gold will go up this week, you should buy."}, "advice_given"),
    ],
)
def test_hard_failures_become_a_safe_fallback(overrides, flag):
    result, problems = check(good(**overrides))
    assert problems
    assert flag in result.safety_flags
    assert result.reply_draft == HANDOFF and not result.grounded and result.needs_human_escalation
    assert set(result.retrieved_articles) <= KB_IDS


def test_advice_request_without_refusal_falls_back_to_the_refusal():
    result, _ = check(good(intent="trading_advice_request", reply_draft="Here is some general information."))
    assert result.reply_draft == REFUSAL
    assert {"advice_request", "advice_not_refused"} <= set(result.safety_flags)


@pytest.mark.parametrize("reply", ["Your deposit will be credited within 24 hours.", "Your withdrawal is guaranteed.", "The fee is 3%."])
def test_unsupported_claims_are_flagged_and_escalated(reply):
    result, problems = check(good(reply_draft=reply))
    assert problems
    assert result.reply_draft == reply  # kept for the agent to see
    assert not result.grounded and result.needs_human_escalation
    assert "insufficient_grounding" in result.safety_flags


def test_the_refusal_itself_passes():
    result, problems = check(good(intent="trading_advice_request", retrieved_articles=["A5"], reply_draft=REFUSAL, safety_flags=["advice_request"]))
    assert problems == [] and result.reply_draft == REFUSAL
