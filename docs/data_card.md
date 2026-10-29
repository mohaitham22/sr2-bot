# Data card

**Version 1.2 · 2026-10-29 · Step 2.1**

This card lists **every data source** of the project: where it comes from, its license or terms,
how it was made, what it may be used for, and what it does badly. The brief asks for it
("Data strategy": *"Every source and its license is recorded in a data card"*).

Read it like the label on a food package. Before you use a dataset, check here what is inside
and what it is not good for. The rules that turn a message into a category and an urgency are in
the [labeling guide](labeling_guide.md). The Whisper results are in the
[Whisper report](../eval/reports/whisper_phase1.md).

Every source has the same 8 parts: **Status · Source · Terms · How it was made ·
Size and columns · Where it is stored · Intended use · Not for**, then **Known limits and bias**.

---

## 1. Rules for all data

These rules come from the brief and from `CLAUDE.md` section 9. They apply to every source,
now and later.

1. **No internal Emaar data.** We use only public and synthetic data (brief: *"Use only public or
   synthetic data; no internal Emaar data is required"*). No real compound names, unit lists,
   complaints or documents from Emaar.
2. **No real resident data.** Every name, phone number, unit and compound in our own data is
   invented. Real residents first meet the bot in the live demo (Phase 6).
3. **Messages, transcripts and voice notes count as personal data**, even when the words are fake:
   a voice is personal, and a message can contain a name or a phone. They never go into git.
4. **Free LLM and speech APIs get fake data only.** Free tiers may use what we send for training.
5. **The test set is never used for training** or as an example in a prompt. The synthetic
   training data comes from a different model family than the test set: never Claude (section 8).
6. **A new source gets its section in this card before we use it.** If its terms are unclear, we
   don't use it.
7. **We keep only the columns we need** (data minimization). For example: no addresses from NYC 311.

---

## 2. All sources at a glance

| # | Source | Kind | Status | Terms | In git? | Used for |
|---|---|---|---|---|---|---|
| 3 | [NYC 311 housing complaints](#3-nyc-311-housing-complaints-hpd) | Public, real (city data) | ✅ in use (Steps 1.7–1.8) | NYC Open Data: no restrictions on use, no license attached, no warranty; name the source and version when we share | No (too big; scripts are in git) | Problem list, label mapping, training base |
| 4 | [Mock unit registry](#4-mock-unit-registry) | Synthetic (our script) | ✅ in use (Step 1.9) | Our own work; no license chosen yet | Yes, `app/db/seed/units.csv` | `units` table, unit checks, demo |
| 5 | [Test voice notes](#5-test-voice-notes) | Recorded by Momo, fake details | ✅ used once (Step 1.6) | Our own; not shared | No (personal data) | Whisper test only |
| 6 | [Synthetic requests](#6-synthetic-requests-planned) | Synthetic (LLM) | ⏳ planned (Phase 2) | Depends on the model's license and the provider's terms | To decide | Training the classifier |
| 7 | [Translated subset](#7-translated-subset-planned) | Synthetic (LLM translation) | ⏳ planned (Phase 2) | Same as source 6 | To decide | More training data in the other language |
| 8 | [AI-written test set](#8-ai-written-test-set) | Synthetic (Claude, chat); labels checked by Momo | ✅ frozen v1 (Step 2.1): 252 rows | Anthropic Consumer Terms: outputs are ours, not for training competing models; our labels: no license yet | No (D6 A: phone numbers) | The final scores only |

**Our own data has no license yet** (decision D3 A). The repo has no `LICENSE` file, which by
default means "all rights reserved": others may read it, but not reuse it. This is intern work for
Emaar, so the instructor decides if and how it is licensed.

---

## 3. NYC 311 housing complaints (HPD)

| Part | Details |
|---|---|
| **Status** | ✅ In use. Sampled in Step 1.7, labeled in Step 1.8 |
| **Source** | NYC Open Data, *"311 Service Requests from 2020 to Present"*, dataset ID `erm2-nwe9`, published by the NYC Office of Technology and Innovation (OTI), updated daily. <https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9/about_data> (2010–2019 is a separate dataset, `76ig-c548`, not used) |
| **Download** | A CSV export of **all rows**, by Momo on **2026-10-22**: 22,879,856 rows, 44 columns, 16,144,617,323 bytes (16.1 GB, or 15.0 GiB, so some older notes say "15.0 GB") |
| **Who is in it** | Complaints from New York residents to the city's 311 service (phone, app, web). The dataset description says it holds no personal data about the caller. We keep no addresses or coordinates |

### Terms

- **License field: empty.** The dataset's metadata (`/api/views/erm2-nwe9.json`, checked
  2026-10-28) has `license: null`, `attribution: "311"`, `provenance: "official"`.
- **The law behind NYC Open Data** (Local Law 11 of 2012, NYC Administrative Code, Title 23,
  Chapter 5; official text: <https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/>):
  - §23-504(a) ✅ (checked by Momo on the official site, 2026-10-28): *"Public data sets made
    available on the web portal are provided for informational purposes. The city does not
    warranty the completeness, accuracy, content or fitness for any particular purpose or use of
    any public data set made available on the web portal, nor are any such warranties to be
    implied or inferred with respect to the public data sets furnished therein."*
  - §23-502(d) ✅ (checked by Momo on the official site, 2026-10-28): *"Such public data sets shall
    be made available without any restrictions on their use provided that the department may
    require a third party providing to the public any public data set, or application utilizing
    such data set, to explicitly identify the source and version of the public data set, and a
    description of any modifications made to such public data set."* (The rest of (d) says that
    measures which keep the website working are not "restrictions".)
- **nyc.gov Terms of Use** (<https://www.nyc.gov/main/terms-of-use>, checked 2026-10-28): materials
  are given *"AS IS"* and *"AS AVAILABLE"*; use the site *"only for lawful purposes"*.
- **What this means for us:** we may download, change and share the data: the law allows any use,
  and the dataset has no license attached. There is **no guarantee** that it is correct, so we
  check it ourselves (the Step 1.7 notebook). When we share the data, or a report or app built on
  it, we name the source, the version and our changes: *"NYC Open Data, 311 Service Requests from
  2020 to Present (erm2-nwe9), export of 2026-10-22, filtered and relabeled by us (see the data
  card)"*.
- **Quote the official text only.** An unofficial copy of the code
  (<https://nyc-laws.readthedocs.io/en/latest/nycadmincode/t23/c05/>) still has an older §23-502(d)
  (*"without any registration requirement, license requirement or restrictions"*). The old NYC
  Open Data terms page no longer loads (404, or a redirect to a user guide without terms).

### How it was made

1. **By NYC.** A resident reports a problem to 311. HPD (Housing Preservation and Development, the
   city's housing agency) handles complaints about rented homes. Each complaint is one row. The
   problem is chosen from **fixed lists on 3 levels**: complaint type → descriptor → additional
   details, for example `WATER LEAK / HEAVY FLOW / AT WALL OR CEILING`. There is **no text
   written by the resident**.
2. **By us, Step 1.7** ([`ml/sample_311.py`](../ml/sample_311.py)). We kept rows with agency
   `HPD`, created from 2025-10-01 up to (not including) 2026-10-01, a 12-month window so that
   every season is in it. Of those, we kept the rows whose `unique_key` ends in `7` (about 10%),
   with a cap of 100,000 rows (not reached). The script also counts **all** 904,284 HPD rows of
   the window per problem group, so we can prove the sample looks like the whole: every complaint
   type is within 0.08 points.
3. **By us, Step 1.8** ([`ml/label_mapping.py`](../ml/label_mapping.py),
   [`ml/prepare_311.py`](../ml/prepare_311.py)). 75 rules give each of the 174 problem groups a
   category, an urgency and (for `ac`) a sub-label, or drop it with a reason. The labels come from
   rules, not from a person reading each row (**weak labels**). Details:
   [labeling guide §8](labeling_guide.md#8-how-the-nyc-311-data-was-mapped).

### Size and columns

| File | Rows | Columns | Size |
|---|---|---|---|
| The export (`ml/data/raw/311_Service_Requests_from_2020_to_Present_20261022.csv`) | 22,879,856 | 44 | 16.1 GB |
| `ml/data/raw/311_hpd_sample.csv` (Step 1.7) | 90,405 | 14 | 45.6 MB |
| `ml/data/raw/311_hpd_population_counts.csv` (Step 1.7) | 174 groups | 4 | 8 KB |
| `ml/data/processed/311_mapped.csv` (Step 1.8) | 79,544 | 8 | 6.9 MB |

- **The 14 columns we keep** (API names): `unique_key`, `created_date`, `closed_date`, `agency`,
  `complaint_type`, `descriptor`, `descriptor_2`, `location_type`, `incident_zip`, `borough`,
  `status`, `resolution_description`, `resolution_action_updated_date`, `open_data_channel_type`.
  The 3 problem levels (`complaint_type`, `descriptor`, `descriptor_2`) make the labels. The others
  are for exploring only. The other 30 columns (addresses, coordinates, council districts...) are
  never read.
- **`311_mapped.csv` columns:** `unique_key`, `created_date`, `complaint_type`, `descriptor`,
  `descriptor_2`, `category`, `urgency`, `subcategory`.
- **Key numbers** (the sample after Step 1.8; full tables in the labeling guide):
  - Kept 79,544 rows, dropped 10,861. Of the full year, 12.1% is dropped (two categories in one
    row, things that don't exist in Egypt, not maintenance).
  - Categories: `ac` 27.3% (97.7% of it heating), `plumbing` 23.2%, `general` 21.0%,
    `pest_control` 9.1%, `carpentry` 7.8%, `electricity` 7.0%, `appliances` 3.3%, `gas` 1.2%.
  - Urgency: `medium` 70.3%, `low` 20.6%, `high` 9.2%.

### Where it is stored

On Momo's laptop only, in `ml/data/raw/` and `ml/data/processed/`. Both folders are git-ignored:
the files are far bigger than GitHub's 100 MB limit, and the scripts in git are the recipe. To
build them again you need the same export and 2 commands:
`uv run python -m ml.sample_311` (about 3 min), then `uv run python -m ml.prepare_311` (about 2 s).

### Intended use

- Learn which housing problems exist and how often, and map them to our 8 categories and 3 urgency
  levels (done in Step 1.8).
- The model for the Phase 2 synthetic messages: which problems to write about and in what mix.
  The brief: *"LLM-generated synthetic requests modeled on the 311 data"*.
- Maybe training data for the baseline, as text built from the 3 problem levels (Phase 2 decides).

### Not for

- **Not the test set.** The final scores come only from the test set (section 8).
- **Not a picture of Egyptian compounds.** Its counts and seasons describe New York.
- **Not for finding people or buildings.** We removed addresses and coordinates; don't add them back.

### Known limits and bias

| Limit | Why it matters |
|---|---|
| **New York is not Egypt.** Old rented buildings with radiators, boilers and fire escapes, a cold winter. Egyptian compounds: owned units, split AC units, a hot summer | The mix of problems is different. Radiators, steam pipes, boilers and fire escapes were dropped as `not_in_egypt` (12,392 rows of the year) |
| **English only** | No Arabic, no Egyptian dialect, no Franco-Arabic ("el takyeef mesh shaghal") |
| **No resident text.** Only codes chosen from fixed lists | A model never sees real wording, typos, mixed languages or vague messages from this data |
| **Heat dominates.** The complaint type `HEAT/HOT WATER` is 39.7% of HPD rows; 97.7% of our `ac` rows are heating; **0 cooling rows** | A model trained on it learns "ac = heater". Fix: the Phase 2 AC mix of 70% cooling / 20% heating / 10% ventilation |
| **0 gas-smell rows.** Gas is 1.2%: 966 rows "cooking gas shut off" and 8 rows "no gas" at the cooker | Gas leaks in NYC are probably reported to the gas company or 911, not to HPD. Gas-smell messages must come from synthetic data |
| **Very unbalanced.** In the full year, the biggest complaint type is 308 times the smallest | Small classes (gas, appliances) are hard to learn. Report macro F1 next to the total |
| **Weak labels.** One label per problem group: every row in a group gets the same urgency | A real case may be worse or milder than its group's label. Urgency learned from 311 alone is rough |
| **Reporting bias.** Only problems that tenants report to the city | Problems people fix themselves, or report only to the landlord, are missing |
| **One year, one season mix.** 2025-10 to 2026-09 | Heat is seasonal (62% of January rows, 7% of August). Another window gives other shares |
| **The data changes every day** | A newer export differs a little (we saw 2 rows in 5 days). To rebuild exactly, use the same export |

---

## 4. Mock unit registry

| Part | Details |
|---|---|
| **Status** | ✅ In use. Made in Step 1.9 |
| **Source** | Made by us with [`app/db/seed/generate_units.py`](../app/db/seed/generate_units.py), seed 42. **100% fictional** |
| **Terms** | Our own work. No license chosen yet (D3 A, section 2) |

### How it was made

- **4 invented compounds**, each with an English and an Arabic name, because residents may write
  either: Olive Ridge / أوليف ريدج, Juniper Bay / جونيبر باي, Bostan El Nada / بستان الندى,
  Zahret El Loz / زهرة اللوز. Two English-style and two Arabic-style names, like real Egyptian
  compounds. A web check on 2026-10-27 found no compound with exactly these names.
- **Buildings A–F.** There is no P, because it sounds like B in Egyptian Arabic ("بي").
- **Random sizes in fixed ranges:** 3–6 buildings per compound, 3–6 floors, 2–4 apartments per
  floor. The seed is fixed, so every run on every machine makes the same file.
- **Unit number = building + floor + 2-digit apartment**: `B-204` = building B, floor 2,
  apartment 04 (the brief's example).
- **Checks before writing:** no duplicate (compound, building, unit), one Arabic name per compound
  and one compound per Arabic name, every unit inside its own building. If one check fails,
  nothing is written.

### Size and columns

- **188 units** in 16 buildings: Olive Ridge 30, Juniper Bay 30, Bostan El Nada 56,
  Zahret El Loz 72.
- **4 columns:** `compound_en`, `compound_ar`, `building`, `unit_number`. 8 KB, UTF-8 without BOM.

### Where it is stored

**In git**, in [`app/db/seed/units.csv`](../app/db/seed/units.csv). It is safe in a public repo
because it is fictional. It is made **only by the script**, never edited by hand. A golden-file
test (`tests/test_generate_units.py`) checks in CI that the committed CSV equals a fresh run.

### Intended use

- Fill the Postgres table `units` (Phase 2–3).
- Check the unit that the LLM extracts: does `B-204` exist in this compound?
- Offer returning users their saved unit: *"Is this for Unit B-204?"*
- The dashboard chart "top units and buildings", and the demo data (Phase 6).

### Not for

- **Not for training the classifier.** It has no problems in it, only addresses.
- **Not a model of any real compound** or of Emaar's numbering.

### Known limits and bias

| Limit | Why it matters |
|---|---|
| **Apartments only.** Floors start at 1; no villas, ground floors, duplexes or odd numbering; every floor of a building has the same number of apartments | Real units are messier. Extraction tests on this registry are easier than real life |
| **Small.** 188 units | Fine for a prototype; the dashboard's "top units" will have few units per building |
| **Letters that rhyme.** B, C, D, E sound alike in a voice note ("بي", "سي", "دي", "إي") | Phase 3 must normalize letters, and the summary confirmation catches mistakes |
| **Names may sound real.** A web search can't prove a name is unused. "Olive Ridge" is close to existing names such as "The Ridge" | Kept by Momo's choice; change it if a real compound with this name appears |
| **No residents yet.** The brief says "units and users"; this file has units only | Fake residents come with the Phase 6 demo data |
| **The voice notes use other compound names** (section 5) | They were recorded before the registry existed |

---

## 5. Test voice notes

| Part | Details |
|---|---|
| **Status** | ✅ Used once, for the Whisper test (Step 1.6, 2026-10-27). May be used again to re-measure Whisper (Phase 4) |
| **Source** | **15 voice notes recorded by Momo** (the project intern) on 2026-10-27, on one phone, sent to the bot. Momo also wrote `reference.csv`: what was said, and the expected compound, building, unit, name, phone and category |
| **Terms** | Our own recordings, not shared, no license. Momo is the only speaker and agreed to the uses in this section. **The voice is real personal data, even though every detail in it is fake** |

### How it was made

- Momo wrote short scripts **full of hard cases on purpose**: unit letters (B-204), a leading zero
  (C-015), self-corrections (12 → 14), phones said digit by digit, in pairs and with hundreds,
  English words inside Arabic and the other way round, a very short note, a note with no unit.
- **Every detail is fake:** names, compounds, units and phone numbers.
- The bot saved each note to `eval/voice/raw/` (Step 1.5), and only for the Telegram IDs in
  `VOICE_SAVE_USER_IDS`, so a stranger's voice can never get there.
- **Where the audio went:** transcribed on the laptop with `faster-whisper`, and **once sent to the
  Groq API** (cloud, free tier, `whisper-large-v3`) as a comparison. This was allowed only because
  the content is fake and the speaker agreed. Real residents' voice notes never leave our server
  (decision of 2026-10-25).

### Size and columns

- **15 OGG/Opus files, 1.3 MB:** 10 Egyptian Arabic + 5 English, 4.9–32.8 s each, **342 s in
  total**. Noise: 11 quiet, 2 street, 1 TV, 1 fan. 13 notes say a (fake) name, unit and phone.
- **`reference.csv` columns:** `id`, `file_name`, `language`, `noise`, `text`, `expected_compound`,
  `expected_building`, `expected_unit`, `expected_name`, `expected_phone`, `expected_category`,
  `notes`.
- **Made from them in Step 1.6:** `results.csv` (150 transcripts), `scores.csv`, `judgments.csv`,
  `review.md`.

### Where it is stored

On Momo's laptop only. The **whole folder `eval/voice/` is git-ignored** (Step 1.6 D12 A): audio,
reference texts, transcripts, scores and judgments. In git there are only the scripts and the
[Whisper report](../eval/reports/whisper_phase1.md), where phone numbers are masked.

### Intended use

- Measure speech-to-text on Egyptian Arabic and English (Step 1.6; the brief's top risk).
- Measure it again after changes (Phase 4: target ≥ 85% usable).

### Not for

- **Not for training** any model, and not as examples in a prompt.
- **Not for sharing** outside Momo's laptop, and never in git.

### Known limits and bias

| Limit | Why it matters |
|---|---|
| **One speaker, one phone, one place** | Other voices, dialects, ages and microphones may do worse. Our 80% may be too optimistic |
| **Very small.** 10 Arabic notes, so 1 note = 10 points | Differences of 10–20 points can be chance |
| **Read from a script, by someone who knew the hard cases** | Real residents speak more freely, with more pauses, fillers and background noise |
| **The labels came before the labeling guide.** `expected_category` was written before Step 1.8: 2 notes have `?`, 1 has `plumbing+electricity` | Re-label them with the guide before using them to test categories |
| **Other compound names.** Cedar Park, Lotus Ridge and Nakhla Residence are not in the registry (section 4) | Phase 3 tests of the registry check need new recordings, or a clear note that "not found" is the expected answer |
| **Judged partly by an AI.** 31 Arabic judgments of the large models are by Claude only, not yet reviewed by Momo | See the Whisper report, section 3 |

---

## 6. Synthetic requests (planned)

| Part | Details |
|---|---|
| **Status** | ⏳ Planned for Phase 2. Nothing generated yet |
| **Source** | An LLM writes messages that look like a resident's, in Egyptian Arabic and in English. The brief: *"LLM-generated synthetic requests modeled on the 311 data"* |
| **Terms** | Depend on **the model** and **the provider**. See below. Checked before we generate (rule 6) |

### Terms (checked 2026-10-28; read them again on the day we generate)

The text an LLM writes can come with rules. With an open model on Groq, **the model's license
applies too**: Groq's Terms of Use make the user responsible for following the model owner's terms.

| Model family | What its terms say about using outputs to train another model |
|---|---|
| **Llama 3.1 and newer** (e.g. Llama 3.3) | Allowed. But a model trained with Llama outputs that is *"distributed or made available"* must have a name that starts with *"Llama"*. Llama 2 and the first Llama 3 did **not** allow it ([license](https://www.llama.com/llama3_3/license/), [FAQ](https://www.llama.com/faq/)) |
| **gpt-oss** (OpenAI's open-weight models) | License Apache 2.0 ([model card](https://huggingface.co/openai/gpt-oss-120b)), which has no rule about outputs |
| **Gemini API, free tier** | *"You may not use the Services to develop models that compete with the Services"*. A small category classifier does not compete with Gemini. On the free tier Google may use prompts and responses to improve its products, and *"human reviewers may read, annotate, and process"* them ([terms](https://ai.google.dev/gemini-api/terms), last updated 2026-04-28) |
| **Groq** (the provider) | Each model has its own terms ([models](https://console.groq.com/docs/models)); the user must follow them ([Terms of Use](https://groq.com/terms-of-use)) |

These are summaries for planning, not legal advice. The exact model is chosen in Phase 2.

### How it will be made (plan from Steps 1.8 and earlier)

- **Label first** (decision D9 A): we choose the category, urgency, language and problem first,
  then the LLM writes a message that fits. The problems come from the 311 list and the seed lists
  in the [labeling guide §7](labeling_guide.md#7-seed-lists-for-phase-2-synthetic-messages).
- **AC mix:** 70% cooling, 20% heating, 10% ventilation.
- **Fake details only** in the messages (names, phones, units from the registry).
- **Varied style:** short and long, typos, Franco-Arabic, English words inside Arabic, vague messages.
- The prompt lives in a versioned file (`app/prompts/` or `ml/`, decided in Phase 2), never inline.

### To fill in when it exists

Model and version · provider · date · prompt file and version · settings (temperature) ·
generated / kept / dropped (and why) · counts per category, urgency and language ·
how many messages Momo checked by hand, and how many had a wrong label · where it is stored.

### Intended use

Training and validating the classifier (the TF-IDF baseline, then v2).

### Not for

- **Not for the final scores.** Those come from the test set (section 8).
- **Not as test data for the ML vs LLM comparison**, for the same reason.

### Known limits and bias (expected)

| Limit | Why it matters |
|---|---|
| **LLM style.** Too clean, too polite, too similar; Modern Standard Arabic instead of Egyptian | The classifier learns the LLM's style, not residents'. Scores on synthetic data look better than real life |
| **A message may not match its label.** We ask for "high" and the LLM writes a mild message | Label noise. Momo checks a random sample by hand |
| **Few patterns.** Many messages repeat the seed-list words | The model may learn the seed words only. Remove near-duplicates; ask for variety |
| **Circular comparison.** If the same LLM writes the training data and later classifies zero-shot, it may find its own style easy | Use a different model for each job, or say it in the model report |

---

## 7. Translated subset (planned)

| Part | Details |
|---|---|
| **Status** | ⏳ Planned for Phase 2. Nothing made yet |
| **Source** | Part of the synthetic messages (or of the 311-based texts), translated by an LLM into the other language: English → Egyptian Arabic, maybe Arabic → English. The brief: *"plus a translated subset"* |
| **Terms** | The same as section 6: the terms of the model that translates |

### How it will be made (plan)

- Take a part of the source messages, translate them, and **keep the original label**.
- Each translation keeps the **ID of its original**, so we can always find the pair.

### To fill in when it exists

Model and version · date · prompt file and version · how many, from which source · direction ·
how many Momo checked by hand, and how many had a meaning change.

### Intended use

More training data in the language that has less of it.

### Not for

The test set, and the final scores.

### Known limits and bias (expected)

| Limit | Why it matters |
|---|---|
| **Translationese.** Translated text reads like a translation (often MSA), not like a resident | Same as section 6: scores look better than real life |
| **The meaning may change.** "Dripping" can become "pouring", which changes the urgency | The label is no longer right. Momo checks a sample |
| **Leakage risk.** A message and its translation are almost the same message | If one is in training and the other in validation, the score is too high. Split by the original's ID (both go to the same side) |

---

## 8. AI-written test set

| Part | Details |
|---|---|
| **Status** | ✅ **Frozen as v1** on 2026-10-29 (Step 2.1): 252 rows, SHA-256 `786e72ad2179f88b3d1c9418dd84038154bfae39c4da18c819db9d18754ecbcc` (by `eval/check_test_set.py`, line ends read as LF; 0 problems). Any later change gets a new version and hash in `CLAUDE.md` section 13, and every score names the version it used |
| **Source** | 252 requests written by **Claude** (Anthropic), in the claude.ai chat, on 2026-10-29, `author = ai`: T001–T222 first, then T223–T252 (15 `gas` + 15 `appliances`) from the prompt [`docs/prompts/test_set_extra_rows.md`](prompts/test_set_extra_rows.md). Momo decided every label change. ⚠️ The brief says the test set is *"written and labeled by the interns themselves"*: Momo changed this (Step 2.1); instructor approval pending |
| **Terms** | [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (effective 2025-10-08, read 2026-10-29): Anthropic assigns the outputs to the user (§4); the services may not be used *"to develop or train any artificial intelligence or machine learning algorithms or models"* that compete with them (§3). We only **measure** with these messages, never train on them (rule 5). Anthropic may train on chat inputs and outputs unless the user opts out (§4): our prompts held only our rules and invented data. Our own work on top (labels, fixes): no license chosen yet (D3 A, section 2) |

### How it was made (Step 2.1)

1. **Written** by Claude (chat) **without** our labeling guide or registry: 222 rows, with tags for
   hard cases (Franco-Arabic, Arabic digits, typos, two problems, vague, …). The untouched file is
   kept as `eval/test_set_original.csv`.
2. **Checked by a script:** `eval/check_test_set.py` checks the columns, labels and tags, the clean
   form of every expected field (design notes §1), the registry, and that every expected value
   appears in the text. First run: 501 problems in 189 rows.
3. **Labels reviewed** against the [labeling guide](labeling_guide.md): proposed by Claude Code,
   decided by Momo. 43 rows changed: 39 labels broke the guide (18%), plus 2 dripping-tap rows,
   1 tag and 1 row too vague for a label. The guide became v1.2 (4 cases made clear).
4. **Fitted to the registry** (D2, D3): the 3 invented compounds → our 4; building numbers →
   letters; every unit → a real registry unit (112 of 150 didn't exist). Only location words
   changed (167 rows), listed before/after in `eval/test_set_review.md` and read by Momo.
   Phones → E.164 in the `phone` column (D4).
5. **Realism review:** Momo read 30 random rows (seed 42) and marked none.
6. **30 rows added** (D1 A): `gas` had 3 rows, `appliances` 0. Claude (chat) wrote 15 + 15 from a
   prompt with our rules (no test message); all passed the checker and the label review the first time.

### Size and columns

252 rows, 12 columns: `id, text, language, category, urgency, compound, building, unit_number,
name, phone, author, notes`. The expected fields are the clean values the bot should extract;
**empty = not in the text**, so a value returned for an empty field is a hallucination.

| | Counts |
|---|---|
| Category | electricity 48, plumbing 46, ac 36, carpentry 30, pest_control 30, general 28, gas 18, appliances 15, none 1 (too vague, D5 A) |
| Urgency | low 86, medium 117, high 48, none 1 |
| Language | Egyptian Arabic 138 (21 of them Franco-Arabic), English 77, mixed 37 |
| Tags | short_compound 53, arabic_digits 48, franco 21, gas 18, check_guide 17, very_short 15, long 9, two_problems 8, typo 7, self_correction 6, vague 6, water_heater 3 |
| Expected fields | full location (compound + building + unit) 99, unit 164, building 159, compound 131, phone 77, name 60, none at all 34 |

### Where it is stored

`eval/test_set.csv` on Momo's laptop, **not in git** (D6 A): its invented phone numbers may belong
to real people. Next to it, also git-ignored: the untouched original, the 30 extra rows as sent
(`test_set_extra.csv`) and the location review. Momo keeps a backup and sends the file to the
instructor directly. The checker and its tests are in git.

### Intended use

The **final scores only**: classifier F1 (target ≥ 0.85), the ML vs LLM comparison, and the
extraction checks (all unit fields ≥ 90%, hallucination rate). Every score says "on an AI-written
test set".

### Not for

**Never for training, never as an example in a prompt, never for tuning** (rule 5, `CLAUDE.md`
section 9): choices are made on the validation set. If a test message is used for training even
once, every score after that is too high.

### Known limits and bias

| Limit | Why it matters | What we do |
|---|---|---|
| **AI-written**, not by residents or interns | It may share the "AI style" of the synthetic training data, so the scores look better than real life | Training data from a different model family (never Claude); the Step 2.6 leakage check; "AI-written" next to every score; optional: 20–40 messages by real people, scored apart |
| **One shape repeats**: problem → location → phone, at the end; few greetings (realism review) | Real residents mix the order and send details in several messages, so extraction may look easier than real life | Say it in the reports; the 30 extra rows vary the shape |
| **Written and reviewed by one model family**: Claude (chat) wrote it; Claude Code proposed the label and location fixes | Shared blind spots | Momo decided every change and read 30 random rows |
| **Claude Code has read every row** | Its Step 2.6 prompt drafts may reuse test wording | The leakage check; Momo reviews the Step 2.6 prompts |
| **One labeler** | No second opinion on borderline labels | Open (`CLAUDE.md` section 14): a second person labels a part, and we measure agreement |
| **Small classes**: appliances 15, gas 18 | One mistake moves their F1 a lot | Report every class, macro and weighted F1, and a confidence interval (Step 2.7) |
| **Empty or rare pairs**: `ac` + `high` and `appliances` + `high` have 0 rows (by the guide, a device is never the danger); `carpentry` + `high` and `pest_control` + `high` have 2 each | The test says little about these pairs | Expected from the guide (D8 A); say it in the model report |
| **Some pairs of rows** tell the same problem in two languages (for example T110 / T111) | They are not fully independent samples | A small effect; say it |

---

## 9. Gaps and bias: what the final report must say

None of our data is a real resident message. This table collects the gaps from the sections
above, so that the model report (Phase 4–5) and the final report can measure each one and explain
it. The brief's risk: *"Synthetic data doesn't reflect real requests"*. Mitigation: *"Hand-written
test set; report the gap between synthetic and real-style performance."*

| Gap | What it can do to the results | What we do about it | Where we measure or report it |
|---|---|---|---|
| **No real resident messages** anywhere | All scores describe "resident-style" text, not real residents. The test set is AI-written too (section 8), so the brief's "gap" is only partly measured | Compare scores on synthetic vs test data (the brief's "gap"); optional: 20–40 messages by real people, scored apart | Model report |
| **NYC is not Egypt**; heat-heavy, no cooling, no gas smell (section 3) | The classifier mixes up AC types, and misses gas | Seed lists; 70/20/10 AC mix; test set has gas and cooling cases | Score per category (Phase 4) |
| **English-only 311; Arabic only from an LLM** (sections 3, 6, 7) | Weaker on real Egyptian Arabic | Momo checks Arabic samples; separate scores per language | Model report |
| **The test set and the training data are both AI-written** (sections 6, 8) | Scores too optimistic | Different model families (Claude vs Groq / Gemini); the Step 2.6 leakage check; Momo reviews the generation prompts | Model report, limits |
| **Weak urgency labels** (section 3) | Urgency less reliable than category | Test-set labels checked against the guide, decided by Momo (section 8) | Separate urgency scores |
| **Unbalanced classes** (gas 1.2%) | Small classes are weak, hidden by a good total | Report every class, and macro and weighted F1 | Model report |
| **LLM writes the data and is also the zero-shot rival** (section 6) | The ML vs LLM comparison is not fair | Different models, or say it clearly | ML vs LLM comparison |
| **One speaker for the voice notes** (section 5) | Transcription scores too optimistic | The bot always shows the transcript (D11 A) | Whisper report; final report |
| **Simple unit numbering** (section 4) | Extraction looks easier than real life | Say it; add odd cases to the test set if time allows | Final report |

---

## 10. How to keep this card up to date

1. **A new source:** add a row to section 2 and a section with the same 8 parts, **before** you
   use it. If its terms are unclear, don't use it.
2. **A planned source becomes real:** fill in its "To fill in" list, change its status, and move
   the "expected" limits to measured ones.
3. **A script runs again with other settings:** update the numbers in this card.
4. **Each change:** add a line to the change log below, and log the decision in `CLAUDE.md`
   section 13.
5. **Phase 6:** read the whole card once more. It is one of the brief's deliverables.

## 11. Change log

| Version | Date | Change |
|---|---|---|
| 1 | 2026-10-28 | First version (Step 1.10): 3 sources in use (NYC 311, unit registry, voice notes), 3 planned (synthetic, translated, test set) |
| 1.1 | 2026-10-28 | §3 terms checked by Momo on the official site: §23-504(a) and §23-502(d), full quotes. The unofficial copy had an older §23-502(d) ("registration requirement, license requirement"); fixed. Added the city's right to ask for source, version and changes, so we now name them when we share |
| 1.2 | 2026-10-29 | Step 2.1: §8 is now the AI-written test set (252 rows by Claude chat; how it was checked and fixed; counts; Anthropic terms read on the official page; limits measured). Rule 5 adds "a different model family". §2, §3 and §9 follow. Same day: the test set is frozen as v1 (252 rows, hash in §8) |
