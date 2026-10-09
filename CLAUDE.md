# Support Ticket Pipeline — Project Instructions

## What we're building
A small, runnable Python service that takes customer support tickets and, for each one, produces a structured reply draft for a human agent. It classifies the intent, retrieves the most relevant help-centre articles, writes a reply grounded only in those articles, and adds a confidence score, an escalation signal and safety flags.

The full challenge text is in [`docs/brief.md`](docs/brief.md). **That brief is the source of truth for requirements.** If anything else in the repo disagrees with it, flag the conflict.

**The pipeline (stages must be visible in the code):**
`LOAD_DATA → INDEX_KB → CLASSIFY_INTENT → RETRIEVE_CONTEXT → GENERATE_REPLY → VALIDATE_OUTPUT → WRITE_RESULTS`

**Must complete:** the runnable pipeline · intent classification into the 6 allowed labels · deterministic top 1–3 retrieval · grounded reply generation · output validation · basic tests (T4 refused as trading advice, T1 retrieves the deposit article, output matches the schema).
**Should attempt:** confidence + escalation logic · specific safety flags · a debug report (intent, article titles, why escalated or not).
**Stretch:** swap-friendly component boundaries · a non-LLM offline fallback.

## Hard constraints (the evaluator checks these)
- **Runs from a clean checkout** with one command (`python main.py`), and validates with one command (`python validate.py`).
- **Runs without secrets.** The brief lists the offline fallback as a stretch goal, but its Tools section says the solution *must* be runnable without a key. Treat the no-key path as required, and assume the evaluator has no key.
- **Reads only the local files** `tickets.json` and `kb_articles.json`. No external APIs for retrieval.
- **Retrieval and generation are separate steps.** Retrieval is deterministic for the same inputs.
- **No hard-coded answers per ticket, and no logic keyed on ticket IDs.** The evaluator may swap in similar tickets with the same schema. Tests can refer to T1/T4, but the pipeline must not.
- **Never give trading advice**, market predictions or profit promises. Never invent account-specific facts or promise payment/withdrawal outcomes.
- **Outputs are reproducible** for the same inputs, and `validate.py` checks this.
- **Required artifacts:** `tickets.json`, `kb_articles.json`, `results.json`, `debug_report.json` or `.md`, `README.md`, `validate.py` and/or tests.

## Non-negotiables
- **Read `README.md` + `PLANNING.md` + `TASK.md` first** at the start of any new chat (once they exist), plus `docs/brief.md`.
- **One step at a time/one part at a time.** If the request contains multiple big parts of a task, pick the best one to do next and let me know.
- **Don't assume if u dont know** if unclear just ask me.
- **You're a teammate on this project**, so act like one: care about correctness, grounding (no hallucinations), safe behaviour on edge cases, simple and readable code, and a run that works first time from a clean checkout. Treat it as a real product, not a throwaway demo. Keep scope tight: must-complete before should-attempt before stretch. Flag scope creep early.

## Docs-first research order (enforced)
1) Repo docs: `docs/brief.md`, `README.md`, `PLANNING.md`, `TASK.md`, the plans in `plans/`, and anything else in `docs/`.
2) Official docs (the LLM provider's API, scikit-learn, pydantic) whenever u need them. Try ur built-in knowledge first, then web search, since APIs change.
- If you couldn't find it, ask me and i can find it for u.
- **Model names are newer than ur training data.** `gpt-6-luna` and `gpt-6.1-sol` were checked against OpenAI's models page (Oct 2026). Don't "correct" them to older names you know; if one fails, check the models page and ask me.

## How to work
- **Don't start producing/building anything until I say u can proceed.** Propose the smallest next step first.
- If required context is missing from `PLANNING.md` / `TASK.md`, ask **1-3 specific questions** and stop.
- Follow "Docs-first research order" above whenever u need to implement something.
- If something is not possible due to limitations, explain why and suggest alternatives.
- If something I ask for contradicts a decision already recorded in `PLANNING.md`, or the brief, flag the conflict instead of just picking one.

## Secrets
- API keys live in `.env` only. Never print, log or commit them, and keep `.env` in `.gitignore`.
- Write `.gitignore` before the first `git init` / commit. Commit a `.env.example` with placeholder values instead.

## Plans
- Every piece of work starts with a plan doc in `plans/` (`01-…`, `02-…`), written before any code and signed off by me.
- Use the same structure as the format reference [`reference/faq-bot/plans/01-must-haves.md`](reference/faq-bot/plans/01-must-haves.md) (once we have our own `plans/01-…`, use that instead): status line, why this plan exists, what you'll see at the end, numbered steps + checkpoints, done when, not in this plan, open questions.
- When I sign off a plan or decide an open question, record it in the plan and in `TASK.md` straight away, so a new chat can pick up from the docs alone.

## Tests
- Free tests and `python validate.py` (no API calls, run on the offline path) must pass before anything goes to review.
- Anything that calls a paid LLM API costs money (e.g. a live suite behind `pytest -m live`), so only run it when a step needs it or I ask.

## Tasks
- `TASK.md` is the source of truth.
- When starting a task, mark it `doing`.
- When finishing a task:
  - Mark status in `TASK.md` (todo → doing → review → done)
  - Note what changed and any follow-ups.

## Reference material
- `reference/faq-bot/` is my previous project (an FAQ chatbot). Use it **only** as a format and writing-style reference for `README.md`, `PLANNING.md`, `TASK.md` and plans.
- Its decisions do **not** carry over. For example, it chose "no retrieval, whole FAQ in the prompt" and a Streamlit UI; this brief requires retrieval and a CLI.

## Output format (follow only when necessary)
### What I did
- ...
### Files changed
- ...
### Notes / risks
- ...
