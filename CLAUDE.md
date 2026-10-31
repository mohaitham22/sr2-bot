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
| Speech-to-text | Self-hosted Whisper with `faster-whisper`, on CPU first | Reads Telegram `.ogg` directly (no ffmpeg install). Model `large-v3`, int8, CPU (Step 1.6 D10 A; `medium` is the backup). Groq Whisper API only as a comparison in Step 1.6, never in the app |
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
1. `transcribe`: only for voice notes. The bot shows the transcript and the user confirms or corrects it (Step 1.6 D11 A).
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

**Required fields:** compound, building, unit_number, name, phone, issue_description. Rules and follow-up questions: `docs/design_notes.md` §1.

---

## 5. Repository layout (planned; update when it changes)
```
app/
  main.py            # FastAPI app + webhook endpoint
  config.py          # pydantic-settings, reads .env
  logging_setup.py   # log format for all entry points; hides secrets (token) in every line
  bot/               # aiogram handlers, middlewares, polling entry point
  graph/             # LangGraph state, nodes, edges
  services/          # stt.py, llm.py, extraction.py, classifier.py
  prompts/           # prompt files (*.md), versioned; never inline long prompts
  memory/            # Redis session store
  db/                # models.py (7 tables), session.py (URL + engine), repositories.py (Step 2.2)
    seed/            # mock unit registry: generate_units.py + units.csv (committed; Step 1.9),
                     #   load_units.py (CSV -> Postgres; Step 2.2)
  schemas/           # Pydantic models; labels.py = the allowed labels, one place (Step 2.2)
ml/                  # data prep (sample_311.py, label_mapping.py, prepare_311.py), train_baseline.py, train_setfit.py
  data/raw/ data/processed/   # git-ignored; raw/ holds Momo's 311 export + the Step 1.7 sample; processed/ holds 311_mapped.csv (Step 1.8)
  notebooks/         # EDA notebooks, saved with outputs (01_explore_311.ipynb)
eval/                # check_test_set.py, run_eval.py, ml_vs_llm.py, whisper_test.py, score_whisper.py
                     #   test_set*.csv / .md: git-ignored (Step 2.1 D6 A)
  voice/             # git-ignored, the whole folder: raw/ (test voice notes saved by the bot),
                     #   reference.csv, results.csv, scores.csv, judgments.csv, review.md (Step 1.6)
  reports/           # whisper_phase1.md (Step 1.6)
models/              # downloaded Whisper models, about 6.7 GB (git-ignored; STT_MODEL_DIR)
migrations/          # Alembic: env.py, script.py.mako, README, versions/ (Step 2.2)
docs/                # project_brief, data_card.md, labeling_guide.md, design_notes.md, model_report.md,
                     #   phase1_summary.md, progress_log.md
  prompts/           # step-by-step prompts for each phase (phase1.md, phase2.md, ...),
                     #   test_set_extra_rows.md (Step 2.1: the prompt for the 30 gas + appliances rows)
tests/
.github/workflows/ci.yml   # exists since Step 1.3: ruff check, ruff format --check, pytest
pyproject.toml  uv.lock  .python-version  .gitignore  .env.example   # exist since Step 1.1
alembic.ini          # Alembic settings, no database URL (Step 2.2)
docker-compose.yml   # exists since Step 1.2: postgres + redis (app and metabase come later);
                     #   Postgres logs errors terse, without DETAIL (Step 2.2)
Dockerfile
```
Exists since Step 1.1: `app/config.py`, `tests/test_config.py`, and empty `__init__.py` in `app/` (+ `bot/ graph/ services/ memory/ db/ schemas/`), `ml/`, `eval/`, `tests/`.
Exists since Step 1.2: `docker-compose.yml`. Docker named volumes `sr-bot2_pgdata` and `sr-bot2_redisdata` hold the data (outside the repo).
Exists since Step 1.3: `.github/workflows/ci.yml` (GitHub Actions CI, one job `check`).
Exists since Step 1.4: `app/bot/handlers.py` (Router: `/start` + echo), `app/bot/middlewares.py` (logs update type, chat ID, text length only), `app/bot/polling.py` (entry point), `app/logging_setup.py`, `tests/test_bot.py`, `tests/test_logging_setup.py`.
Exists since Step 1.5: `app/bot/voice_files.py` (folder + file names for test voice notes), `tests/test_voice_files.py`, `tests/test_polling.py`. `handlers.py` also has `save_voice` and the catch-all `unsupported`; `polling.py` has `build_dispatcher()`. The bot creates `eval/voice/raw/` on the first saved voice note.
Exists since Step 1.6: `eval/whisper_test.py` (transcribe the test notes: local models + Groq), `eval/score_whisper.py` (WER/CER, number checks, judgments → summary), `tests/test_whisper_test.py`, `tests/test_score_whisper.py`, `eval/reports/whisper_phase1.md`. `config.py` has `stt_model_dir`.
Exists since Step 1.7: `ml/sample_311.py` (HPD sample + full counts from the local 311 export), `tests/test_sample_311.py`, `ml/notebooks/01_explore_311.ipynb`. Git-ignored outputs: `ml/data/raw/311_hpd_sample.csv`, `ml/data/raw/311_hpd_population_counts.csv`.
Exists since Step 1.8: `ml/label_mapping.py` (the 311 → category + urgency rules, one place), `ml/prepare_311.py`, `tests/test_label_mapping.py`, `tests/test_prepare_311.py`, `docs/labeling_guide.md` (the same rules in words; change both together). Git-ignored output: `ml/data/processed/311_mapped.csv`.
Exists since Step 1.9: `app/db/seed/__init__.py`, `app/db/seed/generate_units.py` (the recipe: seed 42, 4 fictional compounds, buildings A–F), `app/db/seed/units.csv` (committed; made only by the script, never by hand; columns `compound_en, compound_ar, building, unit_number`; 188 rows), `tests/test_generate_units.py` (golden-file test: the CSV = a fresh run).
Exists since Step 1.10: `docs/data_card.md` (every data source: terms, how it was made, intended use, limits; 3 in use + 3 planned; a new source gets its section before it is used).
Exists since Step 1.11: `docs/design_notes.md` (the Phase 2 plan: §1 the 6 required fields with rules and bot questions, §2 the database sketch with the ER diagram, §3 the dashboard charts). Phase 2 code follows it; change it in the same commit when the code needs a change.
Exists since Step 1.12: `docs/phase1_summary.md` (one page for the instructor: what we built, decisions vs the brief, Whisper results, risks, questions), `docs/progress_log.md` (the step entries of finished phases, moved from section 15).
Exists since Step 2.0: `docs/prompts/phase2.md` (Momo's step prompts for Phase 2, Steps 2.0–2.13).
Exists since Step 2.1: `eval/check_test_set.py` (checks every test-set row against the guide, design notes §1 and the registry; prints coverage + SHA-256; exit code 1 on a problem), `tests/test_check_test_set.py` (a tiny fake CSV, so CI never needs the real file), `docs/prompts/test_set_extra_rows.md`. Git-ignored, on Momo's laptop only: `eval/test_set.csv` (252 rows), `eval/test_set_original.csv` (as Claude chat wrote it), `eval/test_set_extra.csv` (the 30 rows as sent), `eval/test_set_review.md` (the location before/after).
Exists since Step 2.2: `app/schemas/labels.py` (labels, one place; `ml/label_mapping.py` imports them), `app/db/models.py`, `app/db/session.py`, `app/db/repositories.py` (ticket number), `app/db/seed/load_units.py`, `alembic.ini`, `migrations/` (`env.py`, `script.py.mako`, `README`, `versions/2026_10_31_1454-db87004e7de1_create_tables.py` = migration 1), `tests/conftest.py` (the test database `srbot_test`), `tests/test_conftest.py`, `tests/test_labels.py`, `tests/test_session.py`, `tests/test_models.py`, `tests/test_repositories.py`, `tests/test_load_units.py`, `tests/test_migrations.py`. `logging_setup.py` also hides Postgres `DETAIL:` lines and asyncpg's wrong-type values. The dev database `srbot` is at migration 1 with the registry loaded (4 compounds, 188 units).

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
uv run alembic upgrade head               # apply all DB migrations (to DATABASE_URL)   ✅ works (Step 2.2)
uv run alembic downgrade -1               # undo the last migration (its tables AND their data are gone)   ✅ works (Step 2.2)
uv run alembic current                    # which migration the database is at   ✅ works (Step 2.2)
uv run alembic check                      # fail if models.py has a change that no migration has   ✅ works (Step 2.2)
uv run alembic upgrade head --sql         # print the SQL only, change nothing   ✅ works (Step 2.2)
uv run alembic revision --autogenerate -m "short title"   # write a new migration from models.py; read it before applying   ✅ works (Step 2.2)
uv run python -m app.db.seed.load_units   # Step 2.2: units.csv -> compounds + units (safe to run twice)   ✅ works (Step 2.2)
docker compose exec postgres psql -U srbot -d srbot_test   # the test database (pytest makes it; empty after the tests)   ✅ works (Step 2.2)
docker compose up -d --wait postgres      # after a change in docker-compose.yml: new container, the data (volume) is kept   ✅ works (Step 2.2)
uv run python -m app.bot.polling          # run the bot locally (no public URL needed); stop with Ctrl+C   ✅ works (Step 1.4)
uv run uvicorn app.main:app --reload      # API for webhook mode
uv run pytest                             # tests                         ✅ works (Step 1.1)
uv run ruff check . && uv run ruff format .   # lint + format          ✅ works (Step 1.1)
uv run ruff format --check .              # only report, change nothing (what CI runs)   ✅ works (Step 1.3)
uv sync --locked                          # fail if uv.lock is out of date (what CI runs) ✅ works (Step 1.3)
# CI runs on GitHub on every push and pull request: https://github.com/mohaitham22/sr2-bot/actions   ✅ works (Step 1.3)
git switch main                           # start each step from the newest main ...   ✅ works (Step 2.0)
git pull                                  #   ... with the merged PRs from GitHub      ✅ works (Step 2.0)
git switch -c step-2.1-test-set           # one branch per step: step-<n>-<short-title>   ✅ works (Step 2.0)
git push -u origin step-2.1-test-set      # first push of the branch (Claude asks first), then open the PR on GitHub   ✅ works (Step 2.0)
git diff main...step-2.1-test-set         # what the PR changes (Claude's review reads this)
git branch -D step-2.1-test-set           # only after GitHub shows "Merged": -D, because git can't see a squashed branch as merged
git fetch --prune                         # forget branches that were deleted on GitHub
uv run mlflow ui                          # http://localhost:5000
uv run python -m ml.train_baseline
uv run python -m eval.run_eval
uv run python -m eval.whisper_test        # Step 1.6 Whisper test: local models, then Groq → eval/voice/results.csv (resumes)   ✅ works (Step 1.6)
uv run python -m eval.whisper_test --engine local --models small   # one engine / model only   ✅ works (Step 1.6)
uv run python -m eval.score_whisper       # score results.csv → scores.csv, review.md + summary table   ✅ works (Step 1.6)
uv run python -m eval.check_test_set      # Step 2.1: check eval/test_set.csv → problems, coverage, SHA-256 (exit 1 on a problem)   ✅ works (Step 2.1)
uv run python -m eval.check_test_set --path eval/test_set_original.csv   # check another file   ✅ works (Step 2.1)
uv run python -m ml.sample_311            # Step 1.7: read the 16 GB 311 export → HPD sample + full counts in ml/data/raw/ (about 3 min)   ✅ works (Step 1.7)
uv run python -m ml.prepare_311           # Step 1.8: label the 311 sample → ml/data/processed/311_mapped.csv + counts per category/urgency (about 2 s)   ✅ works (Step 1.8)
uv run python -m app.db.seed.generate_units   # Step 1.9: make app/db/seed/units.csv (seed 42 → 188 units); commit the CSV if it changes   ✅ works (Step 1.9)
uv run jupyter nbconvert --to notebook --execute --inplace ml/notebooks/01_explore_311.ipynb   # run a notebook, outputs saved in the file (or VS Code: kernel .venv, Run All)   ✅ works (Step 1.7)
docker compose up -d metabase             # http://localhost:3000
```
Note: Momo's terminal is Windows PowerShell 5.1, where `&&` does not work. Run the two ruff commands one after the other.
Note: PowerShell 5.1 removes double quotes *inside* arguments passed to programs like `docker` (e.g. `sh -c '... "x" ...'`). Keep commands simple (as above), or use Git Bash for nested quotes.
Note: Rancher Desktop must be running before any `docker` command.
Note: pytest's database tests need Postgres running: they use `srbot_test`, never `srbot`. Without `DATABASE_URL` (CI until Step 2.11) they are skipped; with it but Postgres off, they fail with what to start.
Note: only one copy of the bot can poll at a time; a second one gets a `Conflict` error from Telegram. The bot needs no Docker.
Note: voice notes are saved to `eval/voice/raw/` only from the Telegram user IDs in `VOICE_SAVE_USER_IDS` (`.env`, a JSON list like `[123456789]`; the brackets are required). Your ID = the `chat_id` in the bot's log for your private chat.
Note: messages sent while the bot is off wait at Telegram (pending updates) and all arrive at once when it starts.
Note: Momo's terminal uses code page cp1252 and cannot print Arabic. Scripts write Arabic only to UTF-8 files. To send Python output with Arabic to a file, set `PYTHONIOENCODING=utf-8`.

---

## 7. Data model (Step 1.11; built in Step 2.2)
Summary only. Types, every CHECK rule, ON DELETE rules, indexes and the ER diagram: `docs/design_notes.md` §2.
Code: `app/db/models.py`; tables made by Alembic migration 1 (`db87004e7de1`). Confidences are `double precision`.
| Table | Columns |
|---|---|
| `compounds` | id, name_en (unique), name_ar (unique) |
| `units` | id, compound_id → compounds, building (`A`–`F`), unit_number (`B-201`, first letter = building); unique(compound_id, unit_number) |
| `users` | id, telegram_user_id (unique, bigint), name, phone (E.164), created_at |
| `user_units` | user_id → users, unit_id → units, confirmed_at; PK (user_id, unit_id) |
| `service_requests` | id (identity BY DEFAULT), ticket_no (unique, `SR-YYYYMMDD-NNNN`), user_id → users (empty after `/forget`), unit_id → units, description, language (`ar` / `en`), category, subcategory (`ac` only), urgency, status (open / in_progress / closed), created_at, closed_at (set only when closed) |
| `predictions` | id, sr_id → service_requests, model_name, model_version, category, category_confidence, subcategory, urgency, urgency_confidence, needs_review, created_at; unique(sr_id, model_name, model_version) |
| `messages` | id, telegram_chat_id (bigint), sr_id → service_requests (nullable), role (`user` / `bot`), text, created_at |

`compounds` and `units` get their rows from the mock registry `app/db/seed/units.csv` (Step 1.9).
Metabase reads only `compounds`, `units`, `predictions` and the view `dashboard_service_requests` (= `service_requests` without `description` and `user_id`), as the read-only user `metabase_reader`.

**Labels:**
- Categories (8): `plumbing`, `electricity`, `ac`, `carpentry`, `pest_control`, `gas`, `appliances`, `general`. The brief lists 6; `gas` and `appliances` were added in Step 1.8 (D5/D6 B, instructor approval pending). `ac` = cooling + heating + ventilation, with a sub-label.
- Urgency: `low`, `medium`, `high`. Rules are defined in `docs/labeling_guide.md` (words) and `ml/label_mapping.py` (the 311 rules as code).

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
- **The synthetic training data comes from a different model family than the test set.** The test set is written by Claude, so the training data is never written by Claude (Step 2.1).

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
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`, `style:`). Keep PRs small.

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

### Phase 1: Foundations (weeks 1–2) ✅ → Gate: scope freeze (frozen 2026-10-28, section 16; instructor review pending)
**Phase 1 order (exception to the usual order):** setup → bot → Whisper test → data → design → review.
Step-by-step prompts: `docs/prompts/phase1.md` (Steps 1.0–1.12).

**Data & ML**
- [x] Download the NYC 311 data and keep only housing complaints (Momo's export, filtered to HPD by `ml/sample_311.py`; explored in Step 1.7)
- [x] Map complaint types to the categories and an urgency level (8 categories: the brief's 6 + gas, appliances; `ml/label_mapping.py`, Step 1.8)
- [x] Write `docs/labeling_guide.md` (Step 1.8)
- [x] Start `docs/data_card.md` (version 1: 3 sources in use + 3 planned for Phase 2; Step 1.10)

**LLM & Speech**
- [x] Get Groq and Gemini API keys
- [x] Record a few Arabic and English voice notes (15: 10 Egyptian Arabic, 5 English; Step 1.6)
- [x] Test Whisper on Egyptian Arabic early (top risk in the brief): best 80% usable < 85% target → `large-v3` + always confirm the transcript (Step 1.6, `eval/reports/whisper_phase1.md`)
- [x] List the required fields (type, examples, rule, follow-up question for each; `docs/design_notes.md` §1, Step 1.11)

**Backend & Memory**
- [x] Create the bot with @BotFather
- [x] Set up the repo structure and `.env` config
- [x] Build a polling bot that receives text and voice (text ✅ Step 1.4; voice ✅ Step 1.5)
- [x] Generate the mock unit registry (4 fictional compounds, 188 units, seed 42; `app/db/seed/`, Step 1.9)
- [x] Sketch the DB tables on paper (7 tables + ER diagram, tested in Postgres with ROLLBACK; `docs/design_notes.md` §2, Step 1.11)

**Dashboard & DevOps**
- [x] Set up the GitHub repo and install Rancher Desktop
- [x] Write a docker compose file with Postgres and Redis
- [x] Create a first GitHub Actions workflow (ruff + pytest)
- [x] List the dashboard charts the brief asks for (5 charts: columns, SQL idea, what to store; `docs/design_notes.md` §3, Step 1.11)

**End of phase:** the bot replies, the data is mapped, and the scope is frozen. New ideas go on a stretch list.

---

### Phase 2: Core AI (weeks 3–4) ◀
**Phase 2 order (the test set first, not the usual role order):** 2.0 kickoff → 2.1 test set review + checker → **test set frozen (row count + hash in section 13)** → 2.2 DB models + Alembic → 2.3 Redis session store → 2.4 LLM client → 2.5 STT service → 2.6 synthetic data + translated subset → 2.7 baseline + MLflow → 2.8 extraction → 2.9 follow-up questions → 2.10 LangGraph skeleton → 2.11 Dockerfile + stronger CI → 2.12 Metabase + fake rows → 2.13 review.
Step-by-step prompts: `docs/prompts/phase2.md` (Steps 2.0–2.13). One branch + one PR per step (section 13, 2026-10-29).
Where a prompt disagrees with section 13, section 13 wins (checked in Step 2.0):
- 2.2: 7 tables, `compounds` included (Step 1.11 D6 B); the prompt lists 6.
- 2.4: the prompt retries on 429 + 5xx with jitter; Step 1.6 D8 A retried only on 429 → decide in 2.4.
- 2.5: STT is local faster-whisper `large-v3`, never the Groq API (2026-10-25, D10 A). So no "local backup when Groq fails" question and no 429 retry; the quality signals (`avg_logprob`, `no_speech_prob`) come from faster-whisper itself.
- 2.7: the prompt trains on synthetic data only; the brief names NYC 311 as the training data, and the data card says "Phase 2 decides" → decide in 2.6/2.7 and tell the instructor.
- 2.8: phone = E.164, any country (Step 1.11 D1 C), not "+20 → 0".
- 2.9: question order, grouping and "after 3 wrong answers" are decided (Step 1.11 D4 B); the fixed question texts are in `docs/design_notes.md` §1.
- 2.11: `main` protection is set up in Step 2.0 (D3 A); 2.11 adds the new CI jobs to the ruleset and does the learning test.

**Data & ML**
- [ ] Build the TF-IDF + logistic regression baseline for category and urgency; log it in MLflow
- [ ] Generate synthetic Egyptian Arabic requests and a translated subset
- [x] AI-written test set (`eval/test_set.csv`): reviewed and frozen (never used for training). Step 2.1: 252 rows, checker 0 problems; frozen as v1 (hash in section 13)

**LLM & Speech**
- [ ] Write `app/services/stt.py` using self-hosted Whisper (`faster-whisper`)
- [ ] Create the Pydantic extraction schema and the extraction prompt
- [ ] Add follow-up questions for missing fields
- [ ] Validate the output; re-ask once if the JSON is broken

**Backend & Memory**
- [x] Build the SQLAlchemy models and Alembic migrations (Step 2.2: 7 tables, migration 1, the registry loaded, tests on `srbot_test`)
- [ ] Build the Redis session store (`session:{chat_id}`, 30-minute expiry)
- [ ] Define the LangGraph state

**Dashboard & DevOps**
- [ ] Write a Dockerfile for the app
- [x] Make CI run on every PR (`pull_request:` since Step 1.3; since Step 2.0 the ruleset `protect-main` makes `main` need a PR and a green "Lint, format and test"; a failing PR is tested in Step 2.11)
- [ ] Run Metabase locally and connect it to Postgres with fake rows

**End of phase:** each piece works on its own. Text goes in, valid JSON comes out, and there is a baseline F1 number.

---

### Phase 3: Integration (weeks 5–6) → Gate: end-to-end demo ⭐
**Data & ML**
- [ ] Wrap the model in `app/services/classifier.py`; it returns category, urgency, and confidence
- [ ] Save the model file with a version number

**LLM & Speech**
- [ ] Turn STT and extraction into LangGraph nodes
- [ ] Show the voice-note transcript; the user confirms or corrects it before extraction (Step 1.6 D11 A)
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
- [ ] Decide if clear audio can skip the transcript confirmation (D11 B: needs a confidence signal that predicts mistakes; see the Whisper report)

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
- [ ] Re-measure Whisper `large-v3` speed on the server CPU; switch to `medium` if it is too slow (Step 1.6 D10 A)

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
| 2026-10-25 | CI runs on every push to any branch and on every pull request (D1 A) | Simplest; a plain push shows the result. Double runs while a PR is open are free in a public repo. Switch to "push to `main` + PRs" if they get noisy |
| 2026-10-25 | CI pins uv `0.12.19`, the laptop's version (D2 A) | CI = laptop, repeatable results. Update `ci.yml` together with the laptop's uv |
| 2026-10-25 | Actions pinned by readable version (D3 A, amended): `actions/checkout@v7` (major tag), `astral-sh/setup-uv@v10.3.2` (exact tag). Switch both to commit SHAs in Phase 5 | setup-uv has no `v10` tag, only exact tags from immutable releases (the first run failed on `@v10`). CI has no secrets and a read-only token, so a moved tag can do little harm now; the Phase 5 deploy step adds real secrets |
| 2026-10-25 | Commit type `ci:` for CI files added to section 10 (D4 A). `style:` (formatting only) added too, because the learning-test fix used it | Standard Conventional Commits types; clearer history than `chore:` |
| 2026-10-25 | aiogram `>=3.31.0,<4` (Step 1.4 D1 A). aiogram needs `pydantic<2.14`, so pydantic went from 2.14.1 to 2.13.5 | The brief names aiogram 3; `<4` blocks breaking changes; `uv.lock` pins the exact versions |
| 2026-10-25 | Async code is tested with `asyncio.run()` inside normal tests, no `pytest-asyncio` (D2 A). Revisit in Phase 2 | No new dependency; enough for a few async tests. Redis/DB tests may need the plugin |
| 2026-10-25 | `/start` greeting in English + Egyptian Arabic, in one message (D3 A) | The brief: Arabic + English; matches how residents write |
| 2026-10-25 | The bot logs only update type, chat ID and text length, in one outer middleware. Every entry point calls `setup_logging(secrets=[...])`, which replaces each secret with `***` in every log line, tracebacks included (D4 B) | Section 9. The token is part of every request URL, and some aiohttp error messages contain that URL. One place to keep safe |
| 2026-10-25 | Polling asks Telegram only for the update types our handlers use (`resolve_used_update_types()`). The Bot has no default parse mode | Less traffic; user text is sent back as plain text, never read as HTML |
| 2026-10-25 | Ctrl+C on Windows: polling runs as a Task behind `asyncio.shield`; on cancel we call `dp.stop_polling()`, then re-raise (D5 B) | aiogram can't catch signals on Windows. asyncio's cancel closed the connection before polling stopped, which logged a false "Failed to fetch updates" ERROR on every stop |
| 2026-10-25 | Entry-point modules use a fixed logger name (`app.bot.polling`), not `__name__` (D6 B) | With `python -m`, `__name__` is `__main__`; a stable name is easier to search in logs |
| 2026-10-25 | Test voice notes are saved as `eval/voice/raw/YYYY-MM-DD_NNN.ogg` (Step 1.5 D1 A): laptop's local date; next number = highest of that day + 1; an empty file is created at once to reserve the name | Short names for `reference.csv` (Step 1.6), files sort in recording order. Reserving the name stops two handlers running at the same time from taking one name (seen live: 2 pending updates → `003` + `004`). Deleting the latest file reuses its number, so delete its `reference.csv` row too |
| 2026-10-25 | Voice notes are saved only from the Telegram user IDs in `VOICE_SAVE_USER_IDS` (`.env`, JSON list) (D2 A). Empty = nobody's. Anyone else gets "not available", and nothing is downloaded | The bot is public, and Step 1.6 sends `eval/voice/raw/` to Groq: a stranger's real voice must never get there (section 9). Real IDs only in `.env`, never in the repo |
| 2026-10-25 | Audio is saved to disk only for our own test recordings with fake data; the real flow (Phase 3) transcribes in memory and keeps no audio. The whole folder `eval/voice/raw/` is git-ignored, not only audio file types | Voice notes are personal data (section 9); the repo is public and git never forgets |
| 2026-10-25 | Handlers get paths and settings through aiogram workflow data (`dp["voice_dir"]`, dependency injection); settings are read only in `main()`. `build_dispatcher()` sets it up, and one test checks the wiring in CI (Momo: "do your recommendation") | One place reads settings; tests pass a temporary folder. Phase 3 will inject more values (Redis, DB), so a name mismatch must fail in CI, not live. Duplicate check by `file_unique_id` and content type in the middleware log: not now |
| 2026-10-26 | Step 1.6 follows `docs/prompts/phase1.md` (self-hosted faster-whisper in 4 sizes, Groq only as a comparison), not an older pasted version that tested only the Groq API (D1 A) | Matches the brief ("self-hosted", "test Whisper sizes early") and the 2026-10-25 decision; gives CPU numbers to choose a size |
| 2026-10-26 | `eval/voice/reference.csv` uses Momo's columns: `id, file_name, language, noise, text, expected_compound/building/unit/name/phone, expected_category, notes` (D2) | The `expected_*` columns let the script check each number exactly |
| 2026-10-26 | "Usable for extraction" = the problem is clear AND compound, building and unit are right (if said; digits or words). Phone scored apart; names not scored (D3 B). A unit letter written as ب stuck to the number counts (Momo, V07) | Rule fixed before seeing results; the bot confirms details with the user anyway |
| 2026-10-27 | `faster-whisper` in main dependencies, `groq` in the `dev` group (D4 A). Whisper models go to the git-ignored `models/whisper/` on D:, through the new optional setting `STT_MODEL_DIR` (a relative path starts at the project root) (D5 A) | `stt.py` needs faster-whisper in Phase 2; groq is only for the comparison now. C: was 96% full; the 4 models take 6.7 GB |
| 2026-10-27 | Whisper tests run on 4 CPU threads (D6 A) | Like the 4-core free server; the laptop has 8 |
| 2026-10-27 | `pyproject.toml`: `[tool.uv] constraint-dependencies = ["av<19"]` (D7 A) | faster-whisper 1.2.1 calls `av.open(metadata_errors=...)`, which av 19 removed. Remove the line when a faster-whisper release works with av 19 |
| 2026-10-27 | Our own `with_retry()` for HTTP 429: wait `retry-after`, else 2/4/8/16 s, at most 5 tries, only 429; the SDK's retry is off (D8 A) | Visible in the logs and testable with a fake `sleep`; Phase 2 `llm.py` needs the same. Seen live: Groq free tier = 20 requests per minute, `retry-after: 3` |
| 2026-10-27 | Claude judges each different transcript first with a reason; Momo reviews the Arabic ones and decides (D9 A). Judgments in `eval/voice/judgments.csv` | Fast; Momo is the native speaker. An LLM judge can be wrong, so a human checks |
| 2026-10-27 | STT model: local `large-v3`, int8, CPU (D10 A). Backup: `medium` if the server is too slow (re-measure in Phase 5) | 80% usable Arabic (same as medium and Groq; target 85% not met), the only local model that kept the problem in 10/10 notes, best CER (0.24), language 15/15. Cost: about 21 s (language set) / 28 s (auto) for a 25 s note on 4 laptop threads |
| 2026-10-27 | Always show the transcript of a voice note; the user confirms or corrects it before extraction (D11 A) | The brief's fallback. No model reached 85%; the typical mistakes (a unit letter, one digit, a lost word like "gas") take a person seconds to spot |
| 2026-10-27 | All of `eval/voice/` is git-ignored: voice notes, reference, results, scores, judgments, review (D12 A). Only the scripts, tests and the report (phones masked) are committed | Momo's words and fake phone numbers must not stay in a public repo forever |
| 2026-10-27 | 311 source: Momo's local export (2026-10-22, all rows), filtered by `ml/sample_311.py`; not the API (Step 1.7 D1 B). Closes the 2026-10-25 question; the export stays in `ml/data/raw/` | Already on disk, no internet needed, 3 minutes to read. Cost: repeating it needs the same export (a newer one differs a little: 2 rows in 5 days) |
| 2026-10-27 | Sample: agency `HPD`, 2025-10-01 ≤ created < 2026-10-01, `unique_key` ends in 7 (about 10%), at most 100,000 rows; plus counts of ALL rows in the window per (type, descriptor, details) (D2 A) | Spread over the whole year: heat is seasonal (62% of January, 7% of August). The full counts prove the sample is fair (≤ 0.08 points off per type) |
| 2026-10-27 | Keep 14 columns, saved with API names and ISO 8601 dates; no addresses or coordinates (D3 A) | Data minimization; stable names if the website renames columns again (it did: "Problem (formerly Complaint Type)") |
| 2026-10-27 | pandas, ipykernel, nbconvert, matplotlib in the `dev` group (D4 A). Notebooks are committed with their outputs (counts and charts only) | Only ML work needs them, not the bot. The instructor can read results on GitHub. Revisit the groups when scikit-learn comes (Phase 2) |
| 2026-10-27 | **8 categories:** the brief's 6 + `gas` and `appliances` (Step 1.8 D5/D6 B). ⚠️ Differs from the brief (user flow step 6); instructor approval pending. Tie rule: gas that doesn't reach the cooker → `gas`; the cooker itself or an unknown cause → `appliances`; the water heater → `plumbing` | Momo: gas is a safety problem that needs its own category; appliances are their own trade. Cost: 311 has 0 gas-smell rows, gas is 1.2% of the sample, more classes make macro F1 harder. Going back = `ml/label_mapping.py` + its test + the guide |
| 2026-10-27 | `ac` = cooling + heating + ventilation (D1 A). New column `subcategory` (ac only: `heating`, `ventilation`; `cooling` comes from Phase 2). Phase 2 synthetic `ac` mix: 70% cooling / 20% heating / 10% ventilation. 311 "no heat" → `ac`, "no hot water" → `plumbing`, both in one row → dropped | Egyptian split units also heat. NYC has 0 cooling rows: 97.7% of the sample's `ac` rows are heating. Cooling seeds are in the guide (§7) |
| 2026-10-27 | Doors, windows, glass, locks, cabinets → `carpentry` (D2 A). Floors, tiles, stairs → `general` (D3 A). Mold → `general`, or `plumbing` if the message names a leak as the cause (D4 A). Small rows as proposed (D7): intercom, smoke/CO detectors → `electricity`; sprinkler → `plumbing`; window guard, elevator, outside, mailbox, garbage → `general` | One simple rule per trade; Egyptian floors are mostly tiles; residents rarely know the cause of mold |
| 2026-10-27 | Dropped 311 rows, with a reason: `two_categories` (no heat + no hot water), `not_in_egypt` (radiators, steam pipes, boilers, fire escapes, dumbwaiters, radiator paint), `not_maintenance` (signage, janitor), `bad_row`. 12.1% of the year | They don't exist in Egyptian compounds, or there is nothing to repair |
| 2026-10-27 | **Urgency rules** (moved from section 14). `high` = danger now, or a basic service (water or electricity for the whole unit) completely gone; `medium` = something important doesn't work; `low` = cosmetic or small. Always high: gas smell, sparks/smoke/burning smell, water on electricity, flooding, no water at all, no power in the whole unit, sewage, falling ceiling, fall risks. Only the problem decides: no extra level for who lives there or the season (D8 A). A 311 row that mixes two levels gets the higher one. Gas urgency: 3 levels, gas smell always `high` (D5 a) | Consistent and learnable from the words. Person or season modifiers (D8 B) are hard to label the same way twice |
| 2026-10-27 | Urgency labels come from rules on the 311 tree now (weak labels), from label-first synthetic messages in Phase 2, and from Momo's hand labels for the test set (D9 A) | Free and consistent. LLM labels would make the Phase 4 ML-vs-LLM comparison circular. HPD's own emergency field (dataset `ygpa-z7cr`) was not verified |
| 2026-10-27 | Two problems in one message → one SR: the category of the most urgent problem (tie: the first one mentioned), the highest urgency (D10 A) | Simple; the bot can ask for the second problem as a new request (Phase 3) |
| 2026-10-27 | `ml/label_mapping.py` design: a default per complaint type + exceptions; the most specific rule wins; `GENERAL` and `SAFETY` have no default; a problem with no rule stops `prepare_311` and no file is written | A new complaint type in a newer export never gets a label by accident |
| 2026-10-27 | Mock unit registry in `app/db/seed/`: `generate_units.py` + `units.csv` (Step 1.9 D1 A). The CSV is committed; a golden-file test checks that it equals a fresh run, value by value, not byte by byte (D2 A) | Next to the DB code that will load it; goes into the Docker image with the app. CI, Docker, Phase 3 and the instructor get it without running anything; any change shows in `git diff`. Safe in the public repo: 100% fictional. Bytes differ by OS (CRLF / LF) |
| 2026-10-27 | Compounds (D3): Olive Ridge / أوليف ريدج, Juniper Bay / جونيبر باي, Bostan El Nada / بستان الندى, Zahret El Loz / زهرة اللوز. Web check 2026-10-27: no exact match; "Olive Ridge" is close to "The Ridge" and "Olive Oasis", kept (Momo) | No Emaar names. 2 English-style + 2 Arabic-style, like real Egyptian compounds; no shared words and different first sounds, so Whisper and the LLM can tell them apart |
| 2026-10-27 | Unit format `B-204` = building letter + floor + apartment (2 digits); buildings A–F only (D4 B) | The brief's example. No P: it sounds like B in Egyptian Arabic ("بي"). Cost: B, C, D, E rhyme by voice → Phase 3 normalizes letters, and the summary confirmation catches mistakes |
| 2026-10-27 | Size (D5 B): 3–6 buildings per compound, 3–6 floors, 2–4 apartments per floor; seed 42 → 188 units in 16 buildings. Kept as is, no "seed shopping" (Momo). Own generator `random.Random(seed)`, not `random.seed()` | Small but realistic compounds. A seed is chosen before seeing the result. Other code that uses `random` can't change our numbers |
| 2026-10-28 | Data card format (Step 1.10 D1 A): a summary table + the same 8 parts per source (status, source, terms, how it was made, size and columns, where it is stored, intended use, not for) + a limits table; planned sources get a "To fill in" list. A new source gets its section before it is used; unclear terms → not used | Easy to compare sources, about 2–3 screens each. The full "Datasheets for Datasets" list (about 50 questions) is too long and fits synthetic data badly |
| 2026-10-28 | The data card holds the key numbers and links to the labeling guide and the Whisper report for details (D2 A) | The reader gets the main facts; big tables stay in one place, so two copies can't drift apart |
| 2026-10-28 | No license for our own data yet (D3 A). The repo has no `LICENSE` file, which means "all rights reserved" by default | Intern work may belong to Emaar; the instructor decides if and how it is licensed (section 14) |
| 2026-10-28 | Field rules (Step 1.11, `docs/design_notes.md` §1): the LLM copies values out of the message; Python cleans and checks them (registry, phone, name). Missing = `null`, never a guess | An LLM can invent a unit; the registry can't. One place for every rule |
| 2026-10-28 | Phone: any country (D1 C), stored as E.164 (`+201XXXXXXXXX`). Without `+`: only an Egyptian mobile (11 digits, 010/011/012/015) is accepted and gets `+20`. Egypt (`+20`): mobile only, landlines refused. Other countries: shape only (`+`, 7–15 digits); the DB has the same shape CHECK | Momo's choice: owners with a foreign number can register. One stored format makes numbers comparable. A full per-country check needs `phonenumbers` (section 14) |
| 2026-10-28 | Name: full name (D2 B): at least 2 words, 3–80 characters, Arabic or Latin letters, spaces, `-` `'` `.`; no digits; saved as written | Momo's choice; closer to a real CRM. Cost: one more question for users who give one name. Known limit: "عبد الله" passes |
| 2026-10-28 | Unit: strict registry (D3 A): compound + building + unit must be one registry row, else the bot says "not found" and shows the valid buildings | Every SR points to a real unit (`unit_id` NOT NULL), so "top units" stays clean. The mock registry is complete by definition |
| 2026-10-28 | Follow-up questions in 3 groups, only for what is missing (D4 B): problem → unit (compound + building + unit) → contact (name + phone). Arabic questions say "محتاجين" instead of "you" verbs. Building letters أ ب ج د هـ → A–E (checked by Momo); و is not used. After 3 wrong answers the bot mentions `/reset` | At most 3 questions; people say the unit parts together. Male and female "you" verbs differ in Arabic. و also means "and" |
| 2026-10-28 | **Ticket number** (D5 B): `SR-YYYYMMDD-NNNN` = the Cairo date of `created_at` + the SR's `id` (no daily restart), at least 4 digits (`f"{id:04d}"`; plain SQL `lpad` would cut `10342`). Numbers can skip. `/status` shows only the user's own SRs; others get "not found". Closes section 14 | The DB sequence makes it unique (no race condition), and the date stays readable. The ownership check, not the number, protects privacy |
| 2026-10-28 | Compound names in a `compounds` table (id, name_en, name_ar, both UNIQUE); `units.compound_id` points to it (D6 B). `units.building` is kept next to `unit_number`, with a CHECK that they agree. Closes section 14 | Normalization: each name stored once, and the database itself blocks a second spelling. The building copy makes "top buildings" easy |
| 2026-10-28 | `predictions`: one row per SR per model run with `category_confidence` and `urgency_confidence` + `subcategory` (D7 A); `service_requests` gets `subcategory` too | Simple queries, and we can see which answer was unsure. Section 7 had one confidence for two answers and no `subcategory` (Step 1.8) |
| 2026-10-28 | `/forget` (D8 C), one transaction, in this order: SR descriptions → `[deleted]`; delete `messages` by chat ID; delete the `users` row (→ `user_units` CASCADE, `service_requests.user_id` SET NULL); delete the Redis keys. The bot asks first and warns about open SRs | The dashboard numbers stay right, and nothing with the person's name, phone or words is left. Step 1 must come before step 3 |
| 2026-10-28 | SR status history: only `status` + `closed_at` (D9 A) | Enough for all 5 charts in the brief, "open over time" included. `in_progress_at` (D9 B) and a history table (D9 C) → stretch list |
| 2026-10-28 | Metabase (D10 A): own read-only user `metabase_reader` that can read `compounds`, `units`, `predictions` and the view `dashboard_service_requests` (no `description`, no `user_id`); not `users`, `messages`, `user_units`. Report time zone `Africa/Cairo` | Section 9: names, phones and message texts can never appear on the dashboard. Tested: the role was denied |
| 2026-10-28 | Smaller DB rules (Momo accepted): a `users` row is made at the first "yes", not at `/start`; `messages` has no `user_id` (found by chat ID); labels are `text` + CHECK, not ENUM; times are `timestamptz` (UTC); Telegram IDs are `bigint`; FK indexes added by hand, but not `predictions (sr_id)` (the UNIQUE index covers it); `service_requests.id` is identity BY DEFAULT, so the app can insert the id it took for the ticket | Store nobody who only says hello; a CHECK is easier to change in a migration than an ENUM; Telegram IDs can be bigger than an integer holds; Postgres doesn't index FKs by itself. Found or confirmed in check C1 |
| 2026-10-28 | Keep the 16 GB 311 export in `ml/data/raw/` (Step 1.12, export A). Closes the Step 1.7 TODO | `sample_311` can be re-run at any time (Step 1.12 re-run: byte-identical); a new download is a different file. Cost: 16 GB on D:, and the Phase 2 Dockerfile needs a `.dockerignore` (section 17, T1) |
| 2026-10-28 | Stretch list = CLAUDE.md section 16 (Step 1.12 D1 A) | Read in every session; the list is short and must be seen when a new idea comes |
| 2026-10-28 | Technical-debt list = section 17, each debt with "pay back in phase X" (D2 A) | The Phase 1 TODOs move with the progress log to `docs/progress_log.md`; a list here keeps them visible |
| 2026-10-28 | **Scope freeze** (D3, Momo's wording; full text at the top of section 16): in scope = the brief + section 13; a new idea goes to section 16 first and moves into a phase only after the week-6 gate passes and the core success criteria are on track, with a section 13 entry (instructor first); bug fixes and "how" choices are not scope changes; removing scope is allowed anytime | The brief's risk table: "Scope creep → freeze scope after week 2; extras go to a stretch list". The week-6 end-to-end demo comes before any extra |
| 2026-10-28 | Stretch list S1–S11 and debt list T1–T9 as proposed (D4). S11 (photos) kept, with a privacy note | Photos can show faces and the inside of homes: they need a storage and deletion plan before any code |
| 2026-10-29 | Step 1.12 committed in 2 commits, content + CLAUDE.md (D5 A). Milestone tag `phase-1-done` is **annotated** (D6 A) and is added only after the instructor has reviewed `docs/phase1_summary.md` (Momo) | Same history pattern as Steps 1.9–1.11. An annotated tag stores who, when and why. The tag marks the reviewed state, so any fix the instructor asks for goes in before it |
| 2026-10-29 | **Phase 2 order** (`docs/prompts/phase2.md`, section 12): Step 2.1 prepares the test set, then Momo writes it by hand over the next days while Steps 2.2–2.5 run; it is frozen (≥ 200 rows; row count + SHA-256 recorded here) before Step 2.6; then 2.6–2.13 | Brief: the test set is "written and labeled by the interns themselves, kept out of training". Written before Momo sees synthetic data or model results, it stays independent (no leakage, no tuning on the test). Steps 2.2–2.5 don't need it |
| 2026-10-29 | **Git workflow** (Step 2.0 D1 A, D2 A): one branch per step, made from an up-to-date `main`, named `step-<n>-<short-title>` (e.g. `step-2.1-test-set`); one PR per step; **squash and merge**, PR title = a Conventional Commit with the step number (e.g. `feat: redis session store (step 2.3)`). Ends Phase 1's direct commits to `main`. Claude still asks before each commit and push | Brief: "All interns review each other's pull requests". `main` always passes CI; each step = one commit on `main`, easy to undo; the PR page shows the instructor the whole step. Cost: after a squash, git can't see the branch as merged, so it is deleted with `git branch -D`, only after GitHub shows "Merged" |
| 2026-10-29 | **`main` protected** (D3 A): GitHub ruleset `protect-main` on the default branch: PR required (0 approvals), check "Lint, format and test" must pass, no force push, no deletion, empty bypass list. Repo settings: squash merging only, default message = PR title, head branches deleted after merge | CI can't be skipped. 0 approvals, because GitHub never lets an author approve their own PR (1 would lock Momo out). Cost: even a one-line doc fix needs a PR |
| 2026-10-29 | **PR reviews** (D4 A): Claude reviews in the chat from `git diff main...<branch>` (each finding with `file:line`, marked "must fix" or "suggestion"; helper prompt "Review my pull request" in `phase2.md`); Momo writes a 1–2 line summary on the PR and merges. No GitHub CLI (`gh`) for now | No new tool; the summary is in Momo's words. Limit: Claude helped write the code, so it is a second look, not an independent review; the instructor is the independent reviewer |
| 2026-10-29 | GitHub's automatic Copilot review of PRs is turned off (Step 2.0 D5 A; Momo: "do what you recommend"). It came from "automatic review settings", not from the ruleset | D4 A: Claude reviews in the chat. A tool outside our stack (rule 9); with no quota it only posts "unable to review" on every PR |
| 2026-10-29 | **AI-written test set** (Momo, Step 2.1): every row of `eval/test_set.csv` is written by Claude (chat), `author = ai` (222 rows on arrival). Claude Code checks them against the guide and the registry; Momo decides every change. Replaces "Momo writes it by hand while Steps 2.2–2.5 run" (Phase 2 order above): the test set is frozen right after Step 2.1. Claude Code may read the rows (closes the Step 2.0 TODO). ⚠️ Differs from the brief ("written and labeled by the interns themselves"; risk table: "Hand-written test set"); Momo tells the instructor, approval pending | Momo's choice: one file with all planned edge cases (tags), ready now. **Risks:** (1) scores too optimistic, because the synthetic training data is AI-written too → it comes from a different model family (section 9), the Step 2.6 leakage check drops near-copies, and every score says "AI-written test set"; (2) Claude Code's review is not independent of the writer (same family) → Momo decides; (3) Claude Code has read every row, so its Step 2.6 prompt drafts may reuse test wording → leakage check, and Momo reviews the prompts; (4) the brief's "gap between synthetic and real-style performance" is only partly measurable → optional: 20–40 messages by real people, scored apart |
| 2026-10-29 | Test set uses the **8 categories** (Step 2.1 D1 A): the 3 gas-smell rows (labeled `general`) → `gas`; about 15 `gas` + 15 `appliances` rows are added (there were 0) | The classifier learns 8 classes. A class with 0 rows can't be measured; with 3 rows, one mistake moves its recall by 33 points |
| 2026-10-29 | **Test set fits the registry** (D2 A, D3 A). Compounds: Lotus Ridge → Olive Ridge, Cedar Park → Juniper Bay, Nakhla Residence → half Bostan El Nada, half Zahret El Loz; short forms and typos keep their style (لوتس → أوليف). Number buildings → letters; every unit → a real registry unit (letter and floor kept when possible); expected `building` = the unit's letter; a self-correction keeps its wrong first value. Only location words change | The file used other compound names, buildings 1–25 and units like C-712 (112 of 150 units can't exist), so the strict registry check (Step 1.11 D3 A) would refuse almost all. The code fills the building from the unit's letter (design notes §1.4), so the expected value must too, or the eval counts it as a hallucination. Changing the registry instead (D3 C) would undo Steps 1.9 and 1.11 |
| 2026-10-29 | Expected `phone` in E.164, `+20…` (D4 A); the message text keeps the resident's way of writing | The format the code stores (Step 1.11 D1 C), so the eval compares cleaned values directly |
| 2026-10-29 | A message too vague for any category (T076) stays for the extraction tests, with empty `category` and `urgency` and the tag `vague`; the classifier score skips it (D5 A). Vague rows with a clear category keep their labels | Labeling guide §6: too vague to label = not a classifier test message. It still tests the follow-up "what is the problem?" |
| 2026-10-29 | **Test set not in git** (D6 A): `eval/test_set*` is git-ignored (the file, the untouched original `eval/test_set_original.csv`, the review file). The hash goes in this log at the freeze; Momo sends the file to the instructor privately and keeps a backup. CI tests the checker with a tiny fake file. Closes the test-set part of the section 14 question | Its "fake" phone numbers are random Egyptian mobiles that may belong to real people (same reason as Step 1.6 D12 A). The answers stay private too |
| 2026-10-29 | **Test-set label review** (Step 2.1, Momo accepted all): 43 rows changed, no message text. G1 (27 rows, clear by the guide): gas smell → `gas`; electric water heater → `plumbing`; AC water on a socket → `electricity`; intercom and doorbell → `electricity, low`; toilet running → low; exhaust fan → `ac, medium`; AC smell → low; broken lock, elderly parent, rat → `medium` (D8 A). G2 (12, the guide's rule order): smoke from the AC → `electricity`; water near a light → `electricity`; the building door → `carpentry`; peeling paint → low; skirting board → `general`; basement water → `plumbing`. G3: scorpion stays high; elevator stays medium (debt T10); a dripping tap → low (T099, T204). T155 gets `arabic_digits`; T076 has no labels (D5 A). Labeling guide v1.2 makes 3 cases clear: smoke from the AC, scorpion or snake, dripping tap | 39 of 222 AI labels (18%) broke our guide: Claude chat never saw it. After the review, no row has `ac` + `high`: by the guide, the AC itself is never danger now, so the Step 2.6 data must not make that pair either |
| 2026-10-29 | **30 extra test rows** (D1 A, author `ai`): Claude (chat) wrote T223–T252 from `docs/prompts/test_set_extra_rows.md` (our guide, registry and field rules; no test message): 15 `gas` (8 high, 5 medium, 2 low) + 15 `appliances` (9 medium, 6 low, 0 high). Momo accepted the numbers and the first `gas, low` example (a stiff valve or a broken meter cover, no smell), now in guide v1.2 | Gas had 3 rows and appliances 0. With the rules in the prompt, all 30 passed the checker and the label review the first time (the first 222 needed 39 label and 167 location fixes). No `appliances` + `high`: danger from a device is `electricity` or `plumbing` by the guide |
| 2026-10-29 | **Test set frozen (v1):** `eval/test_set.csv`, **252 rows**, SHA-256 **`786e72ad2179f88b3d1c9418dd84038154bfae39c4da18c819db9d18754ecbcc`** (computed by `uv run python -m eval.check_test_set`, line ends read as LF); checker 0 problems; labeling guide v1.2. Last look: 20 random rows (seed 2026) all agree with the guide; T082 (a door handle came off) stays `medium`. **From now on no change** without a new entry here: fix the row with the guide (and check its similar rows, not only the model's errors), run the checker, record "Test set changed (v2)" with the id, old → new label, reason, row count and new hash, then re-run every score on v2 | The test set is the ruler for every model (baseline, v2, LLM zero-shot): if it changes between measurements, a better score may come from an easier test. Changing it after seeing results is tuning on the test. Fixing only the rows the model got wrong moves the score in one direction. The hash proves which version a score used; never mix v1 and v2 scores in one table |
| 2026-10-31 | New main dependencies (Step 2.2 D1): `sqlalchemy[asyncio]>=2.1.6,<2.2` (MIT; the extra adds `greenlet`, which async needs), `asyncpg>=0.32.0` (Apache-2.0), `alembic>=1.20.1,<2` (MIT) | The app needs them at run time; Phase 5 runs migrations on deploy. A SQLAlchemy minor version can change behavior, so `<2.2`. `uv.lock` pins the exact versions |
| 2026-10-31 | `DATABASE_URL` stays `postgresql://…` in `.env`. One helper in `app/db/session.py` adds the driver `+asyncpg`; the app and Alembic's `env.py` both use it. A URL that already has `+asyncpg` is kept as it is (tested) (D2 A) | One place for the rule; no `.env` edit; the same plain URL works for other tools and for the CI service in Step 2.11 |
| 2026-10-31 | **Labels in one place:** `app/schemas/labels.py` (8 categories, 3 urgencies, the `ac` subcategories); `ml/label_mapping.py` imports them (D3 A; Momo OK'd the ml change, rule 10). Labels are `text` + CHECK (Step 1.11). A label change later = `labels.py` + a hand-written migration (UPDATE the old rows, drop the old CHECK, add the new one). A migration writes its label list literally and never imports `labels.py` | One list for the database, the classifier and the extraction schema (Steps 2.7–2.8); the app no longer depends on training code. Alembic's autogenerate does not see CHECK changes. A migration is history: it must always build what existed at its time |
| 2026-10-31 | **Test database** (D4 A): `<POSTGRES_DB>_test` (e.g. `srbot_test`) in the same container, created and migrated by the tests; each test runs in a transaction that is rolled back at the end. Guard: the fixtures refuse any database whose name doesn't end in `_test`. An insert that must fail runs inside a SAVEPOINT (`begin_nested`). DB tests are skipped when `DATABASE_URL` is not set (CI until Step 2.11) and fail with a clear message when Postgres is off | Tests can never touch Momo's dev data, even with a wrong URL. In Postgres one error aborts the whole transaction; the savepoint undoes only the failed insert, so the test can go on and the final rollback still cleans up. A silent skip on the laptop would hide a stopped Docker |
| 2026-10-31 | Async tests keep `asyncio.run()` (D5 A; confirms the 2026-10-25 D2 A). **Revisit in Phase 3:** FastAPI depends on AnyIO (through Starlette), and AnyIO has its own pytest plugin, so async fixtures may need no new dependency then | No new dependency for a few DB tests |
| 2026-10-31 | **Indexes** (D6 A): only the 4 of design notes §2.8: `service_requests (created_at)`, `(user_id)`, `(unit_id)` and `messages (telegram_chat_id)`; none on `category` or `status`. Foreign keys with no index at all: `user_units.unit_id` and `messages.sr_id`. More indexes only if `EXPLAIN` shows a need in Phase 4, in a new migration | An index costs time on every insert; columns with few values (low cardinality) rarely use one; with a few hundred rows a full read takes under 1 ms. A missing FK index only slows the delete of a parent row, and registry units and SRs are never deleted |
| 2026-10-31 | `predictions.category_confidence` and `urgency_confidence` are `double precision`, not `real` (Step 2.2, Momo: B). Design notes v2 updated, with the other small changes `models.py` made (ticket pattern CHECK, 2 `closed_at` CHECKs, `confirmed_at` default now, `ON DELETE RESTRICT` written out, unit regex) | 8 bytes like Python's `float`, so a value comes back exactly as saved; as `real` (4 bytes) 0.87 came back as 0.8700000047683716. The size difference doesn't matter at our scale |
| 2026-10-31 | **Database errors and personal data** (Step 2.2, privacy A). Found with fake data on `srbot_test`: when a rule refuses a row, Postgres sends the whole row back as `DETAIL: Failing row contains (…, name, phone, …)`. `hide_parameters` doesn't hide it (it is in asyncpg's error, the *cause* in the chain, which every traceback prints), and the Postgres server log had it too. Fixed now: `RedactingFormatter` replaces every `DETAIL:` line in every log line, tracebacks included; Postgres runs with `log_error_verbosity=terse` (`docker-compose.yml`). Tested with a real refused insert. PR #3 review (M1) found a second path: for a value of the wrong type, asyncpg writes the value itself into its error (`invalid input for query argument $1: '<value>'`), even in `str(error)`; the formatter now hides everything after `query argument $N:` too, tested with a real wrong-type insert. The rest is debt T11 (Phase 3) | Section 9: name and phone never in logs or error messages. Cost: debugging a refused row shows the rule's name, not the row |
| 2026-10-31 | The view `dashboard_service_requests` and the user `metabase_reader` come in Step 2.12, not in migration 1 (D7 A). The password is read from `.env` at run time and is never written in a migration file. Step 2.12 explains whether a database user (server-wide, not part of one database) belongs in a migration or in a setup script | Step 2.12 owns Metabase and its `.env` values. Migration files are committed to the public repo |
| 2026-10-31 | Smaller Step 2.2 choices: `alembic.ini` has no database URL (`env.py` reads it through `session.py`); migration file names start with the date; a ruff hook formats every new migration, and `script.py.mako` uses modern type hints; `load_units.py` only inserts missing rows (`ON CONFLICT DO NOTHING`), never updates or deletes, and stops with nothing saved when the database differs from the CSV; the test helpers (`run_in_rollback`, fake rows) live in `tests/conftest.py`; no `relationship()` in the models yet; `created_at` comes from the database (`now()`), never from Python | The URL holds the password, and `alembic.ini` is committed. Files sort in the order they were made; a new migration passes CI as written. A unit may already have SRs, so the seed never changes one; a person decides about a difference. Async lazy loading fails (`MissingGreenlet`), so joins are written where they are needed (Phase 3). One clock (the database's) for every time |

## 14. Open decisions (decide, then move to the log)
- Instructor approval for 8 categories (Step 1.8 D5/D6 B). If not approved: move `gas` and `appliances` back into the 6 (`ml/label_mapping.py`, its test, the guide).
- Which F1 the brief's "≥ 0.85" means: macro (every class counts the same) or weighted (by class size). Ask the instructor; with 8 unbalanced classes the two can differ a lot.
- Classifier v2: SetFit or multilingual BERT.
- Final hosting: Oracle VM or Azure Container Apps free grant.
- Value of N for conversation history, and the token budget per LLM call.
- How the bot knows a voice note's language: auto-detect (costs +35–45% time with `large-v3`) or a hint, e.g. the language of the user's last text (Phase 2, `stt.py`). Step 1.6's "language set" used the answer from `reference.csv`, which the bot won't have.
- One Telegram bot for everything, or a separate dev bot and demo/prod bot (decide before Phase 5: webhook and polling can't share one bot). Never write the bot's username or IDs in this public repo.
- License for the repo and our own data (registry, test set): ask the instructor (Step 1.10 D3 A: none yet).
- Which LLM writes the synthetic data and the translations (Phase 2). Its license decides what we may do with the outputs (data card §6: Llama 3.1+ → a model trained on its outputs and "made available" must be named "Llama…"; gpt-oss → Apache 2.0; Gemini free tier → no competing models, Google may read what we send). Use a different model for the ML vs LLM zero-shot comparison, or say it clearly in the report (circular comparison). Note: on 2026-10-28 Groq listed no Llama chat model for our key, only `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.8-27b`, `allam-2-7b` (section 17, T2).
- Whether the synthetic data goes into git (Step 2.6). Public = reproducible, but anyone can read it. The test set: not in git (Step 2.1 D6 A).
- Whether a second person labels a part of the test set, to measure agreement (Phase 2).
- Phone check for non-Egyptian numbers (Phase 2, D1 C): add the `phonenumbers` library (new dependency, Apache 2.0) for the real per-country length, or keep the shape check only.
- How long to keep `messages` of conversations that never became an SR (`/reset`, 30 min idle). Message text is personal data (section 9). Decide before Phase 3 saves messages.
- Who changes an SR's status, and how: there is no staff screen (technicians are out of scope). Idea: a demo script that closes some SRs with made-up times (Phase 4 or 6); the demo must say they are invented.

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

### Phase 1 — Foundations (2026-10-24 → 2026-10-28): ✅ done, scope frozen
- Built: repo + CI, Postgres/Redis in Docker, a polling bot (text + voice), the Whisper test (`large-v3`; 80% usable Arabic < 85% → always confirm the transcript), NYC 311 → 79,544 labeled rows (8 categories, 3 urgency levels), the mock registry (188 units), the data card and the design notes.
- Review (Step 1.12): 15/17 tasks ✅; 2 ⚠️ wait for the instructor (8 categories) and Phase 4 (85% target). Stretch list: section 16; debt: section 17; summary for the instructor: `docs/phase1_summary.md`.
- All 13 step entries (1.0–1.12): `docs/progress_log.md`. ⏸️ The tag `phase-1-done` waits for the instructor's review of the summary (commands: Step 1.12 entry).

### Step 2.0 — Phase 2 kickoff (2026-10-29)
- Phase · role: Phase 2 · All roles
- Files: `docs/prompts/phase2.md` (new, Momo's); CLAUDE.md sections 5, 6, 12, 13, 15. Branch `step-2.0-kickoff` (the first step on a branch).
- How it works: no code. Phase 1 checked: all its outputs exist, pytest 102 passed, ruff clean, `main` = `origin/main`. Phase 2's goal, tasks per role and Phase 3 links explained; train / validation / test, data leakage and "never tune on the test" taught; the step order and the git workflow logged.
- Status: ✅ quiz 5/5 (small additions given). Ruleset `protect-main` read back from GitHub's API: deletion and force-push blocked, PR with 0 approvals, required check "Lint, format and test". First PR #1: both runs (push + pull_request) green, the merge box offers only "Squash and merge". Not seen: a merge blocked by a red check (planned in Step 2.11).
- Known issues / TODO: 7 places where `phase2.md` disagrees with section 13 are listed under Phase 2 in section 12 (section 13 wins). For Step 2.1: decide if Claude may read the test-set rows (risk: their wording leaks into the Step 2.6 synthetic-data prompts). Unclear: the ruleset field `require_extra_approval_for_unattributed_changes: true` (not found in GitHub's docs on 2026-10-29; PR #1 stayed mergeable). Copilot's automatic review (failed on PR #1: no quota) → off (D5 A), Momo switches it off in the GitHub settings. `gh` is not installed (D4 A: not needed).
- What Momo did: saved `phase2.md`; chose D1 A, D2 A, D3 A, D4 A, D5 A (Claude's recommendations); answered the quiz; set up the ruleset and the merge settings; opened PR #1.

### Step 2.1 — Test set: review, check, prepare to freeze (2026-10-29)
- Phase · role: Phase 2 · Data & ML. Branch `step-2.1-test-set`.
- Files: `eval/check_test_set.py`, `tests/test_check_test_set.py`, `docs/prompts/test_set_extra_rows.md` (new); `docs/labeling_guide.md` v1.2, `docs/data_card.md` v1.2, `.gitignore`, CLAUDE.md; Momo's `docs/prompts/phase2.md`. Git-ignored: `eval/test_set.csv` (252 rows) + original, extra rows, review.
- How it works: the test set is AI-written (Claude chat; D1–D6 in section 13). The checker tests every row against the guide, design notes §1 and the registry: 501 problems in the original. Momo decided 43 label changes (guide v1.2) and the registry fit (167 rows, phones E.164); Claude chat added 15 gas + 15 appliances rows from a prompt with our rules.
- Status: ✅ checker 0 problems on 252 rows; pytest 154 passed; ruff clean; realism review: 30 random rows, 0 marked; Anthropic terms read. ✅ **Frozen as v1** (freeze prompt, same day): 20 random rows re-read, none changed; row count + SHA-256 in section 13. ⏸️ Not committed yet.
- Known issues / TODO: ⚠️ AI-written test set differs from the brief (instructor approval pending). Debt T10 (311 elevator rule) before training. The counts in `phase2.md` ("plumbing 45, …") are from before the review (Momo's file: suggestion only). Momo backs up `eval/test_set.csv` (not in git).
- What Momo did: chose D1–D6; accepted the label review (G1–G4); read the location review and 30 random rows; ran the extra-rows prompt in Claude chat and saved the 30 rows.
### Step 2.2 — Database models and migrations (2026-10-31)
- Phase · role: Phase 2 · Backend & Memory. Branch `step-2.2-db-models`.
- Files: see section 5 "Exists since Step 2.2". Changed: `ml/label_mapping.py` (imports the labels), `app/logging_setup.py` (hides `DETAIL:`), `docker-compose.yml` (terse log), `pyproject.toml` + `uv.lock` (3 dependencies), design notes v2, data card v1.3, `.env.example`.
- How it works: `models.py` describes the 7 tables of design notes §2; Alembic migration 1 builds them (18 CHECKs, 7 FKs, 6 UNIQUE, 4 indexes, personal-data comments). The ticket = the sequence's next `id` + the Cairo date, so two SRs saved at the same moment can't share one. `load_units.py` loads the registry, safe to run twice. Tests run on `srbot_test`, each one rolled back.
- Status: ✅ on `srbot`: `upgrade head` → `downgrade -1` → `upgrade head` (real output read), `alembic check` clean, also run from another folder (`prepend_sys_path = %(here)s`); seed twice: 4 + 188 new, then 0 + 0. pytest 249 passed with Postgres; CI simulation (a copy without `.env`): 186 passed + 63 skipped; ruff clean; `uv sync --locked` OK. 20 parallel SRs → 20 tickets. Privacy: a real refused row is hidden in our logs and in the Postgres log. Committed and pushed: PR #3, CI green on the first push. PR review (D4 A): 2 must-fix, both fixed in a follow-up commit (M1: asyncpg's wrong-type error shows the value itself → hidden in logs too; M2: this line).
- Known issues / TODO: debt T11 (Phase 3: clean DB errors at the source). CI runs no database test until Step 2.11 (skipped, not failed). `alembic revision --autogenerate` also creates the empty `alembic_version` table (harmless). The view + `metabase_reader` → Step 2.12 (D7 A).
- What Momo did: chose D1–D7 (with additions: no double `+asyncpg`, the `_test` guard, SAVEPOINT, the AnyIO note), double precision (B) and privacy A; read migration 1 line by line before it was applied; asked for the PR review and chose to fix M1 in PR #3.

---

## 16. Stretch list (ideas not in the brief)
**Scope freeze (Step 1.12 D3, Momo's wording):** Scope frozen on 2026-10-28 (end of Phase 1). In scope = the brief + the decisions in section 13. A new idea goes on this list first. It moves into a phase only after the week-6 gate passes and the core success criteria are on track, with a section 13 entry (discuss it with the instructor first). Bug fixes and "how" choices are not scope changes. Removing scope is allowed anytime.

| # | Idea | Note | From |
|---|---|---|---|
| S1 | Better Whisper scoring: number words → digits on both sides, remove fillers, fix reference texts by listening | Makes WER honest; does not change "usable %" | Whisper report §11 |
| S2 | Tune `large-v3`: `vad_filter`, an `initial_prompt` with the registry's compound names, float32 vs int8, force `ar` | The prompt must hold no answers from the test notes; Whisper may copy prompt words into the transcript | Whisper report §11 |
| S3 | Try Egyptian fine-tuned Whisper models and Cohere Transcribe Arabic | `MAdel121/whisper-medium-egy` was checked: not usable (mid-training checkpoint, dataset without license) | Whisper report §11 |
| S4 | A safety tip in the bot's reply for a gas smell (e.g. open the windows, don't switch on lights) | Safety advice: the text must be checked first | Step 1.8 |
| S5 | Urgency modifiers: a baby, an old or sick person, the season (D8 B) | Hard to label the same way twice | Step 1.8 |
| S6 | Two problems in one message → two SRs (D10 C) | Today: one SR, the most urgent problem (D10 A) | Step 1.8 |
| S7 | A real public AC-complaint dataset (D1 C) | NYC 311 has no cooling rows | Step 1.8 |
| S8 | Charts: share of `needs_review` SRs; Arabic vs English SRs | Both columns are stored already | Design notes §3.9 |
| S9 | Chart: voice vs text SRs | Needs a `source` column from the first SR; older SRs would have no value | Design notes §3.9 |
| S10 | `in_progress_at` (D9 B) and a full status history table (D9 C) | Today: `status` + `closed_at` (D9 A) | Design notes §3.9 |
| S11 | Residents send a photo of the problem | Privacy: photos can show faces and the inside of homes (personal data, section 9), so they need a storage and deletion plan first. Today the bot refuses photos and downloads nothing | Claude (Step 1.12) |

---

## 17. Technical debt (known weaknesses in what we built)
Each debt has a phase to pay it back. When it is paid, delete the row and say so in the progress log. A new shortcut gets a row here when we take it.

| # | Debt | Risk while it stays | Pay back in |
|---|---|---|---|
| T1 | No `.dockerignore` yet | A Docker build would send the 16 GB 311 export, 6.7 GB of models, `eval/voice/` and `.env` into the build: slow, and secrets and personal data could end up in the image | Phase 2, with the Dockerfile |
| T2 | Groq no longer lists Llama chat models for our key (2026-10-28: `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.8-27b`, `allam-2-7b`) | Data card §6 and the section 14 LLM question name options we can't use; Qwen's license is not in the card | Phase 2, when choosing the LLM |
| T3 | The same voice note sent twice is handled twice (no `file_unique_id` check) | Two SRs for one problem | Phase 3 |
| T4 | The bot's stop on Linux (SIGTERM) is not tested | Unclean stop in Docker | Phase 3, in Docker |
| T5 | Voice `reference.csv` uses compounds that are not in the registry (Cedar Park, Lotus Ridge, Nakhla Residence) and old labels (2 × `?`, 1 × `plumbing+electricity`) | The Phase 4 re-measure can't test the registry lookup | Phase 4, before re-measuring |
| T6 | All settings are optional; `require()` misses empty `POSTGRES_*` | A missing value fails late, with an unclear error | Phase 5 |
| T7 | GitHub Actions pinned by tag, not by commit SHA | A moved tag could run other code; low risk until the deploy step adds secrets | Phase 5 (CD step) |
| T8 | `av<19` (for faster-whisper 1.2.1); aiogram caps pydantic `<2.14` | We miss fixes in newer versions | When the upstream packages support them |
| T9 | No `README.md` (a brief deliverable: "Git repository with README and setup instructions") | The public repo has no front page; CLAUDE.md is not a README | Phase 6 |
| T10 | 311 rule `ELEVATOR` → `general, low`, but the test set labels "elevator broken" `medium` (Step 2.1 G3b: "something important doesn't work") | The classifier learns low from 311 and loses points on the test for it | Step 2.6, before training: rule → medium in `ml/label_mapping.py` + its test + the guide; re-run `prepare_311` |
| T11 | A database error still carries the refused row (name, phone) in its exception chain, and a wrong-type error carries the value itself, even in `str(error)`. Only our log formatter (it hides `DETAIL:` lines and `query argument $N:` values) and Postgres's `terse` log setting stop it (Step 2.2, privacy A; PR #3 M1) | A crash outside logging (an uncaught exception printed to stderr), another log handler, or an error text sent to the user would show the row | Phase 3: the repository turns `IntegrityError` into a short app error with only the rule's name (`raise … from None` cuts the chain); uncaught exceptions go through logging |
