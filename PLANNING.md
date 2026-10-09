# PLANNING — the overall plan

**Status:** signed off by Kaysar (9 Oct 2026). All three open questions are
decided (recorded at the end).

A small Python service that reads support tickets and a help-centre knowledge
base from disk. For each ticket it produces a structured reply draft for a
human agent to review. It classifies the intent, retrieves the most relevant
articles, writes a reply grounded only in those articles, and attaches a
confidence score, an escalation signal and safety flags. The full brief is in
[`docs/brief.md`](docs/brief.md); it is the source of truth for requirements.

We're treating it as a real product, not a throwaway demo. Every decision below
has a "why", so whoever picks this up next can tell what to keep and what to
change.

This is the long view. What we're building *right now* goes in `TASK.md`, and
each phase gets its own plan in `plans/`.

| Phase | What it is | Brief section | Status |
|---|---|---|---|
| **1 — The offline pipeline** | All 7 stages end to end with no API key: rules, TF-IDF, template replies, validation, `validate.py`, tests | Must 1–6, Stretch 10–11 | not started |
| **2 — The LLM generator** | OpenAI writes the reply when a key is set; grounding checks; reproducibility | Must 4 (the LLM path) | not started |
| **3 — Confidence, flags, debug report** | Real confidence and escalation logic, the full safety-flag set, `debug_report.md` | Should 7–9 | not started |
| **4 — Ship it** | README, a clean-checkout run, clean-up | Required artifacts | not started |

Rule: finish a phase before starting the next. Phases 1, 2 and 4 are what
ships. Phase 3 is "should attempt", but it's cheap once 1 and 2 exist, so we
plan to do it.

---

# Decisions

## Decided by Kaysar (9 Oct)

1. **LLM provider:** OpenAI, model `gpt-6-luna`.
2. **The LLM runs by default when a key is set.** `python main.py` uses OpenAI
   to write replies if `OPENAI_API_KEY` is present, and the offline generator
   if it isn't. (I'd suggested making offline the default. Kaysar chose the
   LLM, since we have a key.)
3. **Scope:** aim for everything in the brief (must, should, stretch), but
   must-complete first.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.13** (3.13.5 installed) | Required by the brief, and already installed. |
| LLM | **OpenAI Responses API**, `gpt-6-luna`, structured outputs | Decided by Kaysar. Structured outputs make the model return the fields we check (reply + cited article IDs), not free text. Luna is the cheap model; on the previous project it held up at reasoning effort `none`. |
| Model config | `OPENAI_MODEL` in `.env`, defaulting to `gpt-6-luna` in code | A clean checkout works with just a key. Model names are newer than Claude's training data, so they stay one line to change. |
| Retrieval | **scikit-learn `TfidfVectorizer`** + cosine similarity | Suggested by the brief, deterministic, local, no API. Five articles don't need embeddings. |
| Schemas | **pydantic** | Suggested by the brief. One model per record (`Ticket`, `Article`, `TicketResult`) gives us loading checks, the output schema and validation in one place. |
| Config | `python-dotenv`; `.env` holds the key, `.env.example` is committed | Keys never in code. |
| Packaging | pip + pinned `requirements.txt` in a venv | Every evaluator knows it. |
| Tests | **pytest** for unit tests + **`validate.py`** as the evaluator's single check command | The brief asks for both a validation command and tests. |
| Interface | **CLI only** (`python main.py`, `python validate.py`) | The brief asks for a runnable service with two commands. A UI would be scope creep. |

## How it fits together

```
main.py                 CLI: runs the pipeline, prints a one-line summary per ticket
validate.py             the evaluator's check: files, JSON, schema, T4, IDs, reproducibility
triage/
  schemas.py            pydantic: Ticket, Article, TicketResult, Intent (the 6 labels)
  data.py               LOAD_DATA     read + validate tickets.json and kb_articles.json
  retrieval.py          INDEX_KB, RETRIEVE_CONTEXT    TfidfRetriever
  classify.py           CLASSIFY_INTENT               RuleClassifier
  generate.py           GENERATE_REPLY                TemplateGenerator (offline), OpenAIGenerator
  policy.py             confidence, escalation, safety flags (plain rules, no API)
  validation.py         VALIDATE_OUTPUT               checks every result before it's written
  pipeline.py           wires the stages together, WRITE_RESULTS
tickets.json            sample input (from the brief)
kb_articles.json        sample knowledge base (from the brief)
results.json            output: one TicketResult per ticket
debug_report.md         output: why each ticket got its intent, articles and escalation
tests/
```

Each stage is a named function in `pipeline.py`, in the brief's order, so the
evaluator can see `LOAD_DATA → … → WRITE_RESULTS` in the code.

**Swap-friendly boundaries (Stretch 10) from day one.** The classifier,
retriever and generator are each a small interface (`classify(ticket)`,
`retrieve(text, k)`, `generate(ticket, intent, articles)`). The pipeline only
knows the interfaces. Swapping in an LLM classifier or embedding retrieval later
means writing one class. This costs nothing if we design it in now, and
retrofitting it later is a rewrite.

## The key design choices

**Yes, this is RAG, the light kind.** Retrieve the relevant articles, then
generate a reply from only those. The brief requires retrieval as its own
step. What we skip is the heavy machinery (embeddings, a vector database),
since 5 articles don't need it. (The previous project in `reference/` chose
"no RAG, whole FAQ in the prompt"; that doesn't apply here.)

**Intent: rules, not the LLM.** Keyword/phrase rules per intent, checked in a
fixed priority order with `trading_advice_request` first. Why:
- The no-key path needs a classifier anyway.
- Rules are deterministic, free and testable, and five clear-cut intents don't
  need a model.
- **Detecting trading-advice requests must never depend on a model behaving.**
  It's the one check the evaluator tests by name.

The rules also report how sure they are: one intent matched, several matched
(conflict), or none matched (`other`). Confidence uses that. An LLM classifier
can go behind the same interface later if swapped-in tickets show the rules
missing things.

**Retrieval: intent narrows, TF-IDF ranks, always 1–3 results.** (Changed
in Plan 01 Step 4, Kaysar's decision, 9 Oct. The original "TF-IDF + a
minimum score" failed on the test tickets; the numbers are in `TASK.md`.)
- **Tags:** the classifier's rules tag each article with the intents it
  covers, read from the article's own text.
- **Ordering:** ticket text is the query. Articles tagged with the ticket's
  intent come first, ranked by TF-IDF score (plain words), and ties are broken
  by `article_id`, so the order is deterministic.
- **No match:** a ticket classified `other` still gets the single best TF-IDF
  article (the brief says 1 to 3), marked off-intent, so it's treated as
  ungrounded and escalated.
- **The trade-off:** on a 5-article KB the intent mostly decides the article,
  and TF-IDF orders things. It earns more on a bigger KB with several articles
  per intent. The README should say so plainly.

**Retrieval and generation never mix.** The generator only receives the
articles retrieval picked. It never sees the whole KB or searches itself.
That's what makes "trace the answer back to retrieved content" true.

**Trading-advice requests never reach the LLM.** If the intent is
`trading_advice_request`, the reply is a polite refusal built from the
retrieved policy article. It's the same for any advice request, not hard-coded
per ticket, and it's deterministic. Why: never send a request to a generator
that might comply. The validator still checks every reply for refusal and
prediction language as a backstop.

**The LLM generator.**
- **The prompt** includes only the retrieved snippets. It tells the model to:
  - answer the ticket directly
  - use nothing beyond the snippets
  - not state account-specific facts
  - not promise outcomes or timings
- **The structured reply** is `reply_draft` + `used_article_ids`.
- **Settings:** `store=False` and reasoning effort `none` to start (lessons
  from the previous project).
- **If the call fails** (no network, rate limit, refusal, bad parse), that
  ticket falls back to the offline generator. The debug report records which
  generator wrote it. One bad call never crashes the run.

**The offline generator (Stretch 11).** It builds the reply from the retrieved
articles' own sentences, rewritten from agent guidance ("Ask the client to
confirm…") into customer-facing wording ("Please confirm…"), with a standard
opening and closing. It's grounded by construction. It's less fluent than the
LLM, and that's acceptable for a fallback.

**Validation before writing (Must 5).** Every result goes through
`validation.py`:
- **Schema:** required fields, an allowed intent, known article IDs only,
  0 ≤ confidence ≤ 1.
- **Safety:** trading-advice tickets are refused. There's also an
  unsupported-claims check (details below).

A result that fails is **not dropped and doesn't crash the run**. It's
replaced with a safe fallback: a generic "a support agent will follow up"
draft, `grounded: false`, escalation on, and a flag naming the failed check.
So every ticket always has exactly one valid result.

**The unsupported-claims check** is heuristic, and we'll say so in the README.
It flags a reply that does any of these:
- cites an article that wasn't retrieved
- contains a number or time that isn't in the retrieved text
- uses promise language ("guarantee", "will be approved", "within 24 hours")

Any hit sets `grounded: false` plus `insufficient_grounding` and turns on
escalation. It catches the common failures, but it can't prove a reply is
grounded.

**Confidence and escalation are plain rules, never the LLM.** Confidence comes
from:
- the top retrieval score
- the gap between the 1st and 2nd article
- how sure the classifier is
- whether the classifier and retrieval agree

Escalation turns on for:
- low confidence
- a policy-sensitive intent (withdrawal review)
- an account-specific request the KB can't answer
- any grounding or validation failure

Plan 01 ships a simple version. Phase 3 tunes it against the expected outcomes
below.

## Expected outcomes for the sample tickets (signed off 9 Oct)

| Ticket | Intent | Articles | Escalate? | Flags | Why |
|---|---|---|---|---|---|
| T1 card deposit, balance zero | `deposit_issue` | A1 | no | — | A1 gives the steps (confirm payment, check history, wait for the processing window) and says to escalate only after that. |
| T2 no reset email | `password_reset` | A2 | no | — | A2 fully covers it. |
| T3 withdrawal declined | `withdrawal_issue` | A3 | **yes** | `policy_sensitive`, `account_specific_request` | The actual reason needs someone to check the account; A3 lists possible reasons but says not to promise anything without checking. |
| T4 which asset will go up | `trading_advice_request` | A5 | no | `advice_request` | Politely refused. The refusal is complete, so no human is needed. |
| T5 account locked | `account_lock` | A4 | no | — | A4 covers it: wait for the cooldown or use the secure recovery flow. |

These become test expectations, so they should be right before code exists.

## Edge cases we handle

| Case | Behaviour |
|---|---|
| Off-topic ticket ("what's the weather?") | `other`, weak retrieval → low confidence, escalate, `insufficient_grounding` |
| Two issues in one ticket ("deposit and withdrawal") | Rule conflict → lower confidence; retrieval can return both articles |
| Prompt injection in the ticket ("ignore your rules…") | The ticket is passed as data, not instructions; the validator still checks the reply |
| Non-English ticket (`language` ≠ `en`) | Processed, but flagged and escalated: the rules and KB are English-only |
| Empty message | `other`, escalate |
| A broken `tickets.json` or `kb_articles.json` | Fail loudly at LOAD_DATA with a clear message. Bad input files are the operator's problem, not something to guess around. |

---

# Phase 1 — The offline pipeline (Plan 01)

**Goal:** `python main.py` and `python validate.py` both pass from a clean
checkout **with no API key**, covering every must-complete item.

- Setup: `.gitignore` (no git yet, but ready for it), `requirements.txt`,
  `.env.example`, venv, `pytest.ini`.
- The two sample files, exactly as in the brief.
- `schemas.py`, `data.py`, `classify.py`, `retrieval.py`, the offline
  generator, a simple `policy.py`, `validation.py`, `pipeline.py`, `main.py`.
- `validate.py` and the free tests:
  - T4 refused
  - T1 retrieves A1
  - schema
  - IDs valid
  - one result per ticket
  - reproducible across two runs
  - plus unit tests per stage
- **Why offline first, even though the LLM is the default:** it's the path the
  evaluator most likely runs (no key). It's fully testable for free. And it
  proves the stage boundaries before the LLM plugs into them.

# Phase 2 — The LLM generator (Plan 02)

- `OpenAIGenerator` behind the generator interface: the prompt, the structured
  reply, the grounding checks above, and per-ticket fallback on failure.
- The reproducibility mechanism (open question 1).
- A small live suite (`pytest -m live`, costs cents): the sample tickets plus
  tricky ones (paraphrases, near misses, injection, mixed intents). It checks
  the structured fields, not wording.

# Phase 3 — Confidence, flags, debug report (Plan 03)

- Tune the confidence formula and thresholds against the expected-outcomes
  table and the tricky tickets.
- Tune the five brief flags (built in simple form in Plan 01, since the T1–T5
  table needs them), and add a flag for non-English tickets.
- `debug_report.md`: per ticket, the intent and the rule that fired, the
  retrieved titles with scores, which generator wrote the reply, and why it was
  or wasn't escalated.

# Phase 4 — Ship it (Plan 04)

- README: run + validate in a few commands, the pipeline diagram, the key
  decisions above, known limitations (heuristic claim check, rule coverage,
  English only), and how it would scale:
  - embeddings behind `retrieve`
  - an LLM classifier behind `classify`
  - from `reference/research.md` (Gemini, 9 Oct):
    - past resolved tickets as a second retrieval source
    - a tools layer for real account actions, with a human approving them
    - a confidence threshold that decides auto-send vs draft-for-review
- A clean-checkout run, both with and without a key.
- Clean-up: pinned requirements, no dead code.

---

# Risks

- **Reproducibility vs the LLM default.** The brief says `validate.py` must
  check that outputs are reproducible, but LLM text varies between runs, and
  Luna doesn't accept `temperature`. Kaysar's choice to use the LLM by default
  makes this a real design problem. See open question 1.
- **Rules and TF-IDF on swapped tickets.** The evaluator may replace the
  tickets. A paraphrase the rules don't cover becomes `other`, and a word
  mismatch weakens retrieval. Mitigation: test against paraphrases, not just the
  five samples, and let low confidence escalate rather than guess.
- **The KB is written for agents, not customers.** The bodies say things like
  "Ask the client to…". Both generators must turn that into customer-facing
  wording without adding facts.
- **Model names are post-training-cutoff.** They're in `.env` with a default
  in code, so they're one line to change.
- **Scope creep.** No UI, no API server, no vector DB. Phase 3 starts only
  after Phase 2 passes.

# Out of scope

A web UI or HTTP API · embeddings / a vector DB · real account lookups · multiple
languages · deployment · an LLM classifier (the interface allows it later).

---

# Open questions

1. ~~**How do we make LLM outputs reproducible?**~~ **Decided (Kaysar, 9 Oct):
   (a), the response cache.** Options were:
   - **(a) A response cache (recommended).** Cache each LLM reply keyed by a
     hash of the model + prompt (`.cache/`, gitignored). The first run calls
     the API; any rerun with the same inputs returns the identical reply at no
     cost. `validate.py` runs the pipeline twice and compares the whole
     output. This matches what "same inputs → same outputs" means, and it
     makes `validate.py` free after the first run.
   - **(b) Check only the deterministic fields.** `validate.py` compares
     intent, articles, confidence, escalation and flags across runs, but not
     `reply_draft`. Simpler, but it only partly meets the brief.
   - **(c) Run the reproducibility check offline only.** This dodges the
     question rather than answering it.
2. ~~**Are the expected outcomes for T1–T5 right?**~~ **Decided (Kaysar,
   9 Oct): yes, as in the table.** Only T3 escalates; T4 is refused without
   escalation.
3. ~~**Do we include the generated `results.json` and `debug_report.md` in
   the submission?**~~ **Decided (Kaysar, 9 Oct): yes**, generated on the LLM
   path, so the evaluator can read real output before running anything.
   `main.py` overwrites them on every run.

# Submission

- **No git for now** (Kaysar, 9 Oct): it costs time. Maybe later if there's
  time to spare. `.gitignore` is still written in Plan 01, so it's ready if we
  add git, and it keeps `.env` out from the start.
- **The challenge asks for specs/design notes, in Markdown, written before
  coding** (see the addendum in `docs/brief.md`). `PLANNING.md` and `plans/`
  are those notes and go into the submission.
- **Leave out:** `reference/` (the previous project), `.env`, `.venv/`,
  `.cache/`.
- **How it's uploaded** (zip, link, …) is not known yet; it's tracked in
  `TASK.md`.
