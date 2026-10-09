"""The data shapes: the two input files and the output schema from the brief."""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "deposit_issue",
    "password_reset",
    "withdrawal_issue",
    "account_lock",
    "trading_advice_request",
    "other",
]
INTENTS: tuple[str, ...] = get_args(Intent)


class Ticket(BaseModel):
    """One record from tickets.json. An empty message is allowed; it's classified as `other`."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    message: str
    language: str


class Article(BaseModel):
    """One record from kb_articles.json."""

    model_config = ConfigDict(frozen=True)

    article_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class TicketResult(BaseModel):
    """One entry in results.json, exactly the brief's schema.

    Strict on purpose: "true" is not a bool and "0.5" is not a number. Extra
    fields are rejected, so internal details (scores, reasons) can't leak in.
    Whether the article IDs exist in the KB is checked in validation.py,
    since that needs the KB.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    ticket_id: str = Field(min_length=1)
    intent: Intent
    retrieved_articles: list[str] = Field(min_length=1, max_length=3)
    reply_draft: str = Field(min_length=1)
    grounded: bool
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human_escalation: bool
    safety_flags: list[str]

    @field_validator("retrieved_articles")
    @classmethod
    def _no_duplicate_articles(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids):
            raise ValueError("retrieved_articles contains duplicates")
        return ids
