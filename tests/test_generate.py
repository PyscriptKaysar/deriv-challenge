import re

import pytest

from triage.classify import RuleClassifier
from triage.data import load_kb, load_tickets
from triage.generate import (
    CLOSING_ESCALATED,
    CLOSING_RESOLVED,
    HANDOFF,
    OPENING,
    REFUSAL,
    TemplateGenerator,
    customer_sentences,
    rewrite,
)
from triage.policy import assess
from triage.retrieval import TfidfRetriever
from triage.schemas import Ticket

classifier = RuleClassifier()
kb = {a.article_id: a for a in load_kb("kb_articles.json")}
retriever = TfidfRetriever(kb.values(), classifier)
generator = TemplateGenerator()


def draft_for(message):
    ticket = Ticket(id="X", message=message, language="en")
    classification = classifier.classify(message)
    hits = retriever.retrieve(message, classification.ranked_intents)
    assessment = assess(message, classification, hits)
    return generator.generate(ticket, classification.intent, hits, assessment.escalate)


@pytest.mark.parametrize("ticket", [t for t in load_tickets("tickets.json") if t.id != "T4"], ids=lambda t: t.id)
def test_every_content_sentence_comes_from_the_cited_article(ticket):
    draft = draft_for(ticket.message)
    [source] = draft.sources
    body = draft.text.removeprefix(OPENING).removesuffix(CLOSING_RESOLVED).removesuffix(CLOSING_ESCALATED).strip()
    assert body == " ".join(customer_sentences(kb[source].body))


def test_agent_only_sentences_never_reach_the_customer():
    draft = draft_for("Why was my withdrawal declined after verification?")
    assert "Support should not promise" not in draft.text
    assert draft.text.endswith(CLOSING_ESCALATED)


@pytest.mark.parametrize("message", ["Can you tell me which asset will go up today so I can make profit?", "Is BTC a good buy right now?"])
def test_advice_gets_the_fixed_refusal(message):
    draft = draft_for(message)
    assert draft.text == REFUSAL
    assert draft.sources == ("A5",)


@pytest.mark.parametrize("message", ["", "What's the weather like in Dubai today?", "Why was my account suspended?"])
def test_nothing_relevant_gets_the_handoff_with_no_article_content(message):
    draft = draft_for(message)
    assert draft.text == HANDOFF
    assert draft.sources == ()


def test_resolved_tickets_get_the_resolved_closing():
    assert draft_for("I forgot my password and I am not receiving the reset email.").text.endswith(CLOSING_RESOLVED)


@pytest.mark.parametrize(
    ("agent", "customer"),
    [
        ("Ask the client to confirm successful payment.", "Please confirm successful payment."),
        ("Advise the client to wait for the cooldown period.", "Please wait for the cooldown period."),
        ("If the client does not receive a reset email, retry.", "If you do not receive a reset email, retry."),
        ("Check the client's inbox.", "Check your inbox."),
        ("Repeated attempts can lock the account.", "Repeated attempts can lock your account."),
        ("Wait before escalating.", "Wait before contacting us again."),
    ],
)
def test_rewrites(agent, customer):
    assert rewrite(agent) == customer


def test_no_draft_mentions_the_client_or_escalating():
    for ticket in load_tickets("tickets.json"):
        text = draft_for(ticket.message).text
        assert not re.search(r"\bclient\b|\bescalat", text, re.IGNORECASE), ticket.id
