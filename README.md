# Support Ticket Pipeline

A small Python service that reads support tickets and a help-centre knowledge
base, and for each ticket writes a structured reply draft for a human agent:
the intent, the supporting articles, a grounded reply, a confidence score, an
escalation signal and safety flags. It runs fully offline with no API key.

## Run it

Needs Python 3.13.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py                  # writes results.json and debug_report.md
python validate.py              # checks the brief's list, exits 0 if all pass
pytest                          # 164 free tests, no API calls
```

`main.py` takes `--tickets`, `--kb` and `--out` to run on other files.

## How it works

```
LOAD_DATA → INDEX_KB → CLASSIFY_INTENT → RETRIEVE_CONTEXT → GENERATE_REPLY → VALIDATE_OUTPUT → WRITE_RESULTS
```

Each stage is a named function in [`triage/pipeline.py`](triage/pipeline.py).

| Stage | How | File |
|---|---|---|
| Load | pydantic models; a broken input file fails at start-up with the file, record and field named | `data.py`, `schemas.py` |
| Classify | Keyword rules per intent. Trading advice is checked first and always wins. | `classify.py` |
| Retrieve | **Intent narrows, TF-IDF ranks.** The same rules tag each article from its own text; articles tagged with the ticket's intent come first, ranked by TF-IDF (scikit-learn) against the ticket text. 1–3 results, ties broken by ID. | `retrieval.py` |
| Policy | Flags, confidence and escalation, as plain rules | `policy.py` |
| Generate | The retrieved article's own sentences, reworded from agent guidance to customer wording by a generic phrase table. Agent-only sentences are dropped. | `generate.py` |
| Validate | Schema, known article IDs, advice refused. Hard failures become a safe fallback; unsupported claims (numbers not in the sources, promise wording) are flagged and escalated. | `validation.py` |
| Write | `results.json` (the brief's schema exactly) and `debug_report.md` (why each ticket got its intent, articles and escalation) | `pipeline.py` |

## Key decisions

- **Rules for intent, not a model.** Deterministic, free, and detecting trading advice never depends on a model behaving.
- **Trading-advice requests get one fixed, polite refusal**, worded after the no-advice article. It's the same for every advice request (a policy response, not an answer per ticket), and it's never escalated, since the refusal is complete.
- **Why not plain TF-IDF.** On our test tickets no score threshold separated "found it" from "nothing relevant": an off-topic ticket sharing the word "account" outscored correct matches, and "Is BTC a good buy?" shares no words with the no-advice article. Using the intent to narrow the search fixed both. On a 5-article KB the intent mostly decides the article; TF-IDF earns more on a bigger KB with several articles per intent.
- **Tickets nothing covers** (`other`) get a fixed "passed to a specialist" draft with no article content, `grounded: false`, and escalation.
- **Withdrawals are policy-sensitive** and always escalate, as do account-specific questions ("why was my…", "status of my…").
- **Swappable parts.** The classifier, retriever and generator are small interfaces passed into `run()`, so an LLM classifier, embedding search or a hosted-model generator is one new class.

## Testing

- `tests/data/tricky_tickets.json`: 18 tickets written before the rules (paraphrases, disguised advice, near misses, mixed intents, off-topic, empty, injection, Spanish). All behave as expected.
- On 10 tickets the rules had never seen, the classifier got 7 right. All 3 misses fell to `other` and were escalated: a safe failure, never a wrong answer.

## Known limitations

- **Confidence is generous.** The rules can tell a ticket is on topic, but not that the article fails to answer the exact question (e.g. a withdrawal *fee*, which no article covers, still scores 1.0; it is escalated as a withdrawal).
- **The unsupported-claims check is heuristic.** It catches invented numbers and promise wording, not every unsupported sentence.
- **English only.** Other languages fall to `other` and are escalated.
- **Rule coverage.** Paraphrases the rules don't know become `other` and escalate.

## Not built (yet)

An OpenAI generator (planned with a response cache for reproducibility), and
tuning confidence. Design notes, written before the code: [`PLANNING.md`](PLANNING.md),
[`plans/01-offline-pipeline.md`](plans/01-offline-pipeline.md), progress in [`TASK.md`](TASK.md).
The original brief is in [`docs/brief.md`](docs/brief.md).
