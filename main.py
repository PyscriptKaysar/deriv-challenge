"""Run the pipeline: python main.py [--tickets PATH] [--kb PATH] [--out DIR]"""

import argparse
import sys
from pathlib import Path

from triage.data import DataError
from triage.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify support tickets and draft grounded replies.")
    parser.add_argument("--tickets", type=Path, default=Path("tickets.json"))
    parser.add_argument("--kb", type=Path, default=Path("kb_articles.json"))
    parser.add_argument("--out", type=Path, default=Path("."), help="folder for results.json and debug_report.md")
    args = parser.parse_args()

    try:
        traces = run(args.tickets, args.kb, args.out)
    except DataError as e:
        print(f"Input error: {e}", file=sys.stderr)
        return 1

    for t in traces:
        r = t.result
        flags = f"  [{', '.join(r.safety_flags)}]" if r.safety_flags else ""
        print(f"{r.ticket_id:5} {r.intent:23} {','.join(r.retrieved_articles):9} conf {r.confidence:<4} escalate: {'yes' if r.needs_human_escalation else 'no'}{flags}")
    print(f"\nWrote {args.out / 'results.json'} and {args.out / 'debug_report.md'} ({len(traces)} tickets).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
