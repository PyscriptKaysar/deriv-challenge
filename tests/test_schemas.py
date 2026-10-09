import pytest
from pydantic import ValidationError

from triage.schemas import INTENTS, TicketResult


def valid_result(**overrides):
    data = {
        "ticket_id": "T1",
        "intent": "deposit_issue",
        "retrieved_articles": ["A1"],
        "reply_draft": "Please check your transaction history.",
        "grounded": True,
        "confidence": 0.8,
        "needs_human_escalation": False,
        "safety_flags": [],
    }
    return data | overrides


def test_the_six_intent_labels_match_the_brief():
    assert set(INTENTS) == {
        "deposit_issue",
        "password_reset",
        "withdrawal_issue",
        "account_lock",
        "trading_advice_request",
        "other",
    }


def test_valid_result_passes():
    TicketResult.model_validate(valid_result())


def test_confidence_bounds_are_inclusive():
    TicketResult.model_validate(valid_result(confidence=0))
    TicketResult.model_validate(valid_result(confidence=1.0))


@pytest.mark.parametrize(
    "overrides",
    [
        {"intent": "refund_request"},
        {"confidence": 1.5},
        {"confidence": -0.1},
        {"confidence": "0.5"},
        {"retrieved_articles": []},
        {"retrieved_articles": ["A1", "A2", "A3", "A4"]},
        {"retrieved_articles": ["A1", "A1"]},
        {"grounded": "true"},
        {"needs_human_escalation": 1},
        {"reply_draft": ""},
        {"debug_score": 0.3},
    ],
    ids=lambda o: next(iter(o)) + "=" + repr(next(iter(o.values()))),
)
def test_bad_result_is_rejected(overrides):
    with pytest.raises(ValidationError):
        TicketResult.model_validate(valid_result(**overrides))


@pytest.mark.parametrize("field", list(valid_result()))
def test_every_field_is_required(field):
    data = valid_result()
    del data[field]
    with pytest.raises(ValidationError):
        TicketResult.model_validate(data)
