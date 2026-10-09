"""GENERATE_REPLY: turn the retrieved articles into a reply draft.

TemplateGenerator is the offline generator: every fact in its reply is a
sentence from a retrieved article, reworded from agent guidance into
customer wording by a small generic phrase table. Anything with the same
`generate` method can replace it (Plan 02 adds an OpenAI one).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from triage.retrieval import Hit
from triage.schemas import Ticket

OPENING = "Thanks for reaching out."
CLOSING_ESCALATED = "We've passed your ticket to a support specialist, who will review your account and follow up with you."
CLOSING_RESOLVED = "If this doesn't solve it, just reply to this message and we'll help further."

# The same for every trading-advice request: a policy response, not an answer
# per ticket (Plan 01, open question 2). Its wording follows the no-advice
# article; it never names an asset or a price.
REFUSAL = (
    f"{OPENING} We're not able to provide market predictions, profit guarantees or asset "
    "recommendations, so we can't tell you what to buy or sell. Trading decisions are always "
    "your own. If you have a question about your account, deposits or withdrawals, we're happy to help."
)
# For tickets no article covers: no article content, so nothing to get wrong.
HANDOFF = (
    f"{OPENING} We couldn't find a help-centre article that covers your question, so we've "
    "passed your ticket to a support specialist, who will follow up with you."
)

# Sentences that instruct support staff, not the customer; never shown to them.
_AGENT_ONLY = re.compile(r"^(?:support|agents?|support agents?|staff)\b|\b(?:support|agents?) (?:should|must)\b", re.IGNORECASE)

# Generic agent-to-customer rewrites, applied in order. Not tied to any article.
_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:Ask|Advise|Tell|Remind) the client to (\w)"), lambda m: f"Please {m.group(1).lower()}"),
    (re.compile(r"\bthe client does\b"), "you do"),
    (re.compile(r"\bthe client is\b"), "you are"),
    (re.compile(r"\bthe client has\b"), "you have"),
    (re.compile(r"\bthe client's\b"), "your"),
    (re.compile(r"\bthe client\b"), "you"),
    (re.compile(r"\bthe (account|registered)\b"), r"your \1"),
    (re.compile(r"\bbefore escalating\b"), "before contacting us again"),
]


@dataclass(frozen=True)
class Draft:
    text: str
    sources: tuple[str, ...]  # the article IDs the reply's content came from


class Generator(Protocol):
    def generate(self, ticket: Ticket, intent: str, hits: Sequence[Hit], escalate: bool) -> Draft: ...


class TemplateGenerator:
    def generate(self, ticket: Ticket, intent: str, hits: Sequence[Hit], escalate: bool) -> Draft:
        on_intent = [h for h in hits if h.on_intent]
        if intent == "trading_advice_request":
            return Draft(REFUSAL, tuple(h.article.article_id for h in on_intent[:1]))
        if not on_intent:
            return Draft(HANDOFF, ())

        article = on_intent[0].article
        body = " ".join(customer_sentences(article.body))
        closing = CLOSING_ESCALATED if escalate else CLOSING_RESOLVED
        return Draft(f"{OPENING} {body} {closing}", (article.article_id,))


def customer_sentences(body: str) -> list[str]:
    """The article's sentences in customer wording, with agent-only ones dropped."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    return [rewrite(s) for s in sentences if not _AGENT_ONLY.search(s)]


def rewrite(sentence: str) -> str:
    for pattern, replacement in _REWRITES:
        sentence = pattern.sub(replacement, sentence)
    return sentence
