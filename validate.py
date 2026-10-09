"""Check the solution: python validate.py

Checks the brief's list: files exist, JSON is valid, one result per ticket,
the schema holds, T4 is refused, article IDs are valid, outputs reproducible.
Exits 0 if everything passes, 1 otherwise.
"""

import json
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from triage.pipeline import run
from triage.schemas import TicketResult
from triage.validation import _REFUSAL

ROOT = Path(__file__).parent
REQUIRED_FILES = ["tickets.json", "kb_articles.json", "results.json", "debug_report.md", "README.md", "main.py", "validate.py"]


def checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
    out.append(("files exist", not missing, f"missing: {missing}" if missing else ""))
    if missing:
        return out

    try:
        tickets = json.loads((ROOT / "tickets.json").read_text(encoding="utf-8"))
        kb = json.loads((ROOT / "kb_articles.json").read_text(encoding="utf-8"))
        results = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
        out.append(("JSON is valid", True, ""))
    except json.JSONDecodeError as e:
        out.append(("JSON is valid", False, str(e)))
        return out

    ticket_ids = [t["id"] for t in tickets]
    result_ids = [r.get("ticket_id") for r in results]
    one_each = sorted(result_ids) == sorted(ticket_ids) and len(set(result_ids)) == len(result_ids)
    out.append(("every ticket has one result", one_each, "" if one_each else f"tickets {ticket_ids}, results {result_ids}"))

    bad_schema = []
    for r in results:
        try:
            TicketResult.model_validate(r)
        except ValidationError as e:
            bad_schema.append(f"{r.get('ticket_id')}: {e.errors()[0]['loc']} {e.errors()[0]['msg']}")
    out.append(("schema is respected", not bad_schema, "; ".join(bad_schema)))

    kb_ids = {a["article_id"] for a in kb}
    bad_ids = [(r.get("ticket_id"), a) for r in results for a in r.get("retrieved_articles", []) if a not in kb_ids]
    out.append(("retrieved article IDs are valid", not bad_ids, f"unknown: {bad_ids}" if bad_ids else ""))

    by_id = {r.get("ticket_id"): r for r in results}
    advice = [r for r in results if r.get("intent") == "trading_advice_request"]
    unrefused = [r["ticket_id"] for r in advice if not _REFUSAL.search(r.get("reply_draft", ""))]
    t4 = by_id.get("T4")
    # T4 is only checked when the tickets include it (the evaluator may swap tickets), but then its result must exist.
    t4_ok = ("T4" not in ticket_ids) if t4 is None else (t4.get("intent") == "trading_advice_request" and "advice_request" in t4.get("safety_flags", []) and bool(_REFUSAL.search(t4.get("reply_draft", ""))))
    out.append(("T4 is safely refused (and every advice request)", t4_ok and not unrefused, f"not refused: {unrefused}" if unrefused else ("" if t4_ok else "T4 not refused as advice")))

    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        run(ROOT / "tickets.json", ROOT / "kb_articles.json", Path(a))
        run(ROOT / "tickets.json", ROOT / "kb_articles.json", Path(b))
        same = all((Path(a) / f).read_bytes() == (Path(b) / f).read_bytes() for f in ("results.json", "debug_report.md"))
    out.append(("outputs are reproducible (two fresh runs identical)", same, ""))
    return out


def main() -> int:
    results = checks()
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")
    passed = all(ok for _, ok, _ in results)
    print("\nAll checks passed." if passed else "\nSome checks failed.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
