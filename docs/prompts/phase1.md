# Phase 1 prompts for Claude Code — Service Request Bot

Save this file as `docs/prompts/phase1.md` in your repo.

## How to use (for Momo)

**Before Step 1.0:**
1. Create the project folder.
2. Put `CLAUDE.md` in the root.
3. Copy the brief to `docs/project_brief.pdf`.
4. Open Claude Code in that folder.

**Every step:**
1. **One step per session.** Type `/clear` before each new step so Claude Code starts fresh. `CLAUDE.md` and its Progress log carry the memory between sessions.
2. **Paste one prompt.** Claude Code will explain the theory, show a plan, and wait for your **"go"**. It will also wait after each file. Read, ask questions, then say "go".
3. **👉 Your turn** means Claude Code needs you to do something: create an account, fill `.env`, record audio, or make a decision. Do it, then type "done". Never paste keys or tokens into the chat.
4. **Move on only when the step is ✅**, or when you accept a ⚠️ on purpose.
5. **Take each step's "Questions for my instructor"** to your instructor.

If a session ends in the middle of a step, use the **Resume** prompt at the bottom.

## Steps

**Order:** setup → bot → Whisper test → data → design → review.
- Setup comes first because everything needs it.
- The Whisper test comes early because Egyptian Arabic transcription is the brief's top risk.

| Step | Title | Role |
|---|---|---|
| 1.0 | Understand the project (no code) | All |
| 1.1 | Project skeleton and settings | Backend & Memory |
| 1.2 | Postgres and Redis in Docker | Dashboard & DevOps |
| 1.3 | CI with GitHub Actions | Dashboard & DevOps |
| 1.4 | Telegram bot: text | Backend & Memory |
| 1.5 | Telegram bot: voice notes | Backend & Memory |
| 1.6 | Early Whisper test on Egyptian Arabic | LLM & Speech |
| 1.7 | Explore the NYC 311 data | Data & ML |
| 1.8 | Category and urgency mapping + labeling guide | Data & ML |
| 1.9 | Mock unit registry | Backend & Memory |
| 1.10 | Data card | Data & ML |
| 1.11 | Design notes: fields, DB sketch, dashboard charts | LLM & Speech, Backend, DevOps |
| 1.12 | Phase 1 review and scope freeze | All |

---

## Step 1.0 — Understand the project (no code)
**You'll need:** nothing.

```text
Step 1.0 — Understand the project before we build
Phase 1 · All roles

Before anything else: read CLAUDE.md and docs/project_brief.pdf fully.

This step has NO code. Goal: I understand the whole project before we build anything.

1. Explain the project to me like I'm a new team member:
   - the problem it solves and for whom
   - the journey of one request, from the resident's voice note to the dashboard, step by step
   - what each part does (Telegram bot, FastAPI, LangGraph, Whisper, LLM, classifier, Redis, PostgreSQL, Metabase, Langfuse, Docker, GitHub Actions), with one simple analogy each
   - the 4 roles and the 6 phases, and why the week-6 gate matters most
2. Explain Phase 1: its goal, the tasks for each role, the order we will follow (setup → bot → Whisper test → data → design → review), and why.
3. Check my computer, but don't install anything: are git, Python, uv, Docker (or Rancher Desktop) and docker compose installed? Show the versions. This may be my Emaar work laptop, so list what is missing and I will get it installed.
4. Check that docs/project_brief.pdf exists.
5. Quiz me: ask 5 short questions about the project. Wait for my answers, then correct me kindly.

The only file you may change in this step is CLAUDE.md (section 15, Progress log).

How to work: follow CLAUDE.md section 2.
When the step is done: add a section 15 entry with an honest status, show me the change, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.1 — Project skeleton and settings
**You'll need:** uv installed and a GitHub account.

```text
Step 1.1 — Project skeleton and settings
Phase 1 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: create the empty project structure and a safe way to load settings and secrets.

Build (one at a time, waiting for me between files):
1. Git: git init, and a .gitignore for Python. It must ignore .env, .venv/, ml/data/raw/, ml/data/processed/, mlruns/, and audio files (*.ogg, *.mp3, *.wav).
2. pyproject.toml with uv, Python 3.12. Add only what this step needs: pydantic-settings, plus dev tools ruff and pytest. Don't add libraries for later steps.
3. The folders from CLAUDE.md section 5, as empty Python packages (__init__.py). Don't create files for later phases.
4. .env.example with variable names and short comments only, no real values: TELEGRAM_BOT_TOKEN, GROQ_API_KEY, GEMINI_API_KEY, STT_MODEL, DATABASE_URL, REDIS_URL. Later steps will add more.
5. app/config.py: a pydantic-settings Settings class that reads .env. Secrets use SecretStr so they never print by accident.
6. tests/test_config.py: a small test that settings load and that secrets are hidden when printed.

Teach me: virtual environments, what pyproject.toml and the lock file are for, environment variables, why secrets never go in git, what .gitignore does, and what SecretStr protects against.

Check:
- uv run pytest passes. It must also pass in CI later, where there is no .env file.
- uv run ruff check . is clean.
- git status does not show .env.
Ask me before the first commit. Then help me create a PRIVATE GitHub repo, and push only after I say yes.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.2 — Postgres and Redis in Docker
**You'll need:** Rancher Desktop (or Docker Engine) installed.

```text
Step 1.2 — Postgres and Redis in Docker
Phase 1 · Dashboard & DevOps

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: run PostgreSQL and Redis on my laptop in containers.

Build:
1. docker-compose.yml with two services: postgres (version 16) and redis (version 7).
   - Named volumes so data survives restarts.
   - Healthchecks for both.
   - Ports bound to 127.0.0.1 only.
   - The Postgres user, password and database name come from .env, not written in the file. Add them to .env.example.
2. Update DATABASE_URL and REDIS_URL in .env.example to match.
Don't create any tables yet; that is Phase 2.

Teach me: image vs container, volumes, port mapping, healthchecks, why we bind to 127.0.0.1, and why we need two databases (Postgres = long-term memory, Redis = short-term memory).

Check:
- docker compose ps shows both services healthy.
- Postgres answers SELECT version(); and Redis answers PING with PONG.
- Data survives a restart: create a small test table, restart the containers, check it is still there, then drop it (ask me before dropping).
If Docker is not installed, stop and tell me how to install Rancher Desktop. Not Docker Desktop: it needs a paid license at big companies.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.3 — CI with GitHub Actions
**You'll need:** your private GitHub repo from Step 1.1.

```text
Step 1.3 — CI with GitHub Actions
Phase 1 · Dashboard & DevOps

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: GitHub checks my code automatically on every push.

Build: .github/workflows/ci.yml that runs on push and on pull request. It installs uv and the dependencies, then runs ruff check, ruff format --check, and pytest.
CI needs no secrets, and tests must never call real APIs.

Teach me: what CI is and why teams use it, workflow vs job vs step, the difference between linting, formatting and testing, and caching.

Check:
- Ask me before pushing. After the push, tell me where to see the result on GitHub.
- Learning test: on a new branch, add a small formatting mistake on purpose, push it, and show me the red ✗. Then fix it and show me the green ✓. Delete the branch afterwards (ask me first).

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.4 — Telegram bot: text
**You'll need:** Telegram on your phone, to create the bot with @BotFather.

```text
Step 1.4 — Telegram bot: text
Phase 1 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: a Telegram bot that runs on my laptop and replies to text.

Build:
1. Ask me before adding the aiogram (version 3) dependency.
2. Bot code in app/bot/: a /start command that says hello and explains what the bot will do, and an echo reply for normal text.
3. app/bot/polling.py, so that uv run python -m app.bot.polling starts the bot.
4. Logging: log only the update type, the chat ID and the message length. Never log the message text, because later messages will contain names and phone numbers (CLAUDE.md section 9).
5. A small unit test for the echo handler that does not connect to Telegram.

Teach me: how a Telegram bot works (the Bot API and updates), polling vs webhook and why we use polling now, async/await and the event loop, and aiogram's Dispatcher, Router and handlers.

I need to create the bot with @BotFather and put the token in .env. Give me exact steps in 👉 Your turn. Don't ask me to paste the token in the chat.

Check: /start works, text gets echoed, the token never appears in logs, and Ctrl+C stops the bot cleanly.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.5 — Telegram bot: voice notes
**You'll need:** the bot from Step 1.4 running.

```text
Step 1.5 — Telegram bot: voice notes
Phase 1 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: the bot accepts voice notes and saves them, so I can use it to record test audio for Step 1.6.

Build:
1. Handle voice messages: download the .ogg file and save it to eval/voice/raw/ with a clear name (date + number). This folder must be git-ignored.
2. Reply with the duration and file size, so I know it arrived.
3. For other message types (photo, sticker, file), reply politely that the bot reads text and voice notes only.

Teach me: how Telegram stores files (file_id, getFile, download), what OGG/Opus is, file size limits, and why we keep audio out of git.

Check: I send 2 voice notes. The files exist, they play correctly, and they do not appear in git status.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.6 — Early Whisper test on Egyptian Arabic
**You'll need:** Groq and Gemini accounts, about 30 minutes to record 15 voice notes, fake names and phone numbers, and about 7 GB of free disk space for the Whisper models.

```text
Step 1.6 — Early Whisper test on Egyptian Arabic
Phase 1 · LLM & Speech

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: test early whether self-hosted Whisper understands Egyptian Arabic well enough, and which model size we need. The brief lists this as a top risk ("test Whisper sizes early"). We use faster-whisper on the CPU (CLAUDE.md section 13).

My part comes first. Give me exact steps in 👉 Your turn:
- Get a Groq API key and a Gemini API key, and put both in .env. Groq is for the LLM (Phase 2) and the cloud comparison below; Gemini is the backup LLM (Phase 2).
- Record test voice notes through the bot: 10 in Egyptian Arabic and 5 in English, like real maintenance complaints. Include unit numbers (e.g. B-204), building numbers and phone numbers, and make a few with background noise. Fake names and phone numbers only.
- Write down what I actually said in each note in eval/voice/reference.csv (file name, language, text).

Then build:
1. Ask me before adding the faster-whisper and groq packages. Tell me where the models will be downloaded and how much space they need.
2. eval/whisper_test.py: transcribe every file in eval/voice/raw/ with self-hosted faster-whisper on the CPU (int8), using the sizes small, medium, large-v3 and large-v3-turbo, once with automatic language detection and once with the language set. Save the results to eval/voice/results.csv (file, engine, model, language setting, transcript, seconds taken, real-time factor).
3. Comparison only, never used in the app: run the same files through the Groq Whisper API (whisper-large-v3) and add them to results.csv. Retry with a pause on rate limits (HTTP 429).
4. Help me score each transcript against my reference: is it usable for extraction (yes/no)? Are the unit number and phone digits correct?
5. A short report in eval/reports/whisper_phase1.md: a results table, the % usable per model (the brief's target is 85% or more), the speed of each model on the CPU, self-hosted vs Groq, which setting worked best, and common mistakes. Recommend a model size; I decide.

Teach me: how Whisper works at a high level, Egyptian Arabic vs Modern Standard Arabic, why numbers are hard in speech, language detection vs setting the language, model sizes (accuracy vs speed vs memory), int8 quantization, real-time factor, CPU vs GPU, word error rate (WER), and API rate limits.

If the results are weak, explain the brief's fallback (asking the user to confirm the transcript) and let me decide. Add my decisions (model size, and the fallback if needed) to section 13.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.7 — Explore the NYC 311 data
**You'll need:** nothing. An NYC Open Data app token is optional, only if downloads get slowed down.

```text
Step 1.7 — Explore the NYC 311 data
Phase 1 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: understand the NYC 311 data before we use it.

Build:
1. Find the official NYC 311 Service Requests dataset on NYC Open Data. Show me the dataset page, the column descriptions, and the terms of use.
2. The full dataset is very large, so don't download all of it. Write ml/download_311.py: it uses the Open Data API with filters to download a sample of housing complaints from the last 12 months, with a row limit. For example, filter to complaints handled by HPD, the city's housing agency (check this in the data). Put the filters at the top of the script so anyone can repeat the download. Save to ml/data/raw/.
3. Explore the data in a notebook, ml/notebooks/01_explore_311.ipynb (ask me before adding Jupyter). Show me the results in the chat as small tables.

Answer these questions:
- What does each important column mean?
- Which complaint types and descriptors exist, and how many of each?
- Is there any free text written by the resident? If not, what does that mean for training a text classifier, and how does the brief's plan (synthetic requests modeled on 311) solve it?
- How much data is missing, and what date range do we have?
- Are the classes balanced?

Teach me: exploratory data analysis (EDA), sampling, API vs bulk download, class imbalance, and why raw data never goes in git.

Save the source URL, terms of use, download date and filters in this step's Progress log entry. Step 1.10 uses them for the data card.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.8 — Category and urgency mapping + labeling guide
**You'll need:** time to decide. Good to discuss with your instructor before you confirm.

```text
Step 1.8 — Category and urgency mapping + labeling guide
Phase 1 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: decide how NYC complaints map to our 6 categories and our urgency levels, and write the rules down.

This step is mostly decisions, and the decisions are mine. Show me options with pros and cons, then wait for my choice.
1. Using what we found in Step 1.7, propose a mapping table from 311 complaint type (and descriptor, where needed) to plumbing, electricity, ac, carpentry, pest_control and general. Point out the hard cases and the out-of-scope rows we should drop. Examples of hard cases:
   - heating has no category of its own
   - AC is common in Egypt but may be rare in NYC housing data
   - doors, windows and floors could be carpentry
2. Propose urgency rules for low, medium and high: a clear definition, and 3 examples each in English and Egyptian Arabic. Discuss safety cases (gas smell, sparks, flooding, no water at all).
3. Explain how we will get urgency labels, since 311 may not have them directly. Give me the options.

After I decide, build:
4. ml/label_mapping.py: the mapping in one place.
5. ml/prepare_311.py: applies the mapping, drops out-of-scope rows, saves ml/data/processed/311_mapped.csv, and prints the count per category.
6. docs/labeling_guide.md: definitions, rules, edge cases, examples, and what to do when one message has two problems.

Teach me: label taxonomy, why labeling rules must be written down (consistency between labelers), rule-based (weak) labels, and how class imbalance affects F1.

Once I decide, move "Exact urgency rules" from section 14 to section 13.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.9 — Mock unit registry
**You'll need:** nothing.

```text
Step 1.9 — Mock unit registry
Phase 1 · Backend & Memory

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: a fake list of compounds, buildings and units, so the bot can check unit details later and recognize returning users.

Build:
1. Propose where the registry and its script should live, and update CLAUDE.md section 5.
2. A script that generates the registry with a fixed random seed (same output on every run):
   - 3–4 compounds with clearly fictional names, in English and Arabic (residents may write either)
   - several buildings per compound, and units like B-204
   - CSV output with the columns compound_en, compound_ar, building, unit_number
3. Checks: the row count, and no duplicate (compound, building, unit_number).

Teach me: synthetic data, random seeds and reproducibility, unique keys, and how this registry will be used in Phase 3 (checking extracted units, and "Is this for Unit B-204?").

Don't use real Emaar compound names or any internal data.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.10 — Data card
**You'll need:** nothing.

```text
Step 1.10 — Data card
Phase 1 · Data & ML

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: document every data source honestly, as the brief requires.

Build docs/data_card.md with one section per source:
- the NYC 311 sample (Step 1.7): URL, terms of use, download date, filters, size, columns used
- the mock unit registry (Step 1.9)
- my voice notes (Step 1.6): who recorded them, fake details only, not stored in git
- planned for Phase 2: LLM-generated synthetic requests, the translated subset, and the hand-written test set

For each source, include: license or terms, how it was made, intended use, and known limits (e.g. NYC is not Egypt, English only, no resident free text).
Add a rules section: no internal Emaar data and no real resident data.

Teach me: what a data card is, why licenses matter, and how documenting bias helps the final report.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.11 — Design notes: fields, DB sketch, dashboard charts
**You'll need:** a decision on the ticket number format.

```text
Step 1.11 — Design notes: required fields, database sketch, dashboard plan
Phase 1 · LLM & Speech, Backend & Memory, Dashboard & DevOps

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: plan Phase 2 on paper. No code in this step.

Build docs/design_notes.md with three parts:
1. Required fields: for each field (compound, building, unit_number, name, phone, issue_description), give:
   - its type
   - examples in Arabic and English
   - a validation rule (e.g. Egyptian mobile numbers are 11 digits starting with 010, 011, 012 or 015)
   - the follow-up question the bot asks if it is missing
2. Database sketch: an ER diagram in Mermaid based on CLAUDE.md section 7. Explain each table, the keys, and the relationships (one-to-many, many-to-many), and why user_units is a separate table.
3. Dashboard plan: for each chart the brief asks for, list the table and columns it needs and the SQL idea behind it. Point out what we must store to make each chart possible (e.g. closed_at for average handling time).

Also help me decide the ticket number format (an open decision in section 14).

Teach me: data modeling, primary and foreign keys, normalization, and why we design the database before writing code.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Build one file at a time and explain each one. Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md (tick section 12, add a section 15 entry with an honest status, log decisions in section 13, update sections 5 and 6 if needed), show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Step 1.12 — Phase 1 review and scope freeze
**You'll need:** about an hour, and the bot running.

```text
Step 1.12 — Phase 1 review and scope freeze
Phase 1 · All roles

Before anything else: re-read CLAUDE.md, docs/project_brief.pdf, and the Progress log (CLAUDE.md section 15). Tell me in 2–3 simple sentences where we are.

Goal: check that Phase 1 really works, then freeze the scope.

1. Go through every Phase 1 box in section 12. Run each check again yourself (tests, ruff, Docker, scripts) and show me a table: task, status (✅ / ⚠️ / ❌), evidence.
2. Bot test: tell me what to send the bot, and I will report back.
3. List what must be fixed before Phase 2, and fix it with me one item at a time.
4. Add a "Stretch list" to CLAUDE.md for ideas that are not in the brief.
5. Write docs/phase1_summary.md for my instructor (one page): what we built, the decisions and why, the Whisper test results, the risks we found, and open questions.
6. Clean up CLAUDE.md: move the Phase 1 entries from section 15 to docs/progress_log.md, leave a 3-line Phase 1 summary, and move ◀ to Phase 2.
7. Ask me before committing and before adding the git tag phase-1-done.

Teach me: what a scope freeze is and why projects need one, and what technical debt means.

How to work: follow CLAUDE.md section 2 exactly. Explain the theory first in simple English, show your plan, and wait for my "go". Never ask me to paste keys or tokens in the chat.
When the step is done: update CLAUDE.md as described above, show me the changes, and end with the full summary: Done, How it works, Status, Concepts to review, Questions for my instructor, 👉 Your turn, Next.
```

---

## Helper prompts (use any time)

**Resume a step** (new session, same step):
```text
Continue Step 1.x. First read CLAUDE.md and this step's Progress log entry, and tell me in simple words what is done and what is left. Then continue, following CLAUDE.md section 2.
```

**Explain again:**
```text
I didn't understand <topic>. Explain it again more simply: one analogy, one tiny example from our project, and one common mistake. Don't change any files.
```

**Quiz me before meeting my instructor:**
```text
Quiz me on Step 1.x: 5 questions, from easy to hard. Wait for my answers, then correct me. Don't change any files.
```

**Review code I wrote myself:**
```text
I wrote <file> myself. Review it like a senior engineer: what is good, what is wrong, and why. Give hints; don't rewrite it.
```
