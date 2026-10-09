import json
from pathlib import Path

import pytest

from triage.classify import RuleClassifier
from triage.data import load_kb, load_tickets

TRICKY = json.loads((Path(__file__).parent / "data" / "tricky_tickets.json").read_text(encoding="utf-8"))
SAMPLE_INTENTS = {
    "T1": "deposit_issue",
    "T2": "password_reset",
    "T3": "withdrawal_issue",
    "T4": "trading_advice_request",
    "T5": "account_lock",
}
classifier = RuleClassifier()


@pytest.mark.parametrize("ticket", load_tickets("tickets.json"), ids=lambda t: t.id)
def test_sample_tickets(ticket):
    assert classifier.classify(ticket.message).intent == SAMPLE_INTENTS[ticket.id]


@pytest.mark.parametrize("case", TRICKY, ids=lambda c: c["id"])
def test_tricky_tickets(case):
    assert classifier.classify(case["message"]).intent == case["expected"]["intent"], case["why"]


def test_trading_advice_wins_over_everything():
    # X09: a deposit word and an advice phrase -> advice, even though deposit also matched.
    result = classifier.classify("Can you guarantee I'll make a profit if I deposit $500?")
    assert result.intent == "trading_advice_request"
    assert result.certainty == "conflict"


def test_tie_goes_to_priority_order():
    result = classifier.classify("My deposit went through fine but now I can't withdraw any of it.")
    assert set(result.matches) == {"withdrawal_issue", "deposit_issue"}
    assert result.intent == "withdrawal_issue"


def test_certainty():
    assert classifier.classify("I forgot my password and I am not receiving the reset email.").certainty == "single"
    assert classifier.classify("What's the weather like in Dubai today?").certainty == "none"


def test_trading_hours_is_not_advice():
    assert "trading_advice_request" not in classifier.classify("What are your trading hours on weekends?").matches


def test_matches_record_the_text_that_fired():
    result = classifier.classify("My account was locked after too many login attempts.")
    assert "locked" in result.matches["account_lock"]


def test_each_kb_article_matches_its_own_topic():
    # The same rules read the articles, so they must recognise each one's topic.
    expected = {"A1": "deposit_issue", "A2": "password_reset", "A3": "withdrawal_issue", "A4": "account_lock", "A5": "trading_advice_request"}
    for article in load_kb("kb_articles.json"):
        result = classifier.classify(f"{article.title}. {article.body}")
        assert result.intent == expected[article.article_id], article.article_id
