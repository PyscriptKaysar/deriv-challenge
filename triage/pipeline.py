"""The pipeline, stage by stage, in the brief's order:

LOAD_DATA -> INDEX_KB -> CLASSIFY_INTENT -> RETRIEVE_CONTEXT -> GENERATE_REPLY -> VALIDATE_OUTPUT -> WRITE_RESULTS
"""

import json
from dataclasses import dataclass
from pathlib import Path

from triage.classify import Classification, Classifier, RuleClassifier
from triage.data import load_kb, load_tickets
from triage.generate import Generator, TemplateGenerator
from triage.policy import Assessment, assess
from triage.retrieval import Hit, TfidfRetriever
from triage.schemas import Article, Ticket, TicketResult
from triage.validation import validate_output


@dataclass(frozen=True)
class Trace:
    """Everything behind one result, for the debug report."""

    result: TicketResult
    classification: Classification
    hits: list[Hit]
    assessment: Assessment
    problems: list[str]


def load_data(tickets_path: Path, kb_path: Path) -> tuple[list[Ticket], list[Article]]:
    return load_tickets(tickets_path), load_kb(kb_path)


def index_kb(articles: list[Article], classifier: Classifier) -> TfidfRetriever:
    return TfidfRetriever(articles, classifier)


def classify_intent(ticket: Ticket, classifier: Classifier) -> Classification:
    return classifier.classify(ticket.message)


def retrieve_context(ticket: Ticket, classification: Classification, retriever: TfidfRetriever) -> list[Hit]:
    return retriever.retrieve(ticket.message, classification.ranked_intents)


def generate_reply(ticket: Ticket, classification: Classification, hits: list[Hit], generator: Generator) -> tuple[dict, Assessment]:
    assessment = assess(ticket.message, classification, hits)
    draft = generator.generate(ticket, classification.intent, hits, assessment.escalate)
    raw = {
        "ticket_id": ticket.id,
        "intent": classification.intent,
        "retrieved_articles": [h.article.article_id for h in hits],
        "reply_draft": draft.text,
        "grounded": assessment.grounded,
        "confidence": assessment.confidence,
        "needs_human_escalation": assessment.escalate,
        "safety_flags": list(assessment.flags),
    }
    return raw, assessment


def validate(raw: dict, ticket: Ticket, articles: list[Article], hits: list[Hit]) -> tuple[TicketResult, list[str]]:
    source_text = " ".join(f"{h.article.title} {h.article.body}" for h in hits)
    return validate_output(raw, ticket.id, {a.article_id for a in articles}, source_text)


def write_results(traces: list[Trace], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [t.result.model_dump() for t in traces]
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "debug_report.md").write_text(_debug_report(traces), encoding="utf-8")


def run(
    tickets_path: Path,
    kb_path: Path,
    out_dir: Path,
    classifier: Classifier | None = None,
    generator: Generator | None = None,
) -> list[Trace]:
    classifier = classifier or RuleClassifier()
    generator = generator or TemplateGenerator()

    tickets, articles = load_data(tickets_path, kb_path)
    retriever = index_kb(articles, classifier)
    traces = []
    for ticket in tickets:
        classification = classify_intent(ticket, classifier)
        hits = retrieve_context(ticket, classification, retriever)
        raw, assessment = generate_reply(ticket, classification, hits, generator)
        result, problems = validate(raw, ticket, articles, hits)
        traces.append(Trace(result, classification, hits, assessment, problems))
    write_results(traces, out_dir)
    return traces


def _debug_report(traces: list[Trace]) -> str:
    lines = ["# Debug report", "", "Why each ticket got its intent, articles and escalation decision.", ""]
    for t in traces:
        r = t.result
        matched = "; ".join(f"{intent}: {', '.join(repr(m) for m in found)}" for intent, found in t.classification.matches.items())
        lines += [
            f"## {r.ticket_id} — `{r.intent}`",
            "",
            f"- **Intent rules matched:** {matched or 'none'} (certainty: {t.classification.certainty})",
            "- **Retrieved:** "
            + "; ".join(f"{h.article.article_id} \"{h.article.title}\" (TF-IDF {h.score:.2f}{'' if h.on_intent else ', off-intent'})" for h in t.hits),
            f"- **Confidence:** {r.confidence} · **grounded:** {r.grounded} · **flags:** {', '.join(r.safety_flags) or 'none'}",
            f"- **Escalated:** {'yes' if r.needs_human_escalation else 'no'} — {'; '.join(t.assessment.reasons)}",
        ]
        if t.problems:
            lines.append(f"- **Validation:** {'; '.join(t.problems)}")
        lines.append("")
    return "\n".join(lines)
