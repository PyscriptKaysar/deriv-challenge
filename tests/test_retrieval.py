import json
from pathlib import Path

import pytest

from triage.classify import RuleClassifier
from triage.data import load_kb, load_tickets
from triage.retrieval import MAX_RESULTS, TfidfRetriever
from triage.schemas import Article

TRICKY = json.loads((Path(__file__).parent / "data" / "tricky_tickets.json").read_text(encoding="utf-8"))
SAMPLE_TOP = {"T1": "A1", "T2": "A2", "T3": "A3", "T4": "A5", "T5": "A4"}

classifier = RuleClassifier()
retriever = TfidfRetriever(load_kb("kb_articles.json"), classifier)


def retrieve(text):
    return retriever.retrieve(text, classifier.classify(text).ranked_intents)


def test_t1_retrieves_the_deposit_article():
    [t1] = [t for t in load_tickets("tickets.json") if t.id == "T1"]
    hits = retrieve(t1.message)
    assert hits[0].article.article_id == "A1"
    assert hits[0].on_intent


@pytest.mark.parametrize("ticket", load_tickets("tickets.json"), ids=lambda t: t.id)
def test_sample_tickets_top_article(ticket):
    assert retrieve(ticket.message)[0].article.article_id == SAMPLE_TOP[ticket.id]


@pytest.mark.parametrize("case", TRICKY, ids=lambda c: c["id"])
def test_tricky_tickets(case):
    hits = retrieve(case["message"])
    expected_top = case["expected"]["top_article"]
    if expected_top is None:
        # Nothing relevant: exactly one fallback hit, never presented as on-intent.
        assert len(hits) == 1 and not hits[0].on_intent, case["why"]
    else:
        assert hits[0].article.article_id == expected_top, case["why"]
        assert hits[0].on_intent


def test_articles_are_tagged_from_their_own_text():
    assert retriever.tags == {
        "A1": {"deposit_issue"},
        "A2": {"password_reset"},
        "A3": {"withdrawal_issue"},
        "A4": {"account_lock"},
        "A5": {"trading_advice_request"},
    }


def test_mixed_intent_returns_both_articles_main_one_first():
    hits = retrieve("My deposit went through fine but now I can't withdraw any of it.")
    assert [h.article.article_id for h in hits] == ["A3", "A1"]


@pytest.mark.parametrize("text", ["", "What's the weather like in Dubai today?", "x" * 5000])
def test_always_one_to_three_unique_hits(text):
    hits = retrieve(text)
    ids = [h.article.article_id for h in hits]
    assert 1 <= len(hits) <= MAX_RESULTS and len(set(ids)) == len(ids)


def test_never_more_than_three_even_when_many_articles_match():
    kb = [Article(article_id=f"D{i}", title=f"Deposit topic {i}", body="Deposits explained.") for i in range(5)]
    hits = TfidfRetriever(kb, classifier).retrieve("my deposit", ["deposit_issue"])
    assert len(hits) == MAX_RESULTS


def test_ties_are_broken_by_article_id():
    # Identical articles score identically, so ID order decides, whatever the input order.
    kb = [Article(article_id=i, title="Deposit times", body="Deposits are instant.") for i in ("B2", "B1", "B3")]
    hits = TfidfRetriever(kb, classifier).retrieve("deposit", ["deposit_issue"])
    assert [h.article.article_id for h in hits] == ["B1", "B2", "B3"]


def test_deterministic_across_fresh_indexes():
    text = "I deposited by bank card two hours ago but my balance still shows zero."
    again = TfidfRetriever(load_kb("kb_articles.json"), classifier)
    assert retrieve(text) == again.retrieve(text, classifier.classify(text).ranked_intents)


def test_scores_are_between_0_and_1():
    assert all(0.0 <= s <= 1.0 for s in retriever.scores("card deposit withdrawal password").values())
