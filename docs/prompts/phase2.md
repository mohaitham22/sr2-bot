# Phase 2 prompts for Claude Code — Service Request Bot

Save this file as `docs/prompts/phase2.md` in your repo.

## How to use (for Momo)

**Same rules as Phase 1:**
1. **One step per session.** Type `/clear` before each new step. `CLAUDE.md` and its Progress log carry the memory.
2. **Paste one prompt.** Claude Code teaches, shows a plan, and waits for your **"go"**. It also waits after each file.
3. **👉 Your turn** means Claude Code needs you to do something. Do it, then type "done". Never paste keys in the chat.
4. **Move on only when the step is ✅**, or when you accept a ⚠️ on purpose.
5. **Take each step's "Questions for my instructor"** to your instructor.

**Important:**
- Don't replace the `CLAUDE.md` in your repo with an old copy. The one in your repo has your progress and decisions.
- **Phase 1 must be finished first** (Step 1.12 ✅). Phase 2 uses its outputs:
  - the labeling guide
  - the unit registry
  - the design notes
  - your speech-to-text choice from Step 1.6

## The test set plan (updated again)

**The whole test set is AI-written:** 222 messages written by Claude in chat, in one file, `eval/test_set.csv`, with `author = ai` on every row.

**What this means:**
- **Be honest about it.** The data card, the reports and your final report must say the test set is AI-written. Tell your instructor, because the brief says the interns write it.
- **Scores may look better than reality,** because the training data is also AI-made. Two things reduce this:
  - The test set was written by Claude, so the synthetic training data (Step 2.6) must come from a **different** model (Groq or Gemini, never Claude). Then the two don't share one writing style.
  - Step 2.6 runs a leakage check, so no training message is too similar to a test message.
- **Optional, but valuable:** later, add 20–40 messages written by real people (teammates, friends) as a small "reality check" file, scored separately.

**What's in it:**
- **Categories:** plumbing 45, electricity 40, AC 40, general 37, pest control 30, carpentry 30
- **Urgency:** medium 110, low 65, high 47
- **Language:** Arabic 122 (17 of them Franco-Arabic), English 69, mixed 31
- **Realistic mess:** Arabic digits (46), short or misspelled compound names (45), typos, very short (12) and long (7) messages, self-corrections (6)
- **Edge cases**, tagged `check_guide` in the notes: two problems (6), gas (3), water heater (3), vague (6), and a few borderline categories. Claude Code checks them against your labeling guide.
- **Missing details are on purpose:** real residents' first messages rarely include everything. Only 45 messages have the full location, and 24 have no details at all. This tests follow-up questions and hallucination.

**Order:** Step 2.1 (review and check) → freeze → Steps 2.2–2.13.

**Plan:** about 1 step per day for 2 weeks.

## Steps

| Step | Title | Role |
|---|---|---|
| 2.0 | Phase 2 kickoff (no code) | All |
| 2.1 | Test set: review, check, prepare to freeze | Data & ML |
| — | **Freeze the test set** | Data & ML |
| 2.2 | Database models + Alembic migrations | Backend & Memory |
| 2.3 | Redis session store | Backend & Memory |
| 2.4 | LLM client (Groq / Gemini) | LLM & Speech |
| 2.5 | Speech-to-text service | LLM & Speech |
| 2.6 | Synthetic training data + translated subset | Data & ML |
| 2.7 | Baseline classifier + MLflow | Data & ML |
| 2.8 | Extraction: schema + prompt + evaluation | LLM & Speech |
| 2.9 | Follow-up questions + re-ask logic | LLM & Speech |
| 2.10 | LangGraph state and flow skeleton | Backend & Memory |
| 2.11 | Dockerfile + stronger CI | Dashboard & DevOps |
| 2.12 | Metabase + fake rows | Dashboard & DevOps |
| 2.13 | Phase 2 review | All |

---

## Step 2.0 — Phase 2 kickoff (no code)
**You'll need:** nothing.

```text
Step 2.0 — Phase 2 kickoff
Phase 2 · All roles

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

This step has NO code.

1. Check Phase 1 is really finished: is Step 1.12 ✅? Do these exist?
   - docs/labeling_guide.md
   - the mock unit registry
   - docs/data_card.md
   - docs/design_notes.md
   - my speech-to-text choice in section 13
   If anything is missing, STOP, show me a list, and tell me which Phase 1 step to resume.
2. Explain Phase 2 in simple English:
   - its goal ("each piece works on its own")
   - the tasks for each role
   - how each piece connects to the others in Phase 3
3. Explain the test set plan and the step order in docs/prompts/phase2.md: the test set is AI-written (eval/test_set.csv). Explain what that means for our scores, and how we reduce the risk (a different model for the training data, and a leakage check). Teach me: train / validation / test sets, data leakage, and why we never tune on the test set.
4. From Phase 2, propose a git workflow: one branch per step, and a pull request (PR) to merge into main. The brief says all PRs are reviewed. Explain branches and PRs, and how you can review my PRs like a teammate. I decide.
5. Update CLAUDE.md:
   - Under Phase 2 in section 12, add: "Step-by-step prompts: docs/prompts/phase2.md (Steps 2.0–2.13)" and the step order.
   - Log the order and my git workflow decision in section 13.
6. Quiz me: 5 short questions about Phase 2. Wait for my answers, then correct me.

How to work: follow CLAUDE.md section 2.
When the step is done: add a section 15 entry with an honest status, show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.1 — Test set: review, check, prepare to freeze
**You'll need:** `test_set.csv` from Claude chat, saved as `eval/test_set.csv`.

```text
Step 2.1 — Test set: review, check, and prepare to freeze
Phase 2 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Context: the test set plan changed. The whole test set is AI-written: 222 messages written by Claude (chat), in eval/test_set.csv, with author = ai on every row. I will tell my instructor. If CLAUDE.md or any file still describes an older plan (me writing it, Google Forms, Part A / Part B), update it to this plan.

Columns: id, text, language, category, urgency, compound, building, unit_number, name, phone, author, notes.
- The expected fields are normalized (unit like B-204, phone like 01012345678). Empty means "not in the text".
- The notes column has tags: franco, arabic_digits, short_compound, typo, very_short, long, self_correction, two_problems, vague, gas, water_heater, check_guide.

1. Update CLAUDE.md:
   - Section 13: log the decision (AI-written test set), why, and the risks.
   - Section 12: change the Phase 2 box "Hand-write 200–300 test requests" to "AI-written test set (eval/test_set.csv): reviewed and frozen".
   - Section 9: keep the rule that the test set is never used for training or as prompt examples, and add: the synthetic training data must come from a different model family than the test set (never Claude).
2. Explain each column to me, and why empty fields matter (hallucination).
3. Check the file against docs/labeling_guide.md and the unit registry:
   - every category and urgency, especially the rows tagged check_guide (gas, water heater, two problems, vague)
   - compound names: the file uses Cedar Park, Lotus Ridge and Nakhla Residence. If our registry uses different names, propose how to replace them in BOTH the text and the expected fields.
   - unit and phone formats
   Show me every row you would change, with your reason. I decide. Don't rewrite message texts unless a change is needed for the registry.
4. Realism review: show me 30 random messages. I mark any that don't sound like a real Egyptian resident, and you fix only those.
5. eval/check_test_set.py: checks the columns, allowed labels, phone format, compounds in the registry, duplicates, and that each expected value really appears in the text (after converting Arabic digits). It prints coverage (category, urgency, language, tags) and the SHA-256 hash.
6. Update docs/data_card.md: who wrote the test set (AI, with the date), why, and its limits.

Teach me: test set vs validation set, why an AI-written test set can give optimistic scores, how a different model and a leakage check reduce that risk, hallucination, class balance, and what a hash proves.

After this step, I will run the "Freeze the test set" prompt.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Freeze the test set (right after Step 2.1)
**You'll need:** Step 2.1 done.

```text
I want to freeze the test set. Before anything else, read CLAUDE.md and the Progress log.

1. Run eval/check_test_set.py and show me the coverage and any problems. Help me fix them one by one.
2. Read 20 random rows and tell me if any label looks inconsistent with docs/labeling_guide.md. Explain your reasoning; I decide.
3. When it's clean: record the row count and SHA-256 hash in CLAUDE.md section 13 as "Test set frozen", and update the data card.
4. Explain why we must not change it from now on, and what to do if I find a real labeling mistake later (fix it, record a new hash, and note it in section 13).
5. Ask me before committing.
End with the full summary from CLAUDE.md section 2.
```

---

## Step 2.2 — Database models + Alembic migrations
**You'll need:** Postgres running in Docker (from Step 1.2).

```text
Step 2.2 — Database models and migrations
Phase 2 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: create the real PostgreSQL tables from our design (CLAUDE.md section 7 and docs/design_notes.md).

Build (ask me before adding each dependency: SQLAlchemy 2 async, asyncpg, Alembic):
1. app/db/models.py with the tables:
   - users, units, user_units, service_requests, messages, predictions
   - primary keys, foreign keys, unique constraints, NOT NULL where needed
   - timestamps stored in UTC
   - the ticket number format from Step 1.11
2. app/db/session.py: the async engine and session, reading DATABASE_URL from app/config.py.
3. Alembic set up in migrations/, and the first migration. Generate it, then walk me through the migration file line by line before we apply it.
4. Make sure two requests at the same moment can never get the same ticket number. Explain how (e.g. a database sequence).
5. Indexes that the dashboard will need (e.g. on created_at, category, status). Explain why each one helps.
6. A seed script that loads the unit registry into the units table. It must be safe to run twice.
7. Integration tests against the real Postgres in Docker: create a user, a unit and an SR; check the constraints work (a duplicate unit must fail).

Teach me: ORM vs raw SQL, async database access, migrations (why we never change tables by hand), primary/foreign keys, constraints, indexes, why we store time in UTC, and why the phone column is personal data (CLAUDE.md section 9).

Check: alembic upgrade head works; alembic downgrade -1 and upgrade again works (explain why we test both); the seed script works twice; tests pass.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.3 — Redis session store
**You'll need:** Redis running in Docker (from Step 1.2).

```text
Step 2.3 — Redis session store
Phase 2 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: the bot's short-term memory, following the brief's memory design (CLAUDE.md section 8).

Build:
1. A Pydantic model for the session: collected fields, missing fields, current step, language, last update time.
2. app/memory/session.py with these functions:
   - get, save and clear the session (key session:{chat_id})
   - add a message to history (key history:{chat_id}) and keep only the last N turns
   - clear everything for /reset
   Use a 30-minute expiry that restarts on every new message ("sliding expiry"). Explain why sliding.
3. N and the TTL come from app/config.py, not hard-coded.
4. Tests against the real Redis in Docker: save and load, history trimming, /reset, and expiry. Use a very short TTL in tests so they run fast.
5. Should tests use real Redis or a fake one (e.g. fakeredis)? Show me the options with pros and cons. I decide.

Teach me: key-value stores, TTL and sliding expiry, why session data lives in Redis and not Postgres, serialization (Python object → JSON → Redis), and why the phone in a session is still personal data (never log it).

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.4 — LLM client (Groq / Gemini)
**You'll need:** your Groq and Gemini keys in `.env` (from Step 1.6).

```text
Step 2.4 — LLM client
Phase 2 · LLM & Speech

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: ONE place in the code that talks to the LLM (app/services/llm.py), so we can switch Groq ↔ Gemini ↔ Azure OpenAI by changing .env only.

1. Check the current docs, then show me options: the official Groq and Gemini SDKs, or one OpenAI-compatible client for both. Also check what each provider supports for JSON output ("JSON mode" or "structured outputs" with a schema), since the brief asks for validated JSON. I decide.
2. Build app/services/llm.py:
   - provider and model names from .env
   - a timeout
   - retry with exponential backoff and jitter on HTTP 429 and 5xx
   - temperature set per call
   - a JSON-output function that validates the answer with a Pydantic model
3. For every call, record:
   - latency
   - input and output token counts
   - model name
   Never record the message content (it can contain names and phones). We need these numbers in Phase 4 for the ML vs LLM comparison (latency and cost per request).
4. Unit tests with the LLM mocked (no real calls in tests or CI). Then ONE small manual test with a real call, using a harmless sentence, to show me it works.

Teach me: what an LLM API call is (messages, roles, tokens), temperature, rate limits (RPM, RPD), exponential backoff and jitter, JSON mode vs structured outputs, and why we hide the provider behind one module.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.5 — Speech-to-text service
**You'll need:** your voice notes from Step 1.6.

```text
Step 2.5 — Speech-to-text service
Phase 2 · LLM & Speech

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: turn the Step 1.6 experiment into a clean, reusable service: app/services/stt.py.

Build:
1. Use the model and settings I chose in Step 1.6 (section 13 and eval/reports/whisper_phase1.md): the model, the language setting, and the vocabulary prompt if we kept one.
2. A clear interface: transcribe(audio file) returns a Pydantic object with:
   - text
   - detected language
   - audio duration
   - model name
   - seconds taken
   - quality signals if the API gives them (e.g. avg_logprob, no_speech_prob), for the "please confirm the transcript" fallback in Phase 4
3. Guards:
   - a file size limit (25 MB)
   - a timeout and retry on 429
   - a clear error for unsupported formats
4. Ask me: do we add the local faster-whisper model as a backup, used when Groq fails? Show pros and cons. I decide.
5. Unit tests with the API mocked.
6. A regression check: run the service on my voice notes, re-score them with the Step 1.6 scoring code, and confirm the results match the report. Explain what a regression test is.

Teach me: service interfaces (why the rest of the app should not know which STT provider we use), fallbacks, and regression testing.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.6 — Synthetic training data + translated subset
**You'll need:** the frozen test set. Generation uses your free LLM quota, so it may take a few days.

```text
Step 2.6 — Synthetic training data and a translated subset
Phase 2 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are. Check that the test set is frozen (section 13). If not, stop.

Goal: create the training data, as the brief says: "LLM-generated synthetic requests modeled on the 311 data, plus a translated subset."

Plan first, and show me before generating anything:
1. Use what we learned in Step 1.7 about the 311 data (the complaint types and descriptors, and whether it has resident text) and the mapping from Step 1.8.
2. Generate from known "slot values": pick the category, urgency, compound/building/unit from the registry, a fake name and phone, the language and the style first, then ask the LLM to write a message with those values. This way every message comes with correct labels for BOTH the classifier and the extraction. Explain why this is powerful. Use Groq or Gemini to generate, never Claude: our test set was written by Claude, and a different model keeps the two from sharing one writing style.
3. A diversity plan, as a table: categories × urgency × language (Egyptian Arabic, English, mixed) × style (short, long, angry, polite, typos, Arabic digits) × missing fields. Propose a total size and explain the trade-off. I decide.
4. Estimate how many API calls this needs and how long it takes with free-tier limits. Generation must save progress and resume (checkpointing), so a rate-limit stop doesn't lose work.
5. The translated subset: translate part of the English data into Egyptian Arabic. Teach me "translationese" and why we keep a source column (synthetic_ar, synthetic_en, translated).

After my "go", build:
6. The generation prompt as a versioned file (e.g. ml/prompts/synth_v1.md) and ml/generate_synthetic.py.
7. Quality checks:
   - JSON validation
   - exact and near-duplicate removal
   - a leakage check: no synthetic message may be very similar to any test-set message
8. A human check: show me 40 random examples. I rate each as good / bad / wrong label, and we fix the prompt if needed.
9. Save the dataset with its source, generator model name and prompt version (data lineage). Ask me where to store it (git or git-ignored + MLflow artifact); show pros and cons.
10. Update docs/data_card.md: how it was made, the provider's terms for generated text, and known limits.

Teach me: synthetic data, slot filling, diversity vs quality, label noise, near-duplicates and how we measure similarity, data lineage, and why the training data must come from a different model than the test set.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.7 — Baseline classifier + MLflow
**You'll need:** the synthetic data and the frozen test set.

```text
Step 2.7 — Baseline classifier (TF-IDF + logistic regression) with MLflow
Phase 2 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: the first real model. Two classifiers (category and urgency), tracked in MLflow, with a score on the frozen test set. The test set is AI-written, so say so next to every score.

Plan first, and show me before coding:
1. Arabic text normalization: alef forms, ta marbuta, ya / alef maqsura, removing tashkeel, Arabic-Indic digits → 0–9. Show me before/after examples.
2. Features: word TF-IDF plus character n-grams. Explain why character n-grams help with Arabic dialect spelling and typos.
3. Splits: train / validation from the synthetic data only, stratified. Messages made from the same seed should stay on the same side (a group split). The test set is used only for the final score.
4. Metric: the brief says "F1 ≥ 0.85" but not which F1. Explain macro vs weighted F1. I choose the headline metric; we report both.

After my "go", build:
5. ml/train_baseline.py:
   - normalization → TF-IDF → LogisticRegression (try class_weight="balanced")
   - tune a few settings on the VALIDATION set only
   - then evaluate ONCE on the test set
6. MLflow logging (ask me before adding mlflow):
   - parameters
   - metrics on validation and test
   - per-class F1
   - confusion-matrix images
   - the dataset version or hash
   - the saved model
7. Save each model as a versioned file (e.g. ml/models/category_baseline_v1.joblib), plus a small predict function that returns the label and a confidence score (the highest probability). Phase 3 wraps this in app/services/classifier.py.
8. A short report in eval/reports/baseline_phase2.md:
   - validation vs test scores, and THE GAP between them (the brief asks for the gap between synthetic and real-style performance; say clearly that our test set is AI-written, so the real gap is probably bigger)
   - scores by language and by tag (franco, arabic_digits, typo, very_short, ...), to find weak spots
   - a confidence interval for the main score (e.g. bootstrap)
   - per-class results
   - the 15 worst test errors, with my comments on why they failed

Teach me: TF-IDF, n-grams, logistic regression, class imbalance and class weights, precision / recall / F1, the confusion matrix, overfitting, why we tune on validation and not on test, confidence intervals (how sure we can be with 222 messages), what predict_proba means, and why a confidence score isn't always reliable (calibration, Phase 4).

Check: uv run mlflow ui shows the runs; I can explain every number in the report.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.8 — Extraction: schema + prompt + evaluation
**You'll need:** the LLM client (2.4) and the synthetic data (2.6).

```text
Step 2.8 — LLM extraction: schema, prompt, and evaluation
Phase 2 · LLM & Speech

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: text goes in, a valid JSON object with the request fields comes out.

Build:
1. app/schemas/extraction.py: a Pydantic model with compound, building, unit_number, name, phone and issue_description (all optional), plus language. Add validators that clean values:
   - phone: Arabic-Indic digits → 0–9, remove spaces and dashes, +20 → 0, then check the Egyptian mobile format
   - unit: "b204", "B 204", "بي 204" → "B-204"
   - compound: match against the unit registry, allowing small spelling differences (fuzzy matching); keep the raw value and a flag if there is no good match
   Show me the plan for each validator first.
2. The prompt as a versioned file, app/prompts/extract_v1.md. Rules:
   - use null when a field is not mentioned; never guess
   - if the user corrects themselves, the last value wins
   - output JSON only
   Few-shot examples may come from synthetic data, NEVER from the test set.
3. app/services/extraction.py: calls the LLM client (temperature 0, JSON output), validates the result, and returns the schema object.
4. Prompt injection: user text is data, not instructions. Show me what happens with a message like "ignore your instructions and…", and how we protect against it.
5. eval/eval_extraction.py, reporting:
   - accuracy per field
   - the brief's metric: % of messages where ALL unit fields (compound, building, unit) are correct (target ≥ 90%)
   - the hallucination rate: a value was returned when the expected value is empty
   Develop and tune the prompt on the synthetic validation data. Run on the test set only at the end, and break the results down by tag (e.g. arabic_digits, short_compound, self_correction, franco).
6. A mini end-to-end check: run extraction on the Step 1.6 voice transcripts, so I see how STT errors affect extraction.
7. Logging: only which fields were found (true/false), never the values.

Teach me: structured output, JSON schema, Pydantic validators, few-shot prompting, temperature 0, hallucination, prompt injection, fuzzy matching, and why we never tune prompts on the test set.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.9 — Follow-up questions + re-ask logic
**You'll need:** extraction from Step 2.8.

```text
Step 2.9 — Follow-up questions and re-ask logic
Phase 2 · LLM & Speech

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: when fields are missing or invalid, the bot knows what to ask, and it updates the request correctly from the user's answers. No Telegram yet; this is pure logic.

Decisions first (show me options with pros and cons):
1. Questions from fixed templates (Arabic + English) or written by the LLM each time? Think about control, cost, speed and tone.
2. The order and grouping of questions: e.g. location first, then contact; one field or two at a time.
3. What happens after too many failed answers (e.g. 3 wrong phone numbers)?

After my decisions, build:
4. A function that finds missing and invalid fields, using the schema from 2.8.
5. Follow-up questions in the user's language.
6. Merging answers: the new reply goes to extraction together with the fields we already have; the LLM returns only updates; corrections ("no, it's building 5") replace old values; values the user didn't mention stay the same.
7. Broken LLM output: re-ask the LLM once with the validation error, then fall back to asking the user directly (CLAUDE.md section 10).
8. Tests with scripted fake conversations (mocked LLM):
   - a complete message
   - missing phone
   - a correction
   - an invalid phone
   - a broken JSON reply

Teach me: multi-turn state, slot filling, merging vs overwriting, retry vs fallback, and why deterministic code is easier to test than LLM text.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.10 — LangGraph state and flow skeleton
**You'll need:** nothing new.

```text
Step 2.10 — LangGraph state and flow skeleton
Phase 2 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: define the conversation as a graph (CLAUDE.md section 4), with the state and the edges. The nodes can be simple stubs. Phase 3 connects the real services and Telegram.

Decisions first (check the current LangGraph docs, then show me options with pros and cons):
1. The state schema: which fields, TypedDict or Pydantic.
2. How the graph waits for the user's next message: run the graph once per message (loading state from Redis), or use LangGraph's interrupt / human-in-the-loop feature.
3. Where state is saved: our own session store from Step 2.3, or a LangGraph checkpointer (Redis or Postgres). I decide.

After my decisions, build (ask me before adding langgraph):
4. app/graph/state.py and app/graph/flow.py with the nodes transcribe, extract, ask_missing, confirm, classify, save and reply, and conditional edges:
   - voice? → transcribe
   - fields missing? → ask_missing
   - user confirms? → classify; user edits? → extract
5. Stub nodes that return fake data, so the graph runs end to end without real APIs.
6. Draw the graph as a Mermaid diagram and add it to docs/design_notes.md.
7. Tests: run 3 fake conversations through the graph (complete text, voice with missing fields, an edit at the confirm step) and check the path taken.

Teach me: state machines, graphs, nodes and edges, conditional routing, why LangGraph instead of many if/else statements, and checkpointing.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.11 — Dockerfile + stronger CI
**You'll need:** Rancher Desktop running, and your GitHub repo.

```text
Step 2.11 — Dockerfile and stronger CI
Phase 2 · Dashboard & DevOps

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: package the app in a Docker image, and make CI protect the main branch.

Build:
1. A Dockerfile:
   - Python 3.12 slim, using uv
   - multi-stage build (explain why)
   - runs as a non-root user
   - no secrets inside the image
2. A .dockerignore that keeps out: .env, .git, data folders, audio, mlruns, and docs/project_brief.pdf.
3. Build the image and show me its size. Run the tests inside the container.
4. Upgrade CI (.github/workflows/ci.yml):
   - mark tests as unit or integration (pytest markers)
   - run integration tests against Postgres and Redis "service containers"
   - build the Docker image in CI (no push yet)
   - use caching to keep it fast
5. 👉 Guide me to turn on branch protection on GitHub: CI must pass before a PR can merge into main.
6. Learning test: open a PR with a failing test, show me the merge is blocked, then fix it.

Teach me: images vs containers (review), multi-stage builds, layers and caching, why non-root, .dockerignore, service containers in CI, test markers, and branch protection.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.12 — Metabase + fake rows
**You'll need:** Postgres with the tables from Step 2.2.

```text
Step 2.12 — Metabase connected to Postgres, with fake rows
Phase 2 · Dashboard & DevOps

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: Metabase runs locally and reads our database, so we can build the dashboard in Phase 4.

Build:
1. Add Metabase (open-source, pinned version) to docker-compose.yml, on 127.0.0.1:3000 with a volume.
   Decision: Metabase's own settings database, the default H2 file or a separate Postgres database? Show me pros and cons. I decide.
2. A read-only Postgres user for Metabase (credentials in .env). Explain "least privilege": the dashboard should never be able to change data.
3. scripts/seed_fake_data.py: fake users, units and about 300 service requests over the last 60 days, with:
   - realistic category and urgency mixes
   - statuses (open / in_progress / closed), with closed_at for closed ones
   - a fixed random seed (same data every run)
   - fake names and phones only
   - a clear way to delete all fake rows later (propose how)
4. 👉 Guide me to connect Metabase to Postgres with the read-only user, and to build two first questions: SRs per day and SRs by category. The full dashboard is Phase 4.
5. Check the dashboard list in docs/design_notes.md: can every planned chart be built from our tables? List anything missing.

Teach me: what a BI tool does, Metabase questions and dashboards, the app database vs the data database, least privilege, and seed data.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 2.13 — Phase 2 review
**You'll need:** about an hour.

```text
Step 2.13 — Phase 2 review
Phase 2 · All roles

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: check that Phase 2 really works, and that we are ready for the week-6 gate.

1. Go through every Phase 2 box in section 12. Run each check again yourself (tests, ruff, migrations, CI, scripts) and show me a table: task, status (✅ / ⚠️ / ❌), evidence.
2. Check the brief's end-of-phase criteria with real runs:
   - Text in → valid JSON out: run extraction on 5 synthetic messages and 2 voice-note transcripts and show the results.
   - A baseline F1 number on the frozen test set (marked as AI-written), plus the gap to the synthetic validation score.
   - The classifier is ready for Phase 3: a versioned model file, a predict function, and a test.
3. Show me the current scores next to the brief's targets (section 11): what is on track and what is at risk.
4. List what must be fixed before Phase 3, and fix it with me one item at a time.
5. Write docs/phase2_summary.md for my instructor (one page):
   - what we built
   - the decisions and why
   - the scores
   - the risks for the week-6 gate
   - open questions
6. Clean up CLAUDE.md: move the Phase 2 entries from section 15 to docs/progress_log.md, leave a 3-line Phase 2 summary, and move ◀ to Phase 3.
7. Ask me before committing and before adding the git tag phase-2-done.

Teach me: integration risk (pieces that work alone can still fail together) and why Phase 3 is the most important checkpoint.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md as described above, show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Helper prompts (use any time)

**Resume a step** (new session, same step):
```text
Continue Step 2.x. First read CLAUDE.md and this step's Progress log entry, and tell me in simple words what is done and what is left. Then continue, following CLAUDE.md section 2.
```

**Explain again:**
```text
I didn't understand <topic>. Explain it again more simply: one analogy, one tiny example from our project, and one common mistake. Don't change any files.
```

**Quiz me before meeting my instructor:**
```text
Quiz me on Step 2.x: 5 questions, from easy to hard. Wait for my answers, then correct me. Don't change any files.
```

**Review code I wrote myself:**
```text
I wrote <file> myself. Review it like a senior engineer: what is good, what is wrong, and why. Give hints; don't rewrite it.
```

**Review my pull request:**
```text
Review my pull request for Step 2.x like a teammate (the brief says all PRs are reviewed). Check: does it match CLAUDE.md, are there tests, any personal data in logs, any secrets, anything I should understand better. Don't change files; list comments I can reply to.
```
