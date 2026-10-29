# Prompt: 30 extra test-set rows (gas + appliances)

**Step 2.1, decision D1 A.** The first 222 rows of `eval/test_set.csv` had no `gas` rows (only 3 after the
label review) and no `appliances` rows, so these two classes couldn't be measured. Claude (chat) writes
30 more rows with this prompt, in a **new** chat. Save the answer as `eval/test_set_extra.csv`
(git-ignored); Claude Code appends it and runs `eval/check_test_set.py`.

The prompt holds our rules (labeling guide v1.2, design notes §1, the registry), not any test message.

---

You are helping me build a **test set** for a maintenance-request bot used by residents of 4 fictional
residential compounds in Egypt. Write **30 new messages** a resident could send to the bot, each with its
correct labels and expected fields. All names and numbers are invented.

## What to write
- **15 `gas` rows:** 8 `high`, 5 `medium`, 2 `low`.
- **15 `appliances` rows:** 9 `medium`, 6 `low`, 0 `high`.
- **Language mix, for each group of 15:** 8 Egyptian Arabic (`ar`; 2 of them Franco-Arabic, Arabic written in
  Latin letters and digits like `3ayez`, `7aga`), 4 English (`en`), 3 mixed Arabic + English (`mixed`).
- **Style mix over all 30:** about 6 with Arabic-Indic digits (٠١٢), 2 with typos, 3 very short (2-4 words),
  2 long (3+ sentences with details), 2 with two problems in one message (see rule 4).
- **Vary the shape.** Real messages don't always end with "problem. location. phone". Sometimes start with a
  greeting (السلام عليكم، صباح الخير، hi), sometimes give the unit first, sometimes put it in the middle,
  sometimes no location at all.

## Labels (our labeling guide, v1.2)
1. **`gas`** = the gas supply: gas smell, gas leak, a hissing gas pipe, no gas in the flat, gas that doesn't
   reach the cooker, the gas pipe, valve or meter.
   - `high`: any gas smell or leak, even if it "went away"; a hissing sound from the gas pipe.
   - `medium`: no gas in the flat; no gas reaches the cooker (no smell).
   - `low`: a small problem with the gas pipe, valve or meter that doesn't stop the gas and has no smell
     (for example, the valve handle is stiff, the meter cover is broken).
2. **`appliances`** = devices in the unit: fridge, cooker (stove) and oven, microwave, washing machine,
   dishwasher, portable heater.
   - `medium`: the device doesn't work (the fridge doesn't cool, the oven doesn't heat, the washing machine
     doesn't drain or spin, the dishwasher doesn't start).
   - `low`: something small; the device still works (a cooker knob is broken, the fridge light is off, the
     oven door handle is loose, the washing machine is noisy but works).
3. **Not in these two categories** (don't write these): the AC (`ac`), the water heater (`plumbing`, even a
   gas one), sparks, smoke or a burning smell from any device (`electricity`), water flooding the flat
   (`plumbing`). Only the problem decides the urgency: a baby, an old person or the season change nothing.
4. **Two problems in one message:** the category of the most urgent problem; the highest urgency; if both are
   equally urgent, the problem mentioned first. Write one gas row like "the tap drips and there's a gas
   smell" (`gas`, `high`) and one appliances row with a second problem of the same urgency mentioned later
   (for example "the fridge doesn't cool, and a kitchen cabinet door is loose" is `appliances`, `medium`).

## The unit registry (use only these units)
| Compound (English / Arabic) | Short forms residents use | Buildings: floors x apartments |
|---|---|---|
| Olive Ridge / أوليف ريدج | Olive, أوليف | A: 1-3 x 01-04 · B: 1-5 x 01-02 · C: 1-4 x 01-02 |
| Juniper Bay / جونيبر باي | Juniper, جونيبر | A: 1-3 x 01-04 · B: 1-6 x 01-02 · C: 1-3 x 01-02 |
| Bostan El Nada / بستان الندى | Bostan, البستان | A: 1-4 x 01-04 · B: 1-3 x 01-04 · C: 1-4 x 01-04 · D: 1-6 x 01-02 |
| Zahret El Loz / زهرة اللوز | Zahret, الزهرة | A: 1-5 x 01-02 · B: 1-4 x 01-04 · C: 1-6 x 01-03 · D: 1-5 x 01-02 · E: 1-4 x 01-03 · F: 1-3 x 01-02 |

A unit number is the building letter + floor + apartment: `B-204` = building B, floor 2, apartment 04.
Example: Olive Ridge B has floors 1-5 and apartments 01-02, so B-101, B-102, ..., B-502 exist, and B-204 does not.
Buildings are letters, never numbers. How residents write them: `B-204`, `b204`, `B 204`, `بي ٢٠٤`,
`عمارة بي شقة 204`, `عمارة ب`, `building B`, `bldg B`, `3emara B` (Franco). Spoken letters: A إيه, B بي,
C سي, D دي, E إي, F إف. Arabic letters after عمارة: أ = A, ب = B, ج = C, د = D, هـ = E.
A building letter must come right before the unit's digits or right after a building word
(عمارة / بلوك / building / bldg / block / 3emara).

## Columns and expected fields
CSV columns: `id,text,language,category,urgency,compound,building,unit_number,name,phone,author,notes`
- `id`: T223 to T252, in order.
- `compound`, `building`, `unit_number`, `name`, `phone`: what the bot should extract, in clean form.
  **Empty = not in the text. Never fill a value the text doesn't contain.**
  - `compound`: the English registry name (`Olive Ridge`), even if the text says أوليف.
  - `building`: one letter. If the unit has a letter, `building` = that letter (`B-204` -> `B`).
  - `unit_number`: `B-204`. Only if the text gives 3 digits and no building at all: just the digits (`204`).
  - `name`: a full name (2 words), written exactly as in the text.
  - `phone`: an Egyptian mobile (010, 011, 012 or 015 + 8 digits), written in the text in any way
    (`010 1234 5678`, `+20 10…`, `٠١٠…`), and in this column as `+201XXXXXXXXX`.
- About half the rows have no location at all; about a third have a name or a phone.
- `author`: `ai`.
- `notes`: tags separated by `;`, only from: `franco`, `arabic_digits`, `short_compound`, `typo`,
  `very_short`, `long`, `self_correction`, `two_problems`, `vague`, `gas`, `water_heater`, `check_guide`.
  Every gas row gets `gas`. `arabic_digits` if and only if the text has Arabic-Indic digits.
  `short_compound` if the text uses a short form. `check_guide` for the two-problem rows.

## Output
Only the 30 CSV rows, no header, in one code block. Put `text` in double quotes if it has a comma.
