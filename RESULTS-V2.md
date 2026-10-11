# Stage-1 reading experiment v2 — RESULTS

*2026-10-11. Follow-up to RESULTS.md (v1). The v1 guide taught vocabulary, not procedure; its exposed failures were specific: bearing read but imprecise, wall counts below a constant baseline, distances estimated rather than counted, and path existence asserted rather than verified (sealed goal: GLM 0/30, MiniMax 1/30). V2 asks one question: does teaching PROCEDURES move those numbers?*

## Setup — what changed, exhaustively

- **Frozen from v1, byte-identical:** the same 60 episodes (`episodes.jsonl`), the same 300 ground-truth questions (`questions.jsonl`), the same scorer (the pure functions in `run_readers.py`, imported — not reimplemented — by `run_readers_v2.py`), the same reader CLIs, same `--max-tokens 2000`, same temperature defaults, same 3 conditions, same first-success filter rule.
- **The treatment:** `READING_GUIDE_V2.md` = the v1 vocabulary section verbatim, plus (a) an answer format that requires Work lines (checks) before each answer line, (b) explicit procedures per question type (state row/column differences and their signs before naming a bearing; name A's four neighbours one at a time before totalling; tally distance step-by-step along row then column; for path existence, FIRST inspect the goal's four neighbours — if all walls, answer no — otherwise trace a written route), and (c) ONE fully-worked example maze (hand-built, machine-verified: A (4,4), G (6,6), bearing SE, wall count 2, west open, distance 4, route E‑S‑S‑E).
- **Cross-feed (doctrine, disclosed confound):** every v2 prompt was preceded by the program's three writing-break pieces (`writings/claude-piece.md`, `minimax-piece.md`, `glm-piece.md`) as session reading, per the program's cross-feeding doctrine. This is constant across all v2 conditions, so it cannot explain any within-v2 difference; it IS a second difference from v1 alongside the guide, so the v1→v2 deltas below are attributed to the guide+reading package, with the guide as the designed variable. No measured effect is claimed for the stories.
- **Coverage:** 360/360 successful records after backfill passes; 56 failed attempts (mostly ZAI 429s; GLM's runner also exited early twice) are retained in `reader_outputs_v2.jsonl`, as in v1. A few combos carry duplicate successful records from overlapping backfill passes; the frozen first-success filter resolves them exactly as in v1.
- **Cost note:** the v2 prompt is ~22k characters (stories ≈17k). GLM latency rose from ~2.5 s/call (v1) to ~12–106 s/call; MiniMax ~23–41 s/call. Prompt size is a real cost of the cross-feed, recorded here because the program prices everything in compute.

## Headline numbers

Frame accuracy rose **+13.0 points for both readers**. The strict lift narrowed slightly; the parse-adjusted lift (v1's own sensitivity measure) *rose* for both — see finding 6 for why the strict number misleads here.

| reader | frame v1 → v2 | blind v1 → v2 | shuffled v1 → v2 | strict lift v1 → v2 | adjusted lift v1 → v2 |
|---|---|---|---|---|---|
| GLM | 0.443 → **0.573** | 0.153 → 0.313 | 0.337 → 0.290 | +0.290 → +0.260 | ≈+0.11 → **≈+0.24** |
| MiniMax | 0.353 → **0.483** | 0.107 → 0.257 | 0.253 → 0.260 | +0.247 → +0.227 | ≈+0.17 → **≈+0.24** |

Per-question frame accuracy (v1 → v2), with v1's constant-answer baselines:

| q | type | GLM | MiniMax | constant baseline |
|---|---|---|---|---|
| Q1 | goal bearing | 0.517 → **0.967** | 0.267 → **0.850** | 0.250 |
| Q2 | adjacent walls | 0.533 → 0.483 | 0.300 → 0.283 | **0.850** |
| Q3 | wall west | 0.600 → **0.700** | 0.533 → **0.617** | 0.633 |
| Q4 | Manhattan distance | 0.067 → **0.250** | 0.183 → **0.200** | 0.133 |
| Q5 | path exists | 0.500 → 0.467 | 0.483 → 0.467 | 0.500 |

Q5 split by the sealed-goal manipulation (frame condition):

| reader | sealed v1 → v2 (of 30) | unsealed v1 → v2 (of 30) |
|---|---|---|
| GLM | 0 → **16** | 30 → **12** |
| MiniMax | 1 → **1** | 28 → 27 |

Q4 error profile (frame; exact / within-one / mean |error| / max |error|):

| reader | v1 | v2 |
|---|---|---|
| GLM | 4/60 · 13/60 · 5.12 · 18 | 15/60 · **39/60** · **1.37** · 6 |
| MiniMax | 11/42 parsed · 22/42 · 2.24 · 11 | 12/56 parsed · **38/56** · **1.36** · 6 |

## Findings

1. **Bearing is transformed — the sign procedure works.** GLM 0.517 → 0.967, MiniMax 0.267 → 0.850. Stating both differences and their signs before naming the direction nearly eliminates the mirror flips and axis errors of v1. Q1 is now the first question type to clear the 90% stage-1 gate bar (GLM).
2. **Distance is now counted, not guessed.** Both readers' error distributions collapsed (table above): GLM's mean |error| fell from 5.12 to 1.37 and its worst error from 18 to 6; ~2/3 of answers land within one step. Exact answers remain a minority (25% / 20%) — the tally procedure runs, but individual tallies still slip. A tally quote (GLM, ep03, correct): "Column steps from A's column 11 toward G's column 3: step 1 -> column 10, step 2 -> column 9, … step 8 -> column 3. Total: 0 + 8 = 8."
3. **Wall counting did not move — and the reason is not the procedure.** Q2 stays below the constant-2 baseline for both readers (0.483 / 0.283 vs 0.850). The Work lines show the neighbour-naming procedure executed faithfully — on the WRONG CELL. GLM, ep00 (truth: A at row 4, column 8; answer 2): "Neighbours of A (row 4, column 7): north cell (row 3, column 7) is '#' — wall. South … '#' — wall. East cell (row 4, column 8) is '#' — wall. West … '.' — open. Total walls: 3." Perfect arithmetic, wrong address.
4. **The binding constraint is absolute localization — specifically columns.** Extracting the positions readers stated in their own Work lines (59/60 records extractable): rows are read nearly perfectly (GLM row-exact 57/59 for A; MiniMax 48/59), columns are not (GLM column-exact 16/59; MiniMax 19/59), and the dominant error is off-by-one column (24 of GLM's 59 A-localizations). Exact (row+column) localization: ~15–17 of 59 for both readers, both targets. This one mechanism explains the whole delta table: Q1 and Q4 are *differences* (a systematic column shift cancels), so procedures fixed them; Q2, Q3 and Q5's Stage‑1 are *absolute* (which cell, what is beside it), so they remain hostage to a coordinate the reader cannot reliably read. Rows come free from line structure; columns demand counting characters inside a line.
5. **Path existence: the aggregate is flat, the failure mode changed — for GLM.** Overall Q5 sits at chance in both versions, but GLM's errors inverted: v1 was the always-yes constant (sealed 0/30, unsealed 30/30); v2 splits 16/30 and 12/30. Anatomy of GLM's 16 sealed "catches" (negation-aware read of the Stage‑1 text): only **4 are genuine seal detections** (ep09, ep13, ep45, ep51) — and even the cleanest of those is imperfect: on ep09 GLM inspected the cell west of the goal, read the goal's own cell as '#' and an open cell as '#', and still reached the correct "no" because the goal truly is sealed. **11 of the 16 are trace exhaustion**: GLM traced, backtracked, got stuck, and concluded "no" — accidentally right on sealed episodes, and the direct cause of the unsealed collapse (the same give-up-and-say-no on episodes where a path exists but its one-pass written search couldn't find it). MiniMax is unmoved (sealed 1/30 → 1/30): its Stage‑1 inspections run on mislocated goals (ep01: inspected column 8, goal is at column 10) or are confabulated outright (ep03, sealed: all four neighbours of G reported "open", then a route fabricated along a row). Before/after on the same episode, ep01 — v1 GLM: `Q5: yes` (five bare lines, no inspection of any kind). v2 GLM: a full Stage‑1 + a five-step written route — to a cell that is not the goal. The behaviour changed exactly as taught; the eyes it runs on did not.
6. **The controls moved for format reasons — disclosed, not buried.** Blind accuracy rose (GLM 0.153 → 0.313) mainly because blind guesses now PARSE: v1's blind records were majority-unparseable (GLM 161/300 slots, MiniMax 166/300 — template echoes scored as wrong); v2's work-then-answer format cut that to 34 and 17. Hence the strict lift (frame − blind) narrows artifactually while the parse-adjusted lift rises for both readers (≈+0.11 → ≈+0.24 GLM; ≈+0.17 → ≈+0.24 MiniMax). Shuffled fell for GLM (0.337 → 0.290): v1's shuffled score was padded by maze-family priors (Q2 0.450, Q3 0.633 on the wrong maze); v2 commits to worked readings of the wrong frame (shuffled Q3 0.633 → 0.450), which is what a frame-use control should punish.
7. **Format discipline improved where it was broken.** MiniMax frame parse failures 40 → 19 (blind 166 → 17): giving its prose a legitimate Work channel fixed most of its v1 contract violations. GLM, format-perfect in v1, slipped slightly (frame 0 → 8) under the longer format.

## Verdict

**Procedure teaching moved exactly the numbers that were procedural — and exposed, precisely, the ones that aren't.** Bearing (0.52 → 0.97) and distance (mean error ÷ ~4) were knowledge-of-method problems, and the method fixed them. Verification (Q5) changed in form — GLM inspects and traces now instead of asserting — but not yet in reliability: its written search cannot distinguish "sealed" from "I failed to find it," and MiniMax performs the inspection without performing it. Wall counting never had a procedure problem at all: it has a *position* problem. The experiment's sharpest product is that diagnosis — relative geometry (differences of positions) reads well and is now procedure-solid; absolute column position is the binding constraint on everything else, and no amount of additional procedure text in the guide will fix a coordinate the reader misreads before the procedure starts.

Curriculum implication, specific as v1's: the next lever is not more procedure — it is **position anchoring in the frame itself** (a column ruler, coordinate-tagged rows, or another canonical-frame device; a shard‑0011 question), because stage‑1's remaining failures all stand on the same misread column. Against the stage‑1 gate (reader ≥ 90% accuracy, ≥ 40 points of lift): **still not met overall** — best frame accuracy 0.573, best adjusted lift ≈ +0.24 — but the gate is now met by one question type (GLM Q1, 0.967), which is the first clean pass of any reader on any measure in either version.

## Artifacts (all in this directory)

`READING_GUIDE_V2.md` (the treatment) · `reader_outputs_v2.jsonl` (360 scored records with prompts, raw outputs, parsed answers, per-question correctness, latencies; 56 failed attempts retained) · `scores_v2.json` (v1 and v2 stats, same summarizer) · `run_readers_v2.py` (imports the frozen v1 scorer/caller) · `summarize_v2.py` · run logs: `minimax_v2_run.log`, `glm_v2_run.log`, `*_backfill*.log`.

*Readers ran at temperature 0.7 (both callers' defaults), as in v1, so per-record answers are samples, not deterministic reads. The v1→v2 comparison is a guide comparison, not a seed-controlled one — same caveat as v1's own design.*
