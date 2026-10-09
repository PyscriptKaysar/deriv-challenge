import json
from pathlib import Path

from triage.pipeline import run
from triage.schemas import TicketResult

ROOT = Path(__file__).parent.parent


def results_in(out_dir):
    run(ROOT / "tickets.json", ROOT / "kb_articles.json", out_dir)
    return json.loads((out_dir / "results.json").read_text(encoding="utf-8"))


def test_end_to_end_matches_the_signed_off_table(tmp_path):
    by_id = {r["ticket_id"]: r for r in results_in(tmp_path)}
    assert {k: (r["intent"], r["retrieved_articles"][0], r["needs_human_escalation"]) for k, r in by_id.items()} == {
        "T1": ("deposit_issue", "A1", False),
        "T2": ("password_reset", "A2", False),
        "T3": ("withdrawal_issue", "A3", True),
        "T4": ("trading_advice_request", "A5", False),
        "T5": ("account_lock", "A4", False),
    }
    assert "advice_request" in by_id["T4"]["safety_flags"]


def test_output_matches_the_schema(tmp_path):
    for r in results_in(tmp_path):
        TicketResult.model_validate(r)


def test_two_runs_are_byte_identical(tmp_path):
    results_in(tmp_path / "a")
    results_in(tmp_path / "b")
    for name in ("results.json", "debug_report.md"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_tricky_tickets_run_end_to_end(tmp_path):
    run(ROOT / "tests" / "data" / "tricky_tickets.json", ROOT / "kb_articles.json", tmp_path)
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert len(results) == 18
    for r in results:
        TicketResult.model_validate(r)
