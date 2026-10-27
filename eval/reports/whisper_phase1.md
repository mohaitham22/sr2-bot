# Whisper test on Egyptian Arabic (Step 1.6, Phase 1)

Date: 2026-10-27 · Author: Momo (with Claude Code) · Risk from the brief: "Egyptian Arabic voice
transcription is weak. Mitigation: test Whisper sizes early (week 2); fall back to asking the user
to confirm the transcript."

## 1. Answer in short

- **Not quite good enough yet.** The best result is **80% usable** on the Arabic notes (8 of 10).
  The brief's target is **85%**. Three models tie at 80%: local `medium`, local `large-v3` and
  Groq's `whisper-large-v3`.
- **Chosen model: local `large-v3`** (int8, CPU) (decision D10 A). It was the only local model that
  understood the problem in **every** note, and it had the lowest character error rate. It is
  slow: about **21–28 s for a 25 s voice note** on 4 laptop CPU threads.
- **Fallback: the bot always shows the transcript of a voice note** and asks the user to confirm
  or correct it (decision D11 A). The mistakes we found are quick for a person to spot.
- **Small sample:** each Arabic note = **10 points**. Differences of 10–20 points can be noise.

## 2. How we tested

| Item | Details |
|---|---|
| Voice notes | 15, recorded by Momo through the bot: **10 Egyptian Arabic, 5 English**, 4.9–32.8 s each, **342 s in total**. 4 with background noise (TV, street, fan). Fake names, units and phone numbers only |
| Hard cases on purpose | unit letters (B-204), a leading zero (C-015), self-corrections (12 → 14, A-118 → A-181), phones said digit by digit, in pairs and with hundreds, English words inside Arabic, Arabic words inside English, a very short note, a note with no unit |
| Reference | `eval/voice/reference.csv`: what was said, plus the expected compound, building, unit and phone |
| Local engine | `faster-whisper` 1.2.1 (CTranslate2 4.8.4), **int8**, CPU, **4 threads** (like a 4-core server), default decoding (beam 5, no VAD, no prompt). One warm-up run per model, not counted |
| Models | `small`, `medium`, `large-v3`, `large-v3-turbo` |
| Cloud comparison | Groq API, `whisper-large-v3` (comparison only; never used in the app, section 13) |
| Language settings | `auto` (Whisper detects the language) and `set` (the language from `reference.csv`) |
| Laptop | Intel i7-11800H (8 cores), 16 GB RAM, Windows 11 |
| Total | 150 transcripts (5 engines/models × 2 settings × 15 notes), 78 different texts |

Scripts: `eval/whisper_test.py` (transcribe → `results.csv`) and `eval/score_whisper.py`
(score → `scores.csv`, `review.md` and the summary). The voice notes and all CSV files stay on the
laptop (git-ignored, decision D12 A).

## 3. How we scored

- **Usable for extraction (rule D3 B):** the problem is clear, **and** the compound, building and
  unit are right (when the note said them). A number counts as right in digits or in words; small
  spelling differences in the compound name are fine if a person would recognize it. **The phone
  is scored apart** (all 11 digits right). Names are not scored.
- **Who judged:** Claude judged every different transcript first, with a written reason
  (`eval/voice/judgments.csv`). Momo reviewed the 21 Arabic judgments of `small` and `medium` and
  changed 2 of them. ⚠️ The **31 Arabic judgments of `large-v3`, turbo and Groq are by Claude only**
  (not reviewed by Momo yet). Rule used for borderline cases: a unit letter written as "ب" stuck to
  the number ("شقة بمية وعشرة") counts as B-110 (Momo approved this rule on V07 `small`).
- **WER / CER:** word and character error rate after a light normalization (tashkeel removed;
  أ إ آ → ا, ة → ه, ى → ي; ٠-٩ → 0-9; punctuation removed). See section 9 for why WER is too
  pessimistic here.
- **"Unit digits found":** a strict automatic check: do the unit's digits appear in the transcript?
  Numbers written as words do not count, so it is lower than the judged result.

## 4. Results

| Engine / model | Language | **Usable ar** | Usable en | Problem clear ar | Phone exact | WER ar | WER en | CER ar | Language right |
|---|---|---|---|---|---|---|---|---|---|
| local small | set | 30% | 4/5 | 9/10 | 6/13 | 0.72 | 0.35 | 0.43 | (given) |
| local small | auto | 30% | 4/5 | 9/10 | 6/13 | 0.71 | 0.36 | 0.41 | 14/15 |
| local medium | set | **80%** | 4/5 | 9/10 | 9/13 | 0.63 | 0.33 | 0.42 | (given) |
| local medium | auto | **80%** | 3/5 | 9/10 | 9/13 | 0.63 | 0.58 | 0.42 | 13/15 |
| **local large-v3** | set | **80%** | 4/5 | **10/10** | 8/13 | **0.44** | **0.24** | **0.24** | (given) |
| **local large-v3** | auto | **80%** | 4/5 | **10/10** | 8/13 | **0.44** | **0.24** | **0.24** | 15/15 |
| local large-v3-turbo | set | 60% | 4/5 | 8/10 | 7/13 | 0.62 | 0.29 | 0.39 | (given) |
| local large-v3-turbo | auto | 60% | 4/5 | 9/10 | 7/13 | 0.61 | 0.29 | 0.38 | 15/15 |
| Groq whisper-large-v3 | set | **80%** | 4/5 | **10/10** | 8/13 | 0.59 | 0.29 | 0.40 | (given) |
| Groq whisper-large-v3 | auto | **80%** | 4/5 | **10/10** | 8/13 | 0.59 | 0.29 | 0.40 | 15/15 |

Phone: 13 notes include a phone number. Usable en: 5 English notes.

**Per note** (language `set`; ✗ = not usable, and why):

| Note | small | medium | large-v3 | turbo | Groq |
|---|---|---|---|---|---|
| V01 ar | ✗ unit | ✓ | ✓ | ✓ | ✓ |
| V02 ar (fast speech) | ✗ compound, unit | ✗ compound, unit | ✗ compound, unit | ✗ compound | ✗ compound |
| V03 ar (code-switching) | ✗ unit | ✓ | ✓ | ✓ | ✓ |
| V04 ar | ✓ | ✓ | ✓ | ✓ | ✓ |
| V05 ar | ✗ compound, unit | ✓ | ✓ | ✓ | ✓ |
| V06 ar (TV noise) | ✗ compound | ✓ | ✗ unit | ✗ problem, unit | ✗ unit |
| V07 ar (street, gas) | ✓ | ✗ **problem (gas lost)**, unit | ✓ | ✗ **problem (sentence dropped)**, unit | ✓ |
| V08 ar | ✗ unit | ✓ | ✓ | ✓ | ✓ |
| V09 ar (very short) | ✗ problem | ✓ | ✓ | ✓ | ✓ |
| V10 ar (fan, self-correction) | ✓ | ✓ | ✓ | ✗ unit | ✓ |
| V11 en | ✗ unit | ✗ unit | ✗ unit | ✗ unit | ✗ unit |
| V12–V15 en | ✓ | ✓ | ✓ | ✓ | ✓ |

## 5. Speed on the CPU (4 threads, int8)

RTF (real-time factor) = time to transcribe ÷ length of the audio. Below 1 is faster than real time.

| Model | Download | RTF median (set / auto) | **A 25 s note takes** (set / auto) | All 15 notes (342 s of audio), set / auto |
|---|---|---|---|---|
| small | 0.49 GB | 0.19 / 0.27 | 5 s / 7 s | 94 s / 105 s |
| medium | 1.53 GB | 0.44 / 0.62 | 11 s / 16 s | 158 s / 232 s |
| **large-v3** | 3.09 GB | 0.82 / 1.12 | **21 s / 28 s** | 298 s / 410 s |
| large-v3-turbo | 1.62 GB | 0.41 / 0.70 | 10 s / 18 s | 155 s / 253 s |
| Groq (cloud) | none | 0.03 / 0.03 | about 1 s | 9 s / 10 s (+ waits, see section 6) |

- **Auto-detect costs time:** Whisper runs the encoder an extra time to guess the language
  (about +35–45% for large-v3).
- **Short notes are slow per second of audio:** the 4.9 s note had RTF up to 3.5 (fixed costs).
- **Temperature fallback** (the model retries a hard part with more randomness) made some notes
  much slower, e.g. RTF 1.24 for one note on `small`.
- RAM use was not measured. The laptop CPU is not the server CPU: **re-measure on the server
  (Phase 5).**

## 6. Self-hosted vs Groq

| | Local large-v3 | Groq whisper-large-v3 |
|---|---|---|
| Usable ar / problem clear | 80% / 10 of 10 | 80% / 10 of 10 |
| CER ar | **0.24** | 0.40 |
| Speed (25 s note) | 21–28 s | **about 1 s** |
| Style | keeps Egyptian words; numbers as words like the speaker | often **rewrites into MSA** (لدينا، نحتاج الى احد يأتي) and once added a negation (لا يوجد شيء) |
| Privacy | audio never leaves our machine | audio goes to a cloud API (free tier) → fake data only, never residents (section 9) |
| Limits | none | **20 requests per minute**: after 20 calls every call got HTTP 429 with `retry-after: 3`; our retry waited 3 s and every call then worked (10 waits, no lost rows) |

Same model weights, different text: Groq probably uses other decoding settings. Groq is 30×
faster, but it is not allowed for real voice notes (decision of 2026-10-25).

## 7. Which setting worked best

- **Language:** `large-v3`, turbo and Groq detected the language right in **15/15** notes, so
  `auto` gave the same text as `set`, only slower. `medium` detected 2 English notes as Arabic and
  **translated them into MSA** (a toilet became "طاولة", a table). `small` missed 1.
- **Warning: `set` is too optimistic.** It used the language from `reference.csv`, which the real
  bot will not know when a voice note arrives (*oracle information*). The realistic numbers are the
  `auto` rows. How the bot gets the language (auto-detect, or a hint) is an open decision for
  Phase 2.
- **Size:** `small` is not usable for Egyptian Arabic. `medium` and `large-v3` are equal on
  "usable", but `large-v3` never lost the problem and makes fewer, less dangerous mistakes.
  `large-v3-turbo` is as fast as `medium` but worse: it dropped a whole sentence and once
  hallucinated.

## 8. Common mistakes

| Mistake | Example (fake data; phones masked) | Models |
|---|---|---|
| Unit letter wrong or unclear | "unit B 305" → "AB305", "AP-305"; "A-112" → "A122" | all on V11 (Momo checked the audio: "B") |
| Arabic number order | "ستة وأربعين" (46) → **64**, or → "ستة وعشرين" (26) | small; large-v3; Groq |
| Number heard like a year | "ninety, sixteen" → **19 16** / "1916" | all 5 (Momo checked: "ninety") |
| Extra or missing phone digit | "four five six" → "four **six** five six" (confidence 0.98–1.00); the first "صفر" lost in TV noise | large models; most models |
| English compound name in fast Arabic | "ساكنة في لوتس ريدج" → "ساكنة **فلوت الساب ريج**" | all 5 on V02 |
| A common phrase replaces the sound | "دي أربعمية وواحد" → "دي **أبو أمية** 1" | large-v3, turbo, Groq (TV noise) |
| Auto-detect translates | English note → MSA Arabic text | medium (2 notes) |
| **The key word lost** | "ريحة غاز" (gas smell) lost; turbo dropped the whole first sentence | medium; turbo (V07) |
| Hallucination | "مرحبا، مرحبا، مرحبا، مرحبا" instead of the first sentence | turbo `set` (V06) |
| Rewriting into MSA | "عندنا" → "نحن لدينا" | small; Groq |
| Nonsense after temperature fallback | a Chinese word inside Arabic text | small (V05) |

**What worked well:** self-corrections were kept ("12… لا لا، 14", "A118 no sorry I mean A181");
English notes were mostly fine; `large-v3` wrote Egyptian words as spoken; phones said digit by
digit were usually right.

## 9. Limits of this test

1. **10 Arabic notes, one speaker, one phone microphone.** One note = 10 points.
2. **`set` used oracle information** (section 7).
3. **WER is too pessimistic** and should not be compared with other studies: the reference writes
   numbers as words while some models write digits; models write fillers ("اه") that the reference
   leaves out; and some reference texts miss words that were really said (all models agree on
   extra words in V02, V07 and V10). "Usable %" is judged by meaning, so it is not affected.
4. **31 Arabic judgments (large models) are not reviewed by Momo yet** (section 3).
5. RAM use, float32 and the server CPU were not measured.
6. Workaround: `faster-whisper` 1.2.1 does not work with `av` 19 (`av.open()` lost the
   `metadata_errors` argument), so `pyproject.toml` limits `av<19` (decision D7 A).

## 10. Decisions (Momo)

| ID | Decision | Why |
|---|---|---|
| D10 A | STT model: local **`large-v3`**, int8, CPU. Backup: `medium` if the server is too slow | Never lost the problem, best CER, 15/15 language detection. Same "usable" as `medium`, but `medium` lost the word "gas" in an emergency note |
| D11 A | **Always show the transcript** of a voice note and ask the user to confirm or correct it, before extraction | No model reached 85%; the typical mistakes (a unit letter, one digit, a lost word) take a person seconds to spot |

## 11. Ideas not tested (for the stretch list)

- **Scoring:** turn number words into digits on both sides, remove fillers, fix reference texts
  by listening. This makes WER honest; it does not change "usable %".
- **Tuning `large-v3`:** `vad_filter=True` (may stop hallucinations); an `initial_prompt` with the
  compound names from the mock registry (it must contain no answers from these test notes; Whisper
  may also copy prompt words into the transcript); `float32` vs `int8`; forcing `ar` for everyone
  (to measure what happens to English notes). Groq's `prompt` parameter, too.
- **Word confidence** as a signal for "only confirm unsure transcripts" (D11 B, Phase 4). It
  helps sometimes (the lost "صفر" had confidence 0.33 and 0.21), but not always (the extra "six"
  had 0.98–1.00).
- **Egyptian fine-tuned Whisper:** `MAdel121/whisper-medium-egy` was checked (model card only,
  nothing downloaded): it is a SpeechBrain checkpoint saved in the middle of training, not a
  Transformers model; the card is an unfinished template; its training dataset has no license.
  Not usable as published. Other fine-tunes were not searched.
- **Cohere Transcribe Arabic:** not checked.

## 12. How to run it again

The voice notes and `reference.csv` are git-ignored, so this works only on Momo's laptop.

```bash
uv run python -m eval.whisper_test                    # all local models, then Groq (needs GROQ_API_KEY)
uv run python -m eval.whisper_test --engine local --models small   # one model only
uv run python -m eval.score_whisper                   # scores.csv, review.md and the summary table
```
