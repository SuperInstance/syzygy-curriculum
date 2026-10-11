# syzygy-curriculum — the entrance exam for seeing in text

## The question, in plain English

[Syzygy](https://github.com/SuperInstance/Syzygy) turns a picture into a page
of text. Before building a school to teach language models to read those
pages, we ran the entrance exam: **hand a text-only model a scene rendered
as characters, and ask simple questions about it.** Which direction is the
goal? How many walls touch you? Does a path exist at all?

This repo is that exam — the mazes, the questions, every answer the models
gave, and the scores, kept honest by two control conditions: *blind* (no
picture at all — measures guessing) and *shuffled* (the wrong maze's
picture — measures whether the model is reading *this* frame or just
sounding plausible). The difference between the real-frame score and the
blind score is the **lift**: the part of the score that is actually
reading.

## What we found (baseline, 2026-10-11)

60 mazes, 300 questions whose answers were computed from the mazes' ground
truth (never from a model), two readers — MiniMax-Text-01 and GLM
glm-4.5-flash. Full detail in [RESULTS.md](RESULTS.md).

- **Position is genuinely read.** Goal bearing: GLM scored 0.517 with the
  frame vs 0.017 blind, and shuffled frames collapsed it to 0.083. The
  models really do locate things in the grid.
- **Checking is not read — yet.** Wall-counting scored *below* a constant
  "always answer 2" baseline (0.533 / 0.300 vs 0.850). Distances were
  estimated, not counted. And when the goal was sealed inside walls, both
  models still asserted a path exists: GLM 0/30, MiniMax 1/30 on the sealed
  mazes. They assert; they don't inspect.
- **Procedures teach.** In v2 ([RESULTS-V2.md](RESULTS-V2.md)) the only
  change was a reading guide that teaches *procedures* — count cell by cell
  aloud, name each neighbour before totalling, inspect the goal's own four
  neighbours before claiming a path — plus one worked example. Frame
  accuracy rose **+13 points for both readers** (GLM 0.443 → 0.573,
  MiniMax 0.353 → 0.483); GLM's bearing hit 0.967 and its sealed-goal
  detection went 0/30 → 16/30. Vocabulary didn't fail in v1 — procedure was
  missing, and procedure is teachable. That is the curriculum's first
  lesson, measured rather than hoped.

## Files

| file | what it is |
|---|---|
| `episodes.jsonl` | the 60 mazes: ground-truth grids + text frames |
| `questions.jsonl` | the 300 questions, answers derived from ground truth |
| `QUESTION_BANK.md` | the frozen question bank (5 per episode, purpose-shaped) |
| `READING_GUIDE.md` / `READING_GUIDE_V2.md` | the v1 (vocabulary) and v2 (procedures) guides |
| `reader_outputs.jsonl` / `reader_outputs_v2.jsonl` | every reader answer, raw — including failed API attempts, kept on purpose |
| `scores.json` / `scores_v2.json` | exact-match scores by the frozen scorer |
| `RESULTS.md` / `RESULTS-V2.md` | the write-ups, deviations disclosed in-line |
| `gen_episodes.py`, `run_readers*.py`, `summarize*.py`, `glm_call.py` | the harness (stdlib + the fleet CLIs; GLM needs thinking disabled — see RESULTS.md deviation 1) |

Part of the Syzygy program — map and plan:
[SuperInstance/syzygy-program](https://github.com/SuperInstance/syzygy-program).
