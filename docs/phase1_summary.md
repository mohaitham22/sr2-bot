# Phase 1 summary: Foundations (weeks 1–2)

2026-10-28 · Momo (with Claude Code) · Gate: **scope freeze**

**In short:** the bot receives text and voice notes, the NYC 311 data is mapped to our labels,
Whisper was tested on Egyptian Arabic, and the database, fields and dashboard are designed.
Review on 2026-10-28: every Phase 1 check was run again, **15 of 17 tasks ✅, 2 ⚠️**
(see "Risks" and "Questions"). The scope is now frozen.

## What we built

| Part | Result |
|---|---|
| Setup | Python 3.12 + uv, Postgres 16 and Redis 7 in Docker, GitHub Actions CI (ruff + 102 tests, green) |
| Telegram bot | Polling bot: `/start` in English + Egyptian Arabic, text echo, voice notes saved for the test team only. Logs hold no message text and no token (checked live) |
| Whisper test | 15 voice notes (10 Egyptian Arabic, 5 English) × 4 local models + Groq: [report](../eval/reports/whisper_phase1.md) |
| Training data | NYC 311, housing (HPD), 1 year: 904,284 rows → 10% sample (90,405) → 79,544 labeled rows. Scripts re-run on 2026-10-28 gave byte-identical files |
| Labels | 8 categories + 3 urgency levels, written as rules in code and in the [labeling guide](labeling_guide.md) |
| Unit registry | 4 fictional compounds, 188 units (`B-204` style), made by a script with a fixed seed |
| Design | [Design notes](design_notes.md): the 6 required fields and their follow-up questions, 7 database tables (tested in Postgres), 5 dashboard charts |
| Data card | [Data card](data_card.md): every source, its terms, intended use and limits |

## Key decisions and why

| Brief | Our choice | Why |
|---|---|---|
| Azure OpenAI | Groq free tier (Gemini backup), behind one LLM client set by env vars | No paid services for the prototype; switching provider needs no code change |
| Whisper or Azure Speech | Self-hosted `faster-whisper` `large-v3`, int8, CPU | The brief asks for open-source, self-hosted; voice notes never leave our machine |
| Azure Container Apps | Oracle Cloud Always Free VM (Azure free grant as backup) | Free; final choice in Phase 5 |
| 6 categories | **8:** + `gas`, + `appliances` | A gas smell is a safety case that needs its own label; appliances are their own trade. **Needs your approval** |
| "Demoable in 4 weeks" (objectives) | The week-6 end-to-end gate (timeline) | The timeline is more detailed; please confirm |

Other rules we set: urgency depends only on the problem (not on who lives there or the season);
a unit must exist in the registry; the ticket number is `SR-YYYYMMDD-NNNN`; names, phones and
message texts never appear in logs, traces or the dashboard (Metabase reads a view without them).

## Whisper test results (10 Arabic notes, so each note = 10 points)

| Model | Usable Arabic | Arabic CER | Time per audio second (CPU, 4 threads) |
|---|---|---|---|
| `small` | 30% | 0.41 | 0.3 s |
| `medium` | 80% | 0.42 | 0.5–0.8 s |
| **`large-v3` (chosen)** | **80%** | **0.24** | 1.0–1.4 s |
| `large-v3-turbo` | 60% | 0.38 | 0.5–0.9 s |
| Groq `whisper-large-v3` (comparison only) | 80% | 0.40 | 0.03 s (cloud) |

"Usable" = the problem is clear and the compound, building and unit are right. All 52 Arabic
judgments were checked by a native speaker. **The target is 85%, so it is not met yet.** Our
answer (from the brief's own mitigation): the bot **always shows the transcript** of a voice note
and the user confirms or corrects it. Typical mistakes are one digit or a unit letter.

## Risks we found

| Risk | What we do |
|---|---|
| Arabic transcription below 85% | Transcript confirmation; re-measure in Phase 4; tuning ideas parked on the stretch list |
| 311 has no resident text, no AC cooling and no gas smell | Phase 2 synthetic messages, written "label first"; the hand-written test set shows the gap |
| Very unbalanced classes (gas 1.2%, AC 27%) and rule-based ("weak") urgency labels | Balanced synthetic data; report per-class results |
| `large-v3` is slow on CPU (about 21–28 s for a 25 s note) | Re-measure on the server in Phase 5; `medium` is the backup |
| Free tiers change: on 2026-10-28 Groq listed no Llama chat model for our key, although our plan named Llama as an option | All LLM calls behind one client; the model is a setting |

## Scope freeze

In scope = the brief + our logged decisions. New ideas go to a stretch list (11 ideas so far, e.g.
photos of the problem, a gas safety tip). An idea can enter only after the week-6 gate passes,
with your OK. Known weaknesses are listed with the phase that fixes them (9 items).
Both lists: `CLAUDE.md` sections 16 and 17.

## Questions for you

1. Do you approve **8 categories** instead of 6?
2. Is the F1 target of 0.85 **macro** (each class counts the same) or **weighted** (by class size)?
3. Is it OK that the repository is **public** (no Emaar data or brief inside)? Which license, if any?
4. May the test set be public, or should it stay private so nobody (and no future LLM) sees the answers?
5. Week 4 or week 6 for the first end-to-end demo?
