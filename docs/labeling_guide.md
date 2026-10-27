# Labeling guide

**Version 1 · 2026-10-27 · Step 1.8**

This guide says how to give one maintenance message its **category** and **urgency**.
Everyone who labels uses it: the person writing and labeling the test set (`eval/test_set.csv`,
Phase 2), the prompt that writes synthetic messages (Phase 2), and anyone who reviews a label.

The same rules, as code, are in [`ml/label_mapping.py`](../ml/label_mapping.py). That file maps
the NYC 311 data (section 8). If you change a rule, change both, and follow section 9.

**Why write the rules down?** Without written rules, two people (or one person on two days)
label the same message differently. The model then sees the same words with two labels and
learns noise. Written rules keep every label consistent: yours, a reviewer's, and the LLM's.

---

## 1. How to label one message

1. Read the whole message. Find the problem. One problem can have several parts ("the pipe under
   the sink leaks and the floor is wet" is **one** leak).
2. Choose the **category** (section 2). If more than one fits, use the order in section 3.
3. Choose the **urgency** (section 4).
4. If the message has **two different problems**, use section 5.
5. Check the edge cases (section 6) when you are not sure.

Label the message, not what you guess happened. Use only what the message says.

---

## 2. Categories (8)

The brief lists 6 categories. `gas` and `appliances` were added in Step 1.8 (decision D5/D6 B).

| Category | It covers | It does NOT cover (goes to) |
|---|---|---|
| `plumbing` | Water and drains: pipes, leaks, taps, sinks, toilets, showers, bathtubs, no water, low pressure, no hot water, the water heater, sewage, blocked drains, sprinklers | Water touching electricity (`electricity`). Water dripping from the AC (`ac`) |
| `electricity` | Power and wiring: no power, sockets, switches, lights, wiring, fuses and breakers, the intercom and doorbell, smoke and CO detectors | A broken fridge or oven (`appliances`). The AC (`ac`) |
| `ac` | Air conditioning, heating and ventilation. Sub-label: `cooling`, `heating` or `ventilation` (D1 A). The AC unit itself: not cooling, not heating, dripping water, noise, smell, remote, freon. Exhaust fans | A portable heater (`appliances`) |
| `carpentry` | Anything that opens, closes or locks: doors, door frames, locks, windows, window frames, window glass, built-in cabinets and wardrobes (D2 A) | Paint on a door or window (`general`) |
| `pest_control` | Insects and animals: cockroaches, mice and rats, bed bugs, ants, flies, fleas, termites | |
| `gas` | The gas supply: gas smell, gas leak, a hissing gas pipe, no gas, gas that doesn't reach the cooker, the gas pipe, valve or meter | A broken cooker part, such as a knob or oven door (`appliances`) |
| `appliances` | Devices in the unit: fridge, cooker (stove) and oven, microwave, washing machine, dishwasher, portable heater (D6 B) | The AC (`ac`). The water heater (`plumbing`) |
| `general` | Everything else in the unit or building: walls, paint, plaster, ceilings, floors and tiles (D3 A), stairs, mold (D4 A), garbage, the elevator, the roof, balconies, window guards, outside areas | |

`general` is for problems that belong to none of the other 7. It is not a place for messages
you didn't read carefully.

---

## 3. When more than one category fits (one problem)

Go down this list and stop at the first rule that fits:

1. **Gas first.** Any gas smell, gas leak or missing gas → `gas`.
2. **The dangerous part decides.** Water on a light or a socket, sparks, smoke or a burning
   smell → `electricity`.
3. **The source first, if the message names it.** "Mold *because of* the bathroom leak" →
   `plumbing`. "The ceiling paint is peeling *because water comes from upstairs*" → `plumbing`.
   "Water is dripping *from the AC*" → `ac`.
4. **Otherwise, what the resident sees broken.** "There is mold on the wall" (no cause) →
   `general`.
5. **Still not sure?** → `general`.

---

## 4. Urgency (3 levels)

| Level | Definition | Typical time (only to help you choose: the bot promises nothing) |
|---|---|---|
| `high` | Danger to people or property **now**, or a basic service is **completely gone** for the unit | Hours |
| `medium` | Something important doesn't work, or it is getting worse, but nobody is in danger | 1–3 days |
| `low` | Cosmetic or small. The home works normally | A planned visit |

**Basic services** are water and electricity for the whole unit. Gas, hot water, heating and
cooling are important but not basic: losing them is `medium` (unless there is danger, such as a
gas smell).

**Only the problem decides (D8 A).** Who lives there (a baby, an old or sick person), how many
people are affected, and the season do **not** change the urgency. "The AC isn't cooling" is
`medium` in August too. The words that describe the size of the problem **do** matter:
"pouring" vs "dripping", "the whole flat" vs "one room".

### Always `high`

| Case | Category |
|---|---|
| Gas smell or gas leak, even if it "went away" | `gas` |
| Sparks, smoke or a burning smell from a socket, switch, light or wires; exposed wires | `electricity` |
| Water touching electricity (wet light fixture, water near a socket) | `electricity` |
| Flooding, water pouring from a ceiling or wall, water going into another flat | `plumbing` |
| No water at all in the unit | `plumbing` |
| No power in the whole unit | `electricity` |
| Sewage coming back up | `plumbing` |
| Scalding hot water from the tap | `plumbing` |
| A ceiling or wall falling down | `general` |
| A fall risk: missing stairs, a broken balcony railing | `general` |
| A person stuck in the elevator | `general` |

A water cut may come from the city, not the building. It is still `high`: we label the
message, not the cause.

### Examples

| Urgency | English | Egyptian Arabic | Category |
|---|---|---|---|
| high | There's a strong gas smell in the kitchen. | فيه ريحة غاز جامدة في المطبخ | gas |
| high | The bedroom socket is sparking and smells like burning. | بريزة أوضة النوم بتطلع شرار وفيه ريحة حريق | electricity |
| high | Water is pouring from the ceiling and the living room is flooding. | المية نازلة من السقف والصالة بتغرق | plumbing |
| medium | The bedroom AC isn't cooling. | تكييف أوضة النوم مش بيبرد | ac (cooling) |
| medium | The kitchen sink is blocked; the water doesn't go down. | حوض المطبخ مسدود والمية مش بتنزل | plumbing |
| medium | We have lots of cockroaches in the kitchen. | فيه صراصير كتير في المطبخ | pest_control |
| low | The paint on the bathroom ceiling is peeling. | دهان سقف الحمام بيقشر | general |
| low | A kitchen cabinet door is loose. | ضلفة دولاب المطبخ سايبة | carpentry |
| low | One floor tile in the hallway is cracked. | فيه بلاطة مشروخة في الطرقة | general |

---

## 5. Two problems in one message (D10 A)

One message gets **one** label:

- **Category:** the category of the **most urgent** problem. If both problems are equally urgent,
  use the problem the message mentions **first**.
- **Urgency:** the **highest** urgency of the two.

| Message | Label | Why |
|---|---|---|
| The kitchen tap drips and there's a gas smell. / الحنفية بتنقط وفيه ريحة غاز في المطبخ | gas, high | The gas smell is the most urgent |
| The bathroom door doesn't lock and the paint is peeling. / باب الحمام مش بيقفل والدهان بيقشر | carpentry, medium | Door (medium) > paint (low) |
| Cockroaches in the kitchen, and the AC isn't cooling. / فيه صراصير في المطبخ والتكييف مش بيبرد | pest_control, medium | Both are medium, and the cockroaches come first |

In Phase 3 the bot can ask the resident to send the second problem as a new request.

---

## 6. Edge cases

| Message | Label | Rule |
|---|---|---|
| The AC is dripping water on the floor. / التكييف بينقط مية على الأرض | ac (cooling), medium | Source first (§3.3) |
| Water is dripping from the ceiling light. / المية بتنقط من لمبة السقف | electricity, high | The dangerous part decides (§3.2) |
| There's mold on the bedroom wall. / الحيطة في أوضة النوم فيها عفن | general, medium | Mold with no named cause (D4 A) |
| The wall has mold from the bathroom leak. / الحيطة فيها عفن من التسريب اللي في الحمام | plumbing, medium | The source is named (§3.3) |
| No gas reaches the cooker. / البوتاجاز مش بيوصله غاز | gas, medium | The gas supply, not the cooker |
| A cooker knob is broken. / زرار البوتاجاز مكسور | appliances, low | The cooker itself |
| The oven doesn't heat. / الفرن مش بيسخن | appliances, medium | The cooker itself, and it doesn't work |
| The gas water heater won't light (no smell). / السخان مش بيولع | plumbing, medium | The water heater is plumbing; no gas smell |
| The AC doesn't heat. / التكييف مش بيدفي | ac (heating), medium | Heating is `ac` (D1 A) |
| The bathroom exhaust fan is broken. / شفاط الحمام عطلان | ac (ventilation), medium | Ventilation is `ac` |
| The paint on the front door is peeling. / دهان باب الشقة بيقشر | general, low | The problem is the paint, not the door |
| The window glass is broken. / إزاز الشباك مكسور | carpentry, medium | Windows are `carpentry` (D2 A) |
| The lock is broken and I can't lock the flat door. / الكالون بايظ ومش عارف أقفل باب الشقة | carpentry, medium | No extra level for security (D8 A) |
| The intercom doesn't work. / الانتركم مش شغال | electricity, low | |
| The smoke detector keeps beeping. / حساس الدخان بيصفر على طول | electricity, medium | |
| The tap in the bathroom sink gives no water. / حنفية الحوض مش بتنزل مية | plumbing, medium | One tap, not the whole unit |
| There's no water at all in the flat. / مفيش مية خالص في الشقة | plumbing, high | The whole unit (§4) |
| The toilet keeps running. / السيفون بيفضل شغال على طول | plumbing, low | It works; it only wastes water |
| Garbage is piling up in the corridor. / الزبالة متكومة في الطرقة | general, medium | |
| The balcony railing is loose. / سور البلكونة مخلخل | general, high | Fall risk |
| The elevator stopped with someone inside. / الأسانسير وقف وفيه حد محبوس جواه | general, high | A person is in danger now |

**Unclear messages.** If you can't choose a category after reading the message twice, the message
is too vague to be a test message. Rewrite it or leave it out. In the bot, the follow-up
questions (Phase 3) and the `needs_review` flag (Phase 4) handle vague messages.

---

## 7. Seed lists for Phase 2 (synthetic messages)

The NYC data has **no** AC cooling problems and **no** gas smell at all (gas leaks in NYC are
probably reported to the gas company or 911, not to HPD). The Phase 2 synthetic messages for
these come from the lists below. The labels are chosen first and the message is written to fit them ("label first").

**AC mix (D1 A):** of all synthetic `ac` messages, **70% cooling, 20% heating,
10% ventilation**. In Egypt most AC work is cooling. (In the NYC sample, 97.7% of the `ac`
rows are heating.)

| Sub-label | Problem | Egyptian Arabic | Urgency |
|---|---|---|---|
| cooling | Not cooling | التكييف مش بيبرد | medium |
| cooling | Dripping water inside the room | التكييف بينقط مية جوه الأوضة | medium |
| cooling | Very loud noise | التكييف صوته عالي أوي | medium |
| cooling | Bad smell when it runs | التكييف طالع منه ريحة وحشة | low |
| cooling | The remote or display doesn't work (the AC can't be turned on) | ريموت التكييف مش شغال | medium |
| cooling | Needs a freon refill | التكييف محتاج شحن فريون | medium |
| cooling | The outdoor unit doesn't start | الوحدة الخارجية للتكييف مش بتشتغل | medium |
| cooling | Turns off by itself | التكييف بيفصل لوحده | medium |
| heating | Not heating in winter | التكييف مش بيدفي | medium |
| ventilation | The exhaust fan is broken | شفاط الحمام عطلان | medium |

| Problem | Egyptian Arabic | Urgency |
|---|---|---|
| Gas smell | فيه ريحة غاز | high |
| A hissing sound from the gas pipe | فيه صوت تسريب من ماسورة الغاز | high |
| No gas in the flat | الغاز مقطوع عندنا | medium |
| No gas reaches the cooker | البوتاجاز مش بيوصله غاز | medium |

---

## 8. How the NYC 311 data was mapped

The training data source (brief, "Data strategy") is NYC 311, HPD housing complaints
(Step 1.7). Each 311 row has a 3-level problem, for example
`WATER LEAK / HEAVY FLOW / AT WALL OR CEILING`, and **no text written by the resident**.
`ml/label_mapping.py` gives each of the 174 problem groups a category and an urgency, or drops
it. `ml/prepare_311.py` applies it and writes `ml/data/processed/311_mapped.csv`.

- **Rules:** a default per complaint type plus exceptions; the most specific rule wins. `GENERAL`
  and `SAFETY` have no default (they are mixed groups). A problem with no rule stops the script.
- **Mixed rows:** when one 311 row mixes two levels (for example `FAUCET BROKEN/MISSING/LEAKING`),
  it gets the higher one.
- **Dropped rows (12.1% of the year):**

| Reason | Rows (year) | Examples |
|---|---|---|
| `two_categories` | 91,693 | `NO HEAT AND NO HOT WATER` (ac + plumbing in one row) |
| `not_in_egypt` | 12,392 | Radiators, steam pipes, boilers, fire escapes, dumbwaiters |
| `not_maintenance` | 5,212 | Missing legal notices (signage), no janitor |
| `bad_row` | 1 | `Safety / Safety / Safety` |

- **Result (sample, 79,544 kept rows):** ac 27.3%, plumbing 23.2%, general 21.0%,
  pest_control 9.1%, carpentry 7.8%, electricity 7.0%, appliances 3.3%, gas 1.2%.
  Urgency: medium 70.3%, low 20.6%, high 9.2%.

These shares describe NYC housing complaints, not our training set. The Phase 2 training set
gets its own balance (for example the AC mix above).

---

## 9. Changing a rule

1. Discuss it and decide. Log the decision in `CLAUDE.md` section 13.
2. Change this guide **and** `ml/label_mapping.py` (and its test, `tests/test_label_mapping.py`).
3. Re-run `uv run python -m ml.prepare_311` and check the new counts.
4. Add a line to the change log below. Labels made with an older version may need a check.

| Version | Date | Change |
|---|---|---|
| 1 | 2026-10-27 | First version (Step 1.8): 8 categories, 3 urgency levels, D1–D10 |
