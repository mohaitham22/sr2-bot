# CLAUDE.md — AI-Powered Service Request Bot (Emaar Misr intern project)

## 1. What this project is
A Telegram bot where residents report maintenance problems by **text or voice note** (Arabic or English).
The bot turns each report into a stored, categorized **service request (SR)** shown on a dashboard.

Flow: voice → text (STT) → LLM extracts fields → bot asks for missing fields → user confirms →
ML classifier assigns category + urgency → SR saved with a ticket number → user gets confirmation → SR appears on dashboard.

- Length: 10 weeks. Key checkpoint: **week 6**, when one request must flow from Telegram to the dashboard.
- Scope source of truth: `docs/project_brief.pdf`. If this file and the brief disagree, the brief wins. Tell me about the conflict.
- Out of scope: real Emaar systems (CRM, work orders), technician assignment, scheduling, and auth against real resident records.

---

## 2. How to work with me (learning mode). Follow this in every session.
I am building this to **learn**, not to finish fast. I must understand every file and every step, and I discuss each step with my instructor.
Start every answer with 2–3 sentences in very simple English saying what we are doing and why. Use clear English (I'm improving from B1 to B2) and avoid unnecessary jargon.

**Before you start a step**
1. Re-read this file, the brief (`docs/project_brief.pdf`), and the Progress log (section 15), so you know the whole project and what is already done.
2. Name the phase and role of the task (see section 12), e.g. "Phase 1 · Data & ML".
3. Explain in simple English what this step is, why the project needs it, and the theory behind it. Use a small example or analogy.
4. Show your plan: which files you will create or change, in what order, and what each one does. Then wait for my "go".

**While you build**
5. One file (or one function) at a time. After each file, explain what it does and the important lines, then wait for me before the next file. Tiny files (e.g. empty `__init__.py`) can go together.
6. Name each new concept in one line (e.g. "TTL", "data leakage") so I can study it.
7. When I say **"let me try"**, give hints, not the full solution.
8. Errors: explain the cause first, then the fix. Don't silently switch to a different approach.
9. No new dependency, service, or paid tool without asking me first and explaining why. Free tools only.
10. Don't refactor or "improve" code I didn't ask about. Suggest it instead.
11. Ask before `git commit`/`push`, deleting files, dropping DB tables, or `docker system prune`.
12. If you need something from me (an account, a key, an install, a recording, a decision), stop and write a **👉 Your turn** section with exact numbered steps. **Never ask me to paste API keys or tokens in the chat**; tell me which line of `.env` to fill.
13. Decisions that shape the project (labels, urgency rules, mappings, formats, tools) are mine. Show me the options with pros and cons, and let me choose.

**After you build**
14. Show me how to run or test it and what output I should see. Run the check yourself when you can, and report the real result.
15. Be honest about status. Mark ✅ only if you ran the check and it passed. Use ⚠️ for "works with issues", ❌ for "broken", and ⏸️ if we stopped in the middle. Always say why.
16. Update this file: tick the boxes in section 12, add an entry to section 15, add decisions to section 13, and update sections 5 and 6 if the layout or commands changed. Then show me what you changed.
17. End every step with this summary:
    - **Done:** what we built (files).
    - **How it works:** 2–4 simple sentences.
    - **Status:** ✅ / ⚠️ / ❌ / ⏸️ and why.
    - **Concepts to review:** the key ideas.
    - **Questions for my instructor:** 2–3 questions to discuss.
    - **👉 Your turn:** what I must do now (or "nothing").
    - **Next:** the next step.

---

## 3. Tech stack (free-tier version of the brief)
| Layer | Tool | Notes |
|---|---|---|
| Language | Python 3.12 | Type hints everywhere |
| Packages | uv (`pyproject.toml` + `uv.lock`) | |
| Bot | aiogram 3 | Polling locally, webhook when deployed |
| API | FastAPI + Uvicorn | Receives the Telegram webhook |
| Conversation flow | LangGraph | Open-source library only; no paid LangSmith |
| LLM | Groq free tier (default), Gemini Flash free tier (backup) | All calls go through `app/services/llm.py`; provider and model are set by env vars |
| Speech-to-text | Self-hosted Whisper with `faster-whisper`, on CPU first | Reads Telegram `.ogg` directly (no ffmpeg install). Model size chosen from Step 1.6 measurements. Groq Whisper API only as a comparison in Step 1.6, never in the app |
| Validation | Pydantic v2 | Every LLM output is validated against a schema |
| Classifier | scikit-learn TF-IDF + LogisticRegression (v1) → SetFit or multilingual BERT (v2) | Train v2 on Colab/Kaggle free GPU |
| Experiments | MLflow (local) | Log every training run |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic | Persistent data |
| Session memory | Redis 7 (`redis.asyncio`) | Short-term state |
| Dashboard | Metabase open-source | Reads Postgres directly |
| LLM tracing | Langfuse Cloud (Hobby, free) | No personal data in traces |
| Containers | Docker Engine / Rancher Desktop | Not Docker Desktop on the work laptop (license) |
| CI/CD | GitHub Actions | |
| Hosting | Oracle Cloud Always Free VM running docker compose | Alternative: Azure Container Apps free grant |
| Quality | ruff (lint + format), pytest | |

---

## 4. Architecture
```
Resident ⇄ Telegram ⇄ aiogram ⇄ FastAPI ⇄ LangGraph flow
                                              │
      ┌──────────────┬───────────────┬────────┴──────┬──────────────┐
  Whisper        LLM client     Classifier      Redis (session)  PostgreSQL
  (STT, local)   (extract)      (cat+urgency)   (state, turns)   (users, units, SRs)
                                                                     │
                                                                Metabase (reads)
```

**LangGraph nodes** (in order):
1. `transcribe`: only for voice notes.
2. `extract`
3. `ask_missing`: loops back to `extract` until all required fields are filled.
4. `confirm`: show a summary and wait for yes/edit.
5. `classify`
6. `save`
7. `reply`: send the ticket number.

**Bot commands:**
- `/start`
- `/status <ticket>`
- `/reset`: clear the session.
- `/forget`: delete the saved profile.

**Required fields:** compound, building, unit_number, name, phone, issue_description.

---

## 5. Repository layout (planned; update when it changes)
```
app/
  main.py            # FastAPI app + webhook endpoint
  config.py          # pydantic-settings, reads .env
  bot/               # aiogram handlers and commands
  graph/             # LangGraph state, nodes, edges
  services/          # stt.py, llm.py, extraction.py, classifier.py
  prompts/           # prompt files (*.md), versioned; never inline long prompts
  memory/            # Redis session store
  db/                # SQLAlchemy models, session, repositories
  schemas/           # Pydantic models
ml/                  # data prep, train_baseline.py, train_setfit.py
  data/raw/ data/processed/   # git-ignored
eval/                # test_set.csv, run_eval.py, ml_vs_llm.py
migrations/          # Alembic
docs/                # project_brief, data_card.md, labeling_guide.md, model_report.md
  prompts/           # step-by-step prompts for each phase (phase1.md, ...)
tests/
.github/workflows/ci.yml
pyproject.toml  uv.lock  .python-version  .gitignore  .env.example   # exist since Step 1.1
docker-compose.yml   # exists since Step 1.2: postgres + redis (app and metabase come later)
Dockerfile
```
Exists since Step 1.1: `app/config.py`, `tests/test_config.py`, and empty `__init__.py` in `app/` (+ `bot/ graph/ services/ memory/ db/ schemas/`), `ml/`, `eval/`, `tests/`.
Exists since Step 1.2: `docker-compose.yml`. Docker named volumes `sr-bot2_pgdata` and `sr-bot2_redisdata` hold the data (outside the repo).

---

## 6. Commands (planned; mark them as real once they work)
```bash
uv sync                                   # install dependencies          ✅ works (Step 1.1)
docker compose up -d --wait postgres redis   # start databases, wait until healthy   ✅ works (Step 1.2)
docker compose ps                         # status: both must say (healthy)       ✅ works (Step 1.2)
docker compose config --quiet             # check the file + .env (never without --quiet: it prints the password)   ✅ works (Step 1.2)
docker compose exec postgres psql -U srbot -d srbot   # SQL shell (\q to quit)  ✅ works (Step 1.2)
docker compose exec redis redis-cli ping  # expect PONG                         ✅ works (Step 1.2)
docker compose down                       # stop + delete containers; volumes (data) are KEPT   ✅ works (Step 1.2)
# docker compose down -v                  # ALSO deletes the volumes = all data. Ask Momo first.
uv run alembic upgrade head               # apply DB migrations
uv run python -m app.bot.polling          # run the bot locally (no public URL needed)
uv run uvicorn app.main:app --reload      # API for webhook mode
uv run pytest                             # tests                         ✅ works (Step 1.1)
uv run ruff check . && uv run ruff format .   # lint + format          ✅ works (Step 1.1)
uv run mlflow ui                          # http://localhost:5000
uv run python -m ml.train_baseline
uv run python -m eval.run_eval
docker compose up -d metabase             # http://localhost:3000
```
Note: Momo's terminal is Windows PowerShell 5.1, where `&&` does not work. Run the two ruff commands one after the other.
Note: PowerShell 5.1 removes double quotes *inside* arguments passed to programs like `docker` (e.g. `sh -c '... "x" ...'`). Keep commands simple (as above), or use Git Bash for nested quotes.
Note: Rancher Desktop must be running before any `docker` command.

---

## 7. Data model (first version)
| Table | Columns |
|---|---|
| `users` | id, telegram_user_id (unique), name, phone, created_at |
| `units` | id, compound, building, unit_number; unique(compound, building, unit_number) |
| `user_units` | user_id, unit_id, confirmed_at |
| `service_requests` | id, ticket_no (unique), user_id, unit_id, description, language, category, urgency, status (open / in_progress / closed), created_at, closed_at |
| `messages` | id, sr_id (nullable), telegram_chat_id, role, text, created_at |
| `predictions` | id, sr_id, model_name, model_version, category, urgency, confidence, needs_review, created_at |

**Labels:**
- Categories: `plumbing`, `electricity`, `ac`, `carpentry`, `pest_control`, `general`.
- Urgency: `low`, `medium`, `high`. Rules are defined in `docs/labeling_guide.md`.

---

## 8. Memory design (from the brief; must follow)
| Layer | Holds | Storage | Lifetime |
|---|---|---|---|
| Session state | Current SR: collected fields, missing fields, step | Redis, key `session:{chat_id}` | Cleared on submit or after 30 min idle |
| Conversation history | Last N turns of the active session; older turns summarized | Redis, `history:{chat_id}` | Same as session |
| User profile | Name, phone, units, past SR IDs | PostgreSQL | Persistent |

- Recognize returning users by Telegram user ID, and offer their saved unit ("Is this for Unit B-204?").
- Keep each LLM call within a fixed token budget: trim or summarize history.

---

## 9. Hard rules (privacy, data, safety). Never break these.
- **No internal Emaar data.** Only public and synthetic data. Record every source and its license in `docs/data_card.md`.
- **Never send real resident data to free LLM tiers.** Free tiers may use prompts for training.
- **Name and phone are stored permanently only in Postgres.** They may pass briefly through the current user's LLM prompt and Redis session (cleared on submit, `/reset`, or 30 min idle). Never put them in logs, Langfuse traces, MLflow, error messages, or git. Mask them first.
- **Message text, transcripts and voice notes count as personal data too**, because they can contain a name or phone.
- **The LLM prompt contains only the current user's** profile and session. Never include other users' data.
- **Never save LLM-extracted unit info** to the profile until the user confirms it.
- **Secrets go in `.env`** (git-ignored). Keep `.env.example` up to date. Never print keys.
- **The test set (`eval/test_set.csv`) is never used** for training or as prompt examples.

---

## 10. Coding conventions
- Use type hints. Use Pydantic models for any data that crosses a boundary (LLM ↔ app ↔ DB).
- Use async for all I/O (bot, API, Redis, Postgres).
- Read config from env via `app/config.py`. Never hard-code keys, model names, or URLs.
- Services (`app/services`) must not import bot code. Keep one responsibility per module.
- For every LLM/STT call:
  - set a timeout
  - retry with backoff on HTTP 429 (free-tier rate limits)
  - validate with Pydantic
  - on invalid JSON, re-ask once, then fall back to asking the user
- The classifier always returns a confidence. Set `needs_review` when confidence is below the threshold (threshold is set in Phase 4).
- Tests: mock the LLM and STT in unit tests, so CI never spends free quota.
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Keep PRs small.

---

## 11. Success criteria (from the brief)
| Metric | Target |
|---|---|
| Category classification F1 (held-out test set) | ≥ 0.85 |
| Extraction captures all required unit fields | ≥ 90% of test conversations |
| Arabic voice-note transcription usable for extraction | ≥ 85% of test recordings |
| Bot reply time p95 (excluding transcription) | < 5 s |
| Written ML classifier vs LLM zero-shot comparison | accuracy, latency, cost per request |
| Live deployment + 10-minute stakeholder demo | done |

---

## 12. Phases by role (current phase marked ◀)

### The four roles (from the brief)
I do all four roles myself.

| Role | Owns |
|---|---|
| **Data & ML** | Dataset, data card, classifier training, MLflow, ML vs LLM comparison |
| **LLM & Speech** | Whisper, extraction prompts and schema, follow-up questions |
| **Backend & Memory** | FastAPI, LangGraph flow, Redis session memory, PostgreSQL schema |
| **Dashboard & DevOps** | Dashboard, Docker, CI/CD, deployment, Langfuse |

**Usual order inside a phase:** Data & ML → LLM & Speech → Backend & Memory → Dashboard & DevOps.
Data and LLM work feeds the backend, and the backend feeds the dashboard and deployment.
**Key handoff:** the classifier must be ready by the end of Phase 2, or Phase 3 integration gets stuck.

**If behind schedule:** reach the week-6 gate with a basic version of every part first. Cut from Phase 4 (e.g. skip BERT, keep SetFit).

---

### Phase 1: Foundations (weeks 1–2) ◀ → Gate: scope freeze
**Phase 1 order (exception to the usual order):** setup → bot → Whisper test → data → design → review.
Step-by-step prompts: `docs/prompts/phase1.md` (Steps 1.0–1.12).

**Data & ML**
- [ ] Download the NYC 311 data and keep only housing complaints
- [ ] Map complaint types to the 6 categories and an urgency level
- [ ] Write `docs/labeling_guide.md`
- [ ] Start `docs/data_card.md`

**LLM & Speech**
- [ ] Get Groq and Gemini API keys
- [ ] Record a few Arabic and English voice notes
- [ ] Test Whisper on Egyptian Arabic early (top risk in the brief)
- [ ] List the required fields

**Backend & Memory**
- [ ] Create the bot with @BotFather
- [x] Set up the repo structure and `.env` config
- [ ] Build a polling bot that receives text and voice
- [ ] Generate the mock unit registry
- [ ] Sketch the DB tables on paper

**Dashboard & DevOps**
- [x] Set up the GitHub repo and install Rancher Desktop
- [x] Write a docker compose file with Postgres and Redis
- [ ] Create a first GitHub Actions workflow (ruff + pytest)
- [ ] List the dashboard charts the brief asks for

**End of phase:** the bot replies, the data is mapped, and the scope is frozen. New ideas go on a stretch list.

---

### Phase 2: Core AI (weeks 3–4)
**Data & ML**
- [ ] Build the TF-IDF + logistic regression baseline for category and urgency; log it in MLflow
- [ ] Generate synthetic Egyptian Arabic requests and a translated subset
- [ ] Hand-write 200–300 test requests in `eval/test_set.csv` (never used for training)

**LLM & Speech**
- [ ] Write `app/services/stt.py` using self-hosted Whisper (`faster-whisper`)
- [ ] Create the Pydantic extraction schema and the extraction prompt
- [ ] Add follow-up questions for missing fields
- [ ] Validate the output; re-ask once if the JSON is broken

**Backend & Memory**
- [ ] Build the SQLAlchemy models and Alembic migrations
- [ ] Build the Redis session store (`session:{chat_id}`, 30-minute expiry)
- [ ] Define the LangGraph state

**Dashboard & DevOps**
- [ ] Write a Dockerfile for the app
- [ ] Make CI run on every PR
- [ ] Run Metabase locally and connect it to Postgres with fake rows

**End of phase:** each piece works on its own. Text goes in, valid JSON comes out, and there is a baseline F1 number.

---

### Phase 3: Integration (weeks 5–6) → Gate: end-to-end demo ⭐
**Data & ML**
- [ ] Wrap the model in `app/services/classifier.py`; it returns category, urgency, and confidence
- [ ] Save the model file with a version number

**LLM & Speech**
- [ ] Turn STT and extraction into LangGraph nodes
- [ ] Build the confirmation summary
- [ ] Handle edits like "no, it's building 5", and reply in the user's language

**Backend & Memory**
- [ ] Wire FastAPI and the full LangGraph flow together
- [ ] Recognize returning users ("Is this for Unit B-204?")
- [ ] Keep the last N turns and summarize older ones
- [ ] Add ticket numbers and the `/status`, `/reset`, and `/forget` commands
- [ ] Save each SR and its predictions

**Dashboard & DevOps**
- [ ] Run the whole stack in docker compose
- [ ] Add Langfuse tracing
- [ ] Show the first dashboard on real SRs
- [ ] Check that no name or phone appears in logs

**End of phase:** one request flows from Telegram to the dashboard. This is the most important checkpoint.

---

### Phase 4: Insights (weeks 7–8)
**Data & ML**
- [ ] Train classifier v2 (SetFit or BERT) on Colab and compare it with the baseline in MLflow
- [ ] Choose the low-confidence threshold
- [ ] Run the ML vs LLM zero-shot comparison (accuracy, latency, cost)

**LLM & Speech**
- [ ] Measure extraction completeness (target ≥ 90%) and transcription quality (target ≥ 85%)
- [ ] Improve the prompts
- [ ] Add the "please confirm this transcript" fallback for weak audio

**Backend & Memory**
- [ ] Measure p95 reply time (target < 5 s) and speed up slow parts
- [ ] Set the token budget per LLM call
- [ ] Add SR status changes (open → in_progress → closed) for the handling-time chart

**Dashboard & DevOps**
- [ ] Build the full dashboard: volume over time, category and urgency split, top units and buildings, open vs closed, average handling time
- [ ] Make the eval suite run with one command

**End of phase:** every success criterion in section 11 has a measured number.

---

### Phase 5: Deploy (week 9)
**Data & ML**
- [ ] Package the final model with its version
- [ ] Draft `docs/model_report.md`

**LLM & Speech**
- [ ] Fix prompt versions; set timeouts and rate-limit retries
- [ ] Confirm no personal data appears in traces

**Backend & Memory**
- [ ] Switch to webhook mode and add a health-check endpoint
- [ ] Run migrations on deploy; make sure data survives restarts

**Dashboard & DevOps**
- [ ] Deploy to the Oracle VM (or the Container Apps free grant)
- [ ] Set up HTTPS for the webhook (Telegram requires it)
- [ ] Store secrets on the server and add the CD step in GitHub Actions
- [ ] Put Metabase online

**End of phase:** the bot and dashboard are live.

---

### Phase 6: Demo (week 10) → Gate: stakeholder demo
**Data & ML**
- [ ] Finish the model report and the data card

**LLM & Speech**
- [ ] Prepare demo cases: an Arabic voice note, an English text request, and a request with missing fields

**Backend & Memory**
- [ ] Harden the bot: error handling, odd inputs, and checking that `/forget` really deletes everything
- [ ] Write the README setup steps

**Dashboard & DevOps**
- [ ] Fill the dashboard with demo data
- [ ] Make sure the deployment is stable
- [ ] Write the final report

**All roles**
- [ ] Rehearse the 10-minute demo

**End of phase:** stakeholder demo delivered.

---

## 13. Decisions log
| Date | Decision | Why |
|---|---|---|
| 2026-10-23 | Free tool stack instead of Azure / Power BI (Groq or Gemini, Groq Whisper, Metabase OSS, free VM) | No paid services for the prototype |
| 2026-10-23 | One LLM client behind env vars | Swap Groq ↔ Gemini ↔ Azure OpenAI without code changes |
| 2026-10-23 | Follow the brief's 10-week timeline (end-to-end demo at week 6) | Brief's Objectives say "demoable in 4 weeks"; timeline says week 6 |
| 2026-10-24 | Phases split by the brief's 4 roles; I do all 4 roles | Each phase becomes a clear checklist per role |
| 2026-10-24 | Postgres models, Alembic, and Redis session store moved to Phase 2 | Phase 3 can focus on wiring the full flow |
| 2026-10-24 | Phase 1 order: setup → bot → Whisper test → data → design → review | Everything needs the setup; Egyptian Arabic transcription is the brief's top risk, so test it early |
| 2026-10-24 | Progress log kept in section 15; moved to `docs/progress_log.md` at the end of each phase | Keeps this file short |
| 2026-10-24 | Section 9 privacy rule reworded (option A) | The old rule ignored that name and phone pass briefly through the LLM and Redis, and that message text can contain them |
| 2026-10-24 | Rancher Desktop with the dockerd (moby) engine, not Docker Desktop | Avoids Docker Desktop's paid-license question for company work; dockerd keeps the `docker` and `docker compose` commands |
| 2026-10-24 | GitHub repo `mohaitham22/sr2-bot` stays public (phase1.md said private) | Momo's choice: unlimited free CI minutes, portfolio. So never commit `.env`, real data or internal documents |
| 2026-10-24 | Settings are optional for now (`None` when missing). Each entry point checks the settings it needs at startup and stops with a clear message naming the missing `.env` variable (fail fast). In Phase 5 the important settings become required | CI has no `.env`, and keys arrive step by step (bot token in 1.4, Groq key in 1.6) |
| 2026-10-24 | Ruff: add rule groups `I` (import order), `UP` (modern Python 3.12 syntax), `B` (common bug patterns); line length 100 | Cheap to adopt now, while there is little code |
| 2026-10-24 | `docs/project_brief.pdf` is git-ignored | Internal Emaar document; the repo is public and may be shared. Removing a file from git history later is hard |
| 2026-10-24 | `DATABASE_URL` and `REDIS_URL` are `SecretStr`, like the API keys | The URLs contain passwords; they must never print by accident |
| 2026-10-24 | Commit author email stays Momo's Gmail (option A, not the GitHub noreply address) | Momo's choice; it is visible in every commit of the public repo |
| 2026-10-25 | Speech-to-text is self-hosted open-source Whisper, as the brief says. Replaces "Groq Whisper" from 2026-10-23; Groq stays for the LLM only | Brief: "Whisper (open-source, self-hosted)". Voice notes are personal data; self-hosted audio never leaves our machine |
| 2026-10-25 | Whisper engine is `faster-whisper`, run on CPU first (GPU only if CPU is too slow). The Groq Whisper API is kept as a comparison in Step 1.6 only, never in the app | faster-whisper is faster, uses less memory, supports int8 and reads `.ogg` itself. The free server has no GPU, so CPU numbers are realistic. The Groq comparison gives a cloud vs self-hosted number for the report (fake voice notes only) |
| 2026-10-25 | Keep Momo's full NYC 311 export (2020 to present, downloaded 2026-10-22, 15.0 GB) in `ml/data/raw/`. Step 1.7 decides: filter this file, or use a small API sample | Already downloaded; git-ignored there; GitHub rejects files over 100 MB |
| 2026-10-25 | Images `postgres:16` and `redis:7` (standard Debian-based, not `-alpine`) (D1 B) | Most documented images, full locale support for Arabic text; size doesn't matter (downloaded once) |
| 2026-10-25 | `DATABASE_URL` in `.env` is built from `POSTGRES_USER/PASSWORD/DB` with `${...}` (D2 B). Password: letters and digits only | Each value written once. Tested: Docker Compose and python-dotenv (pydantic-settings) both fill in `${...}` |
| 2026-10-25 | Redis has no password for local development (D3 A). Postgres and Redis ports are bound to `127.0.0.1` only; URLs use `127.0.0.1`, not `localhost`. Revisit the Redis password in Phase 5 | Only this laptop can reach Redis (checked: closed on the network IP). On the server Redis will publish no port. `localhost` may try IPv6 first on Windows |
| 2026-10-25 | Redis keeps its default snapshot saving (RDB) on the `redisdata` volume, not AOF. Compose passes only the needed variables (`environment:`), never `env_file: .env` | Enough for 30-minute sessions. Least privilege: API keys never enter the database containers |

## 14. Open decisions (decide, then move to the log)
- Ticket number format (default idea: `SR-YYYYMMDD-XXXX`).
- Exact urgency rules (`low`/`medium`/`high`), to be defined in the labeling guide.
- Classifier v2: SetFit or multilingual BERT.
- Final hosting: Oracle VM or Azure Container Apps free grant.
- Value of N for conversation history, and the token budget per LLM call.
- Whisper model size (`small` / `medium` / `large-v3` / `large-v3-turbo`): decide from Step 1.6 measurements on CPU. Laptop: i7-11800H 8 cores, 16 GB RAM, RTX 3050 4 GB.

---

## 15. Progress log
Add one entry per step (or update it if the step continues in a new session). Keep each entry to 8 lines or fewer.
At the end of each phase, move that phase's entries to `docs/progress_log.md` and leave a 3-line phase summary here.

Format:
```
### Step <phase>.<n> — <title> (YYYY-MM-DD)
- Phase · role:
- Files:
- How it works: (2–3 simple sentences)
- Status: ✅ works / ⚠️ works with issues / ❌ broken / ⏸️ in progress — and why
- Known issues / TODO:
- What Momo did:
```

### Step 1.0 — Understand the project before we build (2026-10-24)
- Phase · role: Phase 1 · All roles
- Files: `CLAUDE.md` (this entry only). No code. Momo added `docs/prompts/phase1.md`.
- How it works: Claude read CLAUDE.md, the brief and phase1.md, explained the project, the 6 phases and Phase 1, and checked the laptop's tools (read-only, nothing installed). Momo answered a 5-question quiz.
- Status: ✅ done. Quiz 5/5 correct. Tools: git 2.54.0 ✅ (name/email set), Python 3.12 ✅, uv 0.12.19 ✅, Brief ✅. Docker CLI 29.9.2 + Compose v5.6.0 ⚠️: they come from Docker Desktop, which will be replaced by Rancher Desktop (not installed yet).
- Known issues / TODO: Install Rancher Desktop (dockerd engine), remove Docker Desktop, test the engine (needed by Step 1.2). The repo is public, so ask the instructor before committing `docs/project_brief.pdf`.
- What Momo did: Answered the quiz (5/5); found the section 9 gap and chose the new wording (A); chose Rancher Desktop; created the public repo `mohaitham22/sr2-bot`; added phase1.md.

### Step 1.1 — Project skeleton and settings (2026-10-24)
- Phase · role: Phase 1 · Backend & Memory
- Files: `.gitignore`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `app/config.py`, `tests/test_config.py`, empty `__init__.py` packages (section 5). Local `.env` (git-ignored).
- How it works: `app/config.py` reads settings from env vars and `.env`. All are optional; the 3 API keys and 2 DB URLs are `SecretStr`; `Settings.require()` lets each entry point fail fast, naming the missing variables. The 4 tests use fake values only and ignore the real `.env`.
- Status: ✅ done. pytest 4 passed, ruff check + format clean, `uv sync` OK, `.env` ignored by git. Commits `5793af7` + `edaafe5` pushed to `mohaitham22/sr2-bot` (`main` tracks `origin/main`).
- Known issues / TODO: Momo's 15.0 GB NYC 311 export (`311_Service_Requests_from_2020_to_Present_20261022.csv`) moved from the root to `ml/data/raw/` (git-ignored ✅); Step 1.7 decides how to use it. Harmless warnings: git LF→CRLF, uv hardlink. Rancher Desktop not installed yet (Step 1.2).
- What Momo did: chose D1 (optional + fail fast), D2 (ruff I/UP/B), D3 (ignore the brief), D4 (DB URLs are secrets), kept Gmail as commit email; created `.env` from the template and set `STT_MODEL`.

### Step 1.2 — Postgres and Redis in Docker (2026-10-25)
- Phase · role: Phase 1 · Dashboard & DevOps
- Files: `docker-compose.yml` (new), `.env.example` (`POSTGRES_*` block, real `DATABASE_URL`/`REDIS_URL` formats). Local `.env` filled by Momo.
- How it works: Compose runs `postgres:16` and `redis:7` in Rancher Desktop (dockerd). Data lives in named volumes; healthchecks use `pg_isready` and `redis-cli ping`; ports are bound to 127.0.0.1 only. Postgres values come from `.env` as required variables (`${VAR:?…}`), and `DATABASE_URL` is built from them.
- Status: ✅ all checks run and passed: `config --quiet` OK; both `(healthy)`; PostgreSQL 16.15 + password login over TCP; Redis 7.4.11 `PONG`; ports open on 127.0.0.1, closed on the network IP; `Settings` loads both URLs; a test table + Redis key survived `restart` and `down`/`up` (new container IDs), then were dropped with Momo's OK. Both databases are empty.
- Known issues / TODO: if `POSTGRES_*` are empty, `DATABASE_URL` is not empty, so `require()` does not catch it (Compose does). PowerShell 5.1 drops nested quotes (section 6 note). Harmless leftover docker context `desktop-linux`. Step 1.0 TODO closed: Rancher Desktop installed, Docker Desktop removed, engine tested.
- What Momo did: started Rancher Desktop; chose D1 B, D2 B, D3 A and default RDB; filled `.env`; typed the password into `.env.example` by mistake, then cleared it and made a new password before the first start (nothing was committed).
