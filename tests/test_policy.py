import json
from pathlib import Path

import pytest

from triage.classify import RuleClassifier
from triage.data import load_kb, load_tickets
from triage.policy import LOW_CONFIDENCE, assess
from triage.retrieval import TfidfRetriever

TRICKY = json.loads((Path(__file__).parent / "data" / "tricky_tickets.json").read_text(encoding="utf-8"))

# The signed-off table in PLANNING.md.
SAMPLE_EXPECTED = {
    "T1": (False, set()),
    "T2": (False, set()),
    "T3": (True, {"policy_sensitive", "account_specific_request"}),
    "T4": (False, {"advice_request"}),
    "T5": (False, set()),
}

classifier = RuleClassifier()
retriever = TfidfRetriever(load_kb("kb_articles.json"), classifier)


def run(text):
    classification = classifier.classify(text)
    return assess(text, classification, retriever.retrieve(text, classification.ranked_intents))


@pytest.mark.parametrize("ticket", load_tickets("tickets.json"), ids=lambda t: t.id)
def test_sample_tickets_match_the_signed_off_table(ticket):
    escalate, flags = SAMPLE_EXPECTED[ticket.id]
    result = run(ticket.message)
    assert result.escalate == escalate
    assert set(result.flags) == flags
    assert result.grounded


@pytest.mark.parametrize("case", TRICKY, ids=lambda c: c["id"])
def test_tricky_tickets(case):
    result = run(case["message"])
    assert result.escalate == case["expected"]["escalate"], case["why"]
    assert set(case["expected"]["flags_include"]) <= set(result.flags), case["why"]


def test_confidence_is_always_between_0_and_1():
    texts = [t.message for t in load_tickets("tickets.json")] + [c["message"] for c in TRICKY]
    assert all(0.0 <= run(text).confidence <= 1.0 for text in texts)


def test_nothing_relevant_means_ungrounded_low_confidence_and_escalated():
    result = run("What's the weather like in Dubai today?")
    assert not result.grounded and result.escalate
    assert {"insufficient_grounding", "low_confidence"} <= set(result.flags)
    assert result.confidence < LOW_CONFIDENCE


def test_advice_is_never_escalated_even_with_other_signals():
    result = run("Why was my profit prediction wrong? Should I buy more?")
    assert "advice_request" in result.flags
    assert not result.escalate


def test_balance_question_alone_is_not_account_specific():
    # T1-style: general steps answer it, so it must not be flagged.
    assert "account_specific_request" not in run("My balance still shows zero after my card deposit.").flags


def test_every_decision_has_a_reason():
    for text in ["I forgot my password", "Why was my withdrawal declined?", "hello?"]:
        assert run(text).reasons
