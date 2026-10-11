# Stage-1 reading experiment — RESULTS

*2026-10-11. The Syzygy premise test (Claude's design, ARCHITECTURE-SYNTHESIS.md: "first move is an experiment"): can text-only models actually READ a scene from its text render? Environment: mazelab (VETTING-01: training-grade; frame and ground truth are two projections of one object, so pairing is exact by construction).*

## Setup

- **Episodes:** 60 mazelab mazes, seeds 2000–2059, sizes cycling 11×9 → 17×15, complexity/density cycling (0.3,0.3)…(0.8,0.7). Agent and goal placed on distinct free cells, Manhattan distance ≥ max(4, (H+W)/4). Full records: `episodes.jsonl`.
- **Questions (frozen bank, `QUESTION_BANK.md`):** 5 closed-form, purpose-shaped (navigation archetype) per episode — Q1 goal bearing (8-way), Q2 adjacent wall count (0–4), Q3 wall immediately west (yes/no), Q4 Manhattan distance (integer), Q5 path exists (yes/no). **Every answer derived programmatically from the ground-truth grid** (`gen_episodes.py`), never from a model.
- **Readers:** MiniMax-Text-01 (stock CLI, temperature 0.7 default) and GLM glm-4.5-flash (see deviation note below; temperature 0.7). Each reader got the frozen reading guide (`READING_GUIDE.md`, written once, never edited during the run) plus, per condition, the frame. One batched call per (reader, condition, episode): all 5 questions, strict 5-line answer format demanded.
- **Conditions:** `frame` (the episode's own text frame), `blind` (no frame — prior/guessing baseline), `shuffled` (a different episode's frame, rotation +23 — frame-use control). 360 scored records total; scoring is exact-match after per-type normalization by a pure function (`run_readers.py`), never by a model. Failed API attempts (44, all HTTP 429) are kept in `reader_outputs.jsonl` and were backfilled to full 360/360 coverage.

## Deviations & design repairs (all documented, none hidden)

1. **GLM reader plumbing.** glm-4.5-flash is a reasoning model: via the stock CLI it returned *empty content* on grid prompts — diagnosed from the raw API response: `finish_reason='length'`, all 2000 completion tokens spent on `reasoning_content` (5,504 chars), content 0 chars; at larger budgets it exceeded the CLI's hardcoded 120 s read timeout. The other entitled models were unavailable (glm-4.5 / glm-4.5-air: 429 on this key). Fix: `glm_call.py`, an experiment-local caller using the *same* endpoint, model, and credential path as the skill documents, with `thinking: {type: 'disabled'}` — the same model then answers in ~2.5 s with clean format. The GLM reader is therefore "glm-4.5-flash with thinking disabled"; its scores are a *direct-answer* measurement, not a chain-of-thought one.
2. **Q5 repair.** The raw generator's free space was connected in 60/60 pilot episodes (Q5 would have been a constant "yes" — pure prior). For half the episodes (odd indices) the goal's 4 neighbours were walled in the raw grid *before* the maze object and frame were built, so frame/truth pairing stayed exact. Q5 truth is 30 yes / 30 no by construction. This manipulation turned out to be the most informative one in the experiment (see findings).
3. **Q2 skew (not repaired, reported).** This maze family's statistics make adjacent-wall-count prior-heavy: truth distribution is {2: 51, 3: 5, 1: 4}. A constant "2" scores 0.850. Q2 therefore measures mostly prior, and is interpreted that way below.

## Headline numbers (strict frozen scoring; unparsed = wrong)

| reader | frame | blind | shuffled | LIFT (frame − blind) |
|---|---|---|---|---|
| GLM (glm-4.5-flash, thinking off) | **0.443** | 0.153 | 0.337 | **+0.290** |
| MiniMax (MiniMax-Text-01) | **0.353** | 0.107 | 0.253 | **+0.247** |

Per-question accuracy (frame | blind | shuffled):

| q | type | GLM | MiniMax | constant-answer baseline |
|---|---|---|---|---|
| Q1 | goal bearing (8-way) | **0.517** \| 0.017 \| 0.083 | 0.267 \| 0.033 \| 0.050 | 0.250 (always SW) |
| Q2 | adjacent walls (0–4) | 0.533 \| 0.050 \| 0.450 | 0.300 \| 0.083 \| 0.383 | **0.850** (always 2) |
| Q3 | wall west (y/n) | 0.600 \| 0.317 \| 0.633 | 0.533 \| 0.217 \| 0.383 | **0.633** (always no) |
| Q4 | Manhattan distance | 0.067 \| 0.000 \| 0.033 | 0.183 \| 0.017 \| 0.000 | 0.133 (always 10) |
| Q5 | path exists (y/n) | 0.500 \| 0.383 \| 0.483 | 0.483 \| 0.183 \| 0.450 | 0.500 (always yes) |

Sensitivity (non-answers distort the naive lift — stated, not buried): in the blind condition GLM frequently echoed the answer *template* instead of guessing ("Q1: <answer>"), leaving 161/300 slots unparsed; MiniMax left 166/300. Scoring only parsed slots: GLM blind 0.331 → adjusted lift ≈ **+0.11**; MiniMax blind 0.239, frame parsed-only 0.408 → adjusted lift ≈ **+0.17**. The strict lift (+0.29 / +0.25) is the frozen headline; the honest range is **+0.11 … +0.29**.

## Findings

1. **Bearing is genuinely read.** Q1 is the clean signal: GLM 0.517 with the frame vs 0.017 blind, and shuffled collapses to 0.083 — the reader is reading *this* frame, not a generic maze. Component analysis of GLM's Q1: 31/60 exact, 28/60 with exactly one axis right, only 1/60 with both axes wrong. It localizes A and G in the grid and compares positions; it is imprecise, not lost. MiniMax reads bearing too, more weakly (0.267 vs 0.250 constant baseline, 0.033 blind).
2. **Local adjacency is NOT read better than prior.** On Q2 both readers lose to a constant answer (0.533/0.300 vs 0.850); on Q3 they match or lose to constant "no" (0.600/0.533 vs 0.633), and GLM's shuffled Q3 (0.633) equals its frame Q3 — its Q3 "skill" is the prior wearing the frame as a costume. Whatever the readers extract from the grid, reliable single-cell neighbourhood inspection is not yet it.
3. **Connectivity is never verified — the sealed goal is invisible to them.** Split by the Q5 manipulation: unsealed episodes, GLM 30/30, MiniMax 28/30 correct ("yes"). Sealed episodes — goal visibly boxed in `#` on all four sides — **GLM 0/30, MiniMax 1/30**. Both readers answer "a path exists" essentially unconditionally; neither performs even the local check around G that would refute it. Q5's ~0.50 frame accuracy is the always-yes constant, not reasoning.
4. **Distance is estimated, not counted (GLM); counted imperfectly (MiniMax).** GLM Q4: 4/60 exact, errors spread to ±18 — it produces a plausible magnitude. MiniMax Q4: 11/60 exact, 11 more off by exactly one — a counting procedure that slips. (Claude's plan takes note: the FFT/luma side channels won't fix this; a *procedure* in the reading guide might — see below.)
5. **Format discipline is part of reader skill.** MiniMax ignored the 5-line format in 19/60 frame records and answered in step-by-step prose, leaving 40/300 frame slots unparsed under the frozen strict parser (its parsed-only frame accuracy is 0.408 vs 0.353 strict; absolute ceiling if every unparsed slot hid a correct answer: 0.486). The prose sometimes contained the right answer in a form the frozen scorer could not take — and at least once talked itself past its own correct intermediate step. GLM (thinking disabled) was format-perfect with a frame present: 0 parse failures in frame and shuffled conditions.
6. **Shuffled > blind for both readers** (0.337/0.253 vs 0.153/0.107): a wrong-but-real maze transfers maze-family priors (Q2≈2, Q3≈no). This is why the blind control alone would overstate reading; the shuffled control is what isolates episode-specific reading, and on Q1 it confirms it.

## Concrete failures (quoted from `reader_outputs.jsonl` / `frame_failures.json`)

- **The invisible box (both readers, ep01, Q5).** The frame's last rows show the goal sealed: `#..A#...#G#.#` with `#` above and below the G. Truth: **no** path exists. GLM: "yes". MiniMax: "yes". Neither checked the four cells around G.
- **Off-by-a-little counting (GLM, Q4).** ep00: truth 7, GLM 8. ep02: truth 10, GLM 11. Close enough to look like counting; the full error distribution (finding 4) shows it is estimation.
- **Mirror flip (MiniMax, ep07, Q1).** Truth SW; MiniMax answered SE — the north/south axis right, east/west mirrored. ep05: truth NW, answered E (both axes wrong, its worst Q1 mode).
- **Right answer, unusable envelope (MiniMax, ep02).** Asked for 5 bare lines, it replied with a step-by-step analysis ("Let me analyze this step by step: … So there are 2 walls adjacent to the agent. Answer: 2") — knowledge present, contract broken; the frozen parser scored 2 of its 5 slots unparsed/wrong on that record.

## Guide finding (noted, NOT applied — the guide stayed frozen)

No guide ambiguity materially affected scoring: symbol meanings, adjacency, and direction conventions were sufficient for every question type. The guide's real gap is that it teaches *vocabulary, not procedure* — nothing in it tells a reader how to count a Manhattan distance cell by cell, or to verify a claimed path by inspecting the goal's neighbourhood. Findings 3–4 are exactly the failures a procedure section targets. That is a curriculum-v2 experiment (guide as a variable), deliberately not folded into this run.

## Verdict

**The premise holds — narrowly, unevenly, and only for position.** At stage-1 difficulty, text-only models really can read *where things are* from a symbolic character grid: bearing lift over both controls is large and frame-specific. They cannot yet be trusted to *check* anything in the grid: local wall facts are at or below constant-answer baselines, path existence is asserted rather than verified (a fully walled-in goal went unnoticed 59 times out of 60), and distances are guessed magnitudes (GLM) or slip-prone counts (MiniMax).

Against Claude's proposed stage-1 gate (reader ≥ 90% accuracy, ≥ 40 points of lift): **not met by either reader** — best is 44.3% and +29 points strict (+11 adjusted). Per the architecture synthesis, the gate thresholds are now to be re-set from this baseline rather than from hope; the curriculum implication is specific, not generic: teach and test *verification behaviour* (inspect the goal's neighbourhood, trace before claiming a path) and *counting procedure*, because positional reading is already there to build on.

## Artifacts (all in this directory)

`episodes.jsonl` (60 episodes: grid, frame, positions) · `questions.jsonl` (300 questions with ground-truth answers) · `READING_GUIDE.md` + `QUESTION_BANK.md` (frozen instruments) · `reader_outputs.jsonl` (360 scored records with prompts, raw outputs, parsed answers, per-question correctness, latencies; plus 44 failed 429 attempts, backfilled) · `pilot_failures.jsonl` (pilot-phase failures, archived) · `scores.json` (machine-readable results) · `frame_failures.json` (every frame-condition failure) · `gen_episodes.py`, `run_readers.py`, `glm_call.py`, `summarize.py` (the harness) · `full_run.log`, `backfill1.log` (run logs).

*Run cost note: ≈360 successful reader calls (MiniMax mean latency ≈6.6–9.0 s, GLM ≈2.5–3.4 s per batched 5-question call) plus retries. Readers ran at temperature 0.7 (both CLIs' default), so per-record answers are samples, not deterministic reads.*
