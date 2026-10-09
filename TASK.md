# TASK — Support Ticket Pipeline (build)

Status flow: todo → doing → review → done.

The requirements are in [`docs/brief.md`](docs/brief.md). The long view and the
reasoning behind every decision are in [`PLANNING.md`](PLANNING.md). Each phase
gets its own plan in `plans/`, written before work starts and signed off before
code.

---

## Decided (9 Oct 2026)

| Topic | Decision |
|---|---|
| Language | Python 3.13 (3.13.5 installed) |
| LLM | OpenAI Responses API, `gpt-6-luna` (`OPENAI_MODEL` in `.env`, default in code) |
| Default mode | The LLM writes replies when `OPENAI_API_KEY` is set; the offline generator otherwise |
| Intent | Keyword rules, not the LLM; trading advice is checked first |
| Retrieval | scikit-learn TF-IDF + cosine, top 1–3, ties broken by `article_id` |
| Trading advice | Never sent to the LLM; one fixed polite refusal for every advice request (a policy response, not an answer per ticket) |
| Offline reply wording | Article sentences with generic phrase rewrites ("Ask the client to" → "Please"); agent-only sentences dropped |
| Reproducibility | LLM replies cached by a hash of model + prompt (`.cache/`), so reruns are identical |
| Expected T1–T5 outcomes | The table in `PLANNING.md`: only T3 escalates; T4 refused, not escalated |
| Generated outputs | `results.json` + `debug_report.md` go into the submission, generated on the LLM path |
| Interface | CLI only: `python main.py`, `python validate.py` |
| Git | Not for now (costs time); maybe later. `.gitignore` written anyway |
| Scope | Aim for must + should + stretch, must-complete first |

---

## Now — Plan 01: the offline pipeline

Plan: [`plans/01-offline-pipeline.md`](plans/01-offline-pipeline.md).
Goal: `python main.py` and `python validate.py` pass from a clean copy **with no API key**.

- [x] **Step 0 — write the plan** — done (9 Oct) — signed off by Kaysar; both open questions decided: the offline reply uses generic phrase rewrites (agent-only sentences dropped), and trading advice gets one fixed refusal for every advice request.
- [x] **Step 1 — project setup** — done (9 Oct, Kaysar approved) — `.venv` (Python 3.13.5); `requirements.txt` pins the direct dependencies as installed: scikit-learn 1.9.1, pydantic 2.14.0, pytest 9.1.1 (it resolves in a fresh install, checked with `pip install --dry-run --ignore-installed`); `.gitignore` (`.env`, `.venv/`, `.cache/`, caches, and `reference/` since it isn't submitted); `.env.example` (`OPENAI_API_KEY=`, `OPENAI_MODEL=gpt-6-luna`); `pytest.ini` (`tests/`, `pythonpath = .`, a `live` marker skipped by default). `tickets.json` and `kb_articles.json` were extracted from `docs/brief.md` by script, so they're byte-for-byte the brief's text (5 + 5 records). `.env` untouched. A plain `pytest` exits 5 (no tests yet) until Step 2. Follow-ups: scikit-learn 1.9.1 is newer than Claude's training data, so check `TfidfVectorizer` against the installed package in Step 4; numpy/scipy (pulled in by scikit-learn) aren't pinned, so look at that in Plan 04's clean-up.
- [x] **Step 2 — schemas and loading** — done (9 Oct, Kaysar approved) — `triage/schemas.py`: `Intent` (the 6 labels), `Ticket`, `Article`, and `TicketResult` (the brief's output schema, **strict**: `"true"`, `1` and `"0.5"` are rejected, extra fields are forbidden, `confidence` 0–1 inclusive, 1–3 unique article IDs, a non-empty reply). Strict-mode behaviour was checked against the installed pydantic 2.14 first. `triage/data.py`: `load_tickets()` and `load_kb()` raise `DataError` naming the file, the record number and the field (e.g. `tickets.json: record 1: message: Field required`), for a missing file, broken JSON, not a list, a bad or missing field, duplicate IDs, or an empty KB. An empty ticket list and an empty message are allowed (the empty message is classified as `other` later); extra input fields are ignored. 35 free tests pass (`tests/test_schemas.py`, `tests/test_data.py`). Whether article IDs exist in the KB is left to `validation.py` (Step 6), since it needs the KB.
- [x] **Step 3 — the tricky tickets** — done (9 Oct, checkpoint A passed: Kaysar approved the list and all three judgement calls as written) — `tests/data/tricky_tickets.json`: 18 tickets (X01–X18) written before any rules, each with an expected intent, top article (`null` = nothing relevant, so the match must be weak), escalation, the flags it must include, and why it's there. Covers paraphrases, disguised advice, near misses, mixed intents, off-topic, empty, injection, Spanish, and account-detail requests. `tests/test_tricky_tickets.py` checks the file is well formed (37 free tests pass). Judgement calls for Kaysar: X17 (suspension → `other`, not `account_lock`), X11 ("trading hours" is not advice), X02 (locked out + password → `account_lock`). Checkpoint A: Kaysar reads the list.
- [x] **Step 4 — classifier and retriever** — done (9 Oct, Kaysar approved) — **Decision (Kaysar, 9 Oct): "intent narrows, TF-IDF ranks", with plain word TF-IDF.** Kaysar asked whether going straight to the LLM (Plan 02) would solve this instead. No: the no-key path is still required, and the brief forbids external APIs for retrieval, so retrieval must work locally either way.
  - **Retriever done:** `triage/retrieval.py`, the `TfidfRetriever`. At index time the classifier tags each article from its own text (A1 deposit … A5 advice). At query time the on-intent articles come first, ranked by TF-IDF score, then those for other matched intents; up to 3, ties by `article_id`, scores rounded to 6 places. A ticket classified `other` gets the single best TF-IDF article, marked `on_intent=False`. `Classification.ranked_intents` was added to `classify.py`. `tests/test_retrieval.py`: T1 → A1, all samples, all 18 tricky tickets (every expected top article right, and every "nothing relevant" ticket gets exactly one off-intent hit), tags, mixed intents, the 1–3 limit, tie-breaking, determinism across fresh indexes. **99 free tests pass.**
  - **For Step 5 / Plan 03:** plain words score 0.00 on some correct on-intent articles (X05, X06–X08, X12, X15: no shared word forms), so confidence must not rely on the score alone. U1 ("money I sent with my debit card…") was missed by the classifier, but TF-IDF found A1 at 0.33, off-intent. It escalates, which is safe, but it's a possible confidence signal to revisit in Plan 03.
  - **Classifier done:** `triage/classify.py`, the `RuleClassifier`. Patterns per intent; trading advice wins if it matches at all; otherwise the most matches wins, with ties going to the priority order (advice > lock > password > withdrawal > deposit). It returns the matched text per intent and a certainty (`single` / `conflict` / `none`). `tests/test_classify.py`: 29 tests pass (5 samples, 18 tricky, priority/tie/certainty, and each KB article recognised as its own topic). scikit-learn 1.9.1's `TfidfVectorizer` options were checked against the installed package and are unchanged.
  - **Honest number:** the rules were written knowing the tricky set, so 18/18 flatters them. On 10 **unseen** tickets they got **7/10**. The misses ("money I sent with my debit card…", "will EUR/USD rise tomorrow?", "get my money out") all fell to `other`, which escalates: a safe failure, never a wrong answer. The rules were deliberately **not** tuned afterwards.
  - **Retrieval comparison** (top-1 correct on the 17 tickets with a known right article): plain words 10/17, character n-grams 12/17, words with light suffix-stripping 12/17, character n-grams without stop words 13/17, a blend of the last two 12/17. **The minimum-score threshold in the plan can't work with any of them:** tickets no article covers score as high as correct matches (X17 "account suspended" 0.31 vs X01 correct 0.25), because sharing a word like "account" is enough. And tickets like "Is BTC a good buy?" share no words with A5, so no lexical method finds it.
- [x] **Step 5 — generator and policy** — done (9 Oct, checkpoint B passed: Kaysar approved the drafts) — (Kaysar, 9 Oct: no UI and no `--ask` single-ticket option; CLI only, as planned.)
  - `triage/policy.py`: `assess()` → `Assessment(grounded, confidence, escalate, flags, reasons)`. It runs before generation, since the closing line depends on escalation.
    - Flags: `advice_request` (the intent), `insufficient_grounding` (no on-intent article), `policy_sensitive` (any withdrawal match), `account_specific_request` (narrow patterns: "why was/is… my", "status of / where is my", "how long until my", "send/show me my"; "my balance shows zero" alone isn't flagged), `low_confidence` (< 0.6).
    - Confidence = 0.4 × classifier certainty (single 1 / conflict 0.7 / none 0) + 0.4 × on-intent article found + 0.2 × min(1, TF-IDF score / 0.3).
    - Escalate if any risk reason applies, **except** trading advice, which is never escalated (the refusal is complete). Every outcome records a reason for the debug report.
  - `triage/generate.py`: `TemplateGenerator` → `Draft(text, sources)`. For a normal ticket: opening + the top on-intent article's sentences (agent-only sentences dropped, generic rewrites applied) + a closing that depends on escalation. Advice gets the fixed `REFUSAL` (worded after A5, naming no asset or price); no on-intent article gets the fixed `HANDOFF` with no article content.
  - Tests: `tests/test_policy.py`, `tests/test_generate.py`. The T1–T5 table and all 18 tricky expectations are met; every content sentence traces to the cited article; no draft says "client" or "escalating". **145 free tests pass.**
  - **Known weaknesses (for Plan 03 / Plan 02):** (1) confidence is 1.0 on T1–T5 and also on X10 (the fee question, which no article answers). The rules can't tell that an on-topic article doesn't answer the specific question; X10 still escalates via `policy_sensitive`, and its draft explains declines rather than inventing a fee, but the score overstates it. (2) T1 reads "check transaction history" without "your"; fixing that would need an article-specific rewrite, so it's left alone. Checkpoint B: Kaysar reads the T1–T5 drafts.
- [ ] **Step 6 — validation** — review (9 Oct) — done together with Step 7 without a stop in between (Kaysar had 15 minutes left; checkpoint B passed: "looks good"). `triage/validation.py`: hard failures (schema, `ticket_id` mismatch, unknown article, advice wording in any reply, an advice request not refused) → a safe fallback (`REFUSAL` for advice, otherwise `HANDOFF`; `grounded: false`, confidence 0, escalated, plus a flag naming the check). Unsupported claims (a number not in the retrieved text, promise wording like "will be credited", "guaranteed", "within 24") → the reply is kept, with `grounded: false`, `insufficient_grounding` and escalation. `tests/test_validation.py`.
- [ ] **Step 7 — pipeline, CLI, `validate.py`** — review (9 Oct) — `triage/pipeline.py` (the 7 stage functions by name + `run()`, which also writes `debug_report.md`: matched rules, articles with scores, confidence, flags and escalation reasons), `main.py` (`--tickets/--kb/--out`, one summary line per ticket), `validate.py` (the brief's 7 checks; reproducibility = two fresh runs in temp folders, byte-compared), `tests/test_pipeline.py`, and a minimal `README.md` (run/validate, how it works, decisions, limitations). **160 free tests pass; `python main.py` and `python validate.py` both succeed (all 7 checks PASS, exit 0).** **Fresh-copy run done (9 Oct):** only the submission files, a new venv, `pip install -r requirements.txt`, no `.env` → `main.py`, `validate.py` (exit 0) and all tests pass. **Bug found and fixed:** with T4 missing from `results.json`, "T4 is safely refused" still passed; it now fails whenever the tickets include T4 but the results don't. `tests/test_validate_script.py` runs `validate.py` on a copy of the project: it passes on real output, and fails on a missing T4, an answered T4 and an unknown article ID. **164 free tests pass.** `results.json` is generated **offline** (the LLM path doesn't exist yet), which differs from PLANNING's decision 3.
- [ ] **Step 8 — wrap up** — todo — `TASK.md`, `PLANNING.md`, write Plan 02.

## Later

- **Plan 02 — the LLM generator:** `OpenAIGenerator`, grounding checks, the response cache, a live suite (`pytest -m live`, costs cents). **Undecided idea (9 Oct):** when a key is set, ask the LLM (output limited to the 6 labels) about tickets the rules mark `other`, while the rules still run first and trading advice still always wins. It would likely catch the 3 unseen misses, but it conflicts with PLANNING's "intent: rules, not the LLM", so it's Kaysar's call when we write Plan 02.
- **Plan 03 — confidence, flags, debug report:** tune against the T1–T5 table and tricky tickets, the full flag set, `debug_report.md`
- **Plan 04 — ship it:** README, a clean-copy run with and without a key, clean-up, package the submission

---

## Done

- [x] **Project docs set up** — done (9 Oct) — the previous project's README, PLANNING, TASK and plan moved to `reference/faq-bot/` (format reference only); the brief saved verbatim to `docs/brief.md`; `CLAUDE.md` rewritten for this project; `PLANNING.md` written and signed off by Kaysar, with all 3 open questions decided.

---

## Needs an answer

- [ ] **How is the submission uploaded?** A zip, a link, or something else? This decides the packaging in Plan 04. Not needed before then.

---

## Notes

- The challenge asks for specs/design notes in Markdown, written before coding, uploaded with the submission (addendum in `docs/brief.md`). `PLANNING.md` and `plans/` are those notes.
- Leave out of the submission: `reference/`, `.env`, `.venv/`, `.cache/`.
- Update status here as work happens; note follow-ups when marking something done.
