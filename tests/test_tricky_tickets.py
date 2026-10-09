"""Checks the tricky-ticket file itself is well formed. The rules and retriever are tested against it in Step 4."""

import json
from pathlib import Path

from triage.data import load_kb, load_tickets
from triage.schemas import INTENTS

TRICKY = Path(__file__).parent / "data" / "tricky_tickets.json"


def test_tricky_tickets_load_as_tickets():
    tickets = load_tickets(TRICKY)
    assert len(tickets) >= 15


def test_expectations_are_valid():
    kb_ids = {a.article_id for a in load_kb("kb_articles.json")}
    known_flags = {"advice_request", "insufficient_grounding", "policy_sensitive", "low_confidence", "account_specific_request"}
    for case in json.loads(TRICKY.read_text(encoding="utf-8")):
        expected = case["expected"]
        assert expected["intent"] in INTENTS, case["id"]
        assert expected["top_article"] is None or expected["top_article"] in kb_ids, case["id"]
        assert isinstance(expected["escalate"], bool), case["id"]
        assert set(expected["flags_include"]) <= known_flags, case["id"]
        assert case["why"], case["id"]
