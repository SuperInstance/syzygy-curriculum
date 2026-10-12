# Gradebook pilot — first frozen slice

*2026-10-12. Teacher loop from the Syzygy Phase 2 architecture plan, exercised at
pilot scale. Teacher output is frozen as a content-addressed gradebook; the teacher
is not a runtime dependency of anything here — consumers read the frozen items and
their verification annotations, never the model.*

## What this is

60 items. For each item the teacher (MiniMax-Text-01, temperature 0) produced the
synthesis's four graded outputs: **(a)** closed-form facts in a fixed predicate
vocabulary, **(b)** a per-fact recoverability judgement (`recoverable` / `hard` /
`unrecoverable` — could a careful reader derive this from the frame alone?),
**(c)** appearance labels for a 4×3 region grid over the frame, and **(d)** one-line
reader hints, each tagged with a known reader failure mode drawn from the
reading-experiment results (sealed-goal assertion, wall-count constant-guessing,
distance guessing, direction slip; for real frames: confabulated tallies,
bright-flat misreads, saturation blindness). No free-text captions are graded or
stored as facts.

Items are content-addressed: `items/<sha256>.json`, the hash taken over the
canonical JSON of the item body. `manifest.json` (sha256 in `manifest.sha256`)
records every item's hash, provenance, split, and verification summary.

## Coverage

| slice | n | source | split |
|---|---|---|---|
| Mazelab episodes ep00–ep39 | 40 | `syzygy-program/reading-experiment/episodes.jsonl` (glyph frames, exact programmatic truth) | train |
| Docks text frames 0, 15, 30, …, 285 | 20 | `syzygy-video/out/docks-text/tone/` — tone plane, 148×80, 6 fps timestamps 0.0–47.5 s; source video sha256 `5acbb9b5…9475e0` | train |

All 60 items are **training-side**. The remaining mazelab episodes (ep40–ep59)
were not touched and stay reserved. The docks clip is team-recorded corpus clip #1
and also feeds presentation material; per the programme's split discipline these
items are drawn from the shipped text-frame corpus (not from presentation cuts)
and are labelled `train`, never test — presentation cuts must not leak into test
splits, and nothing here is a test item.

## Verification — mazelab (teacher vs programmatic truth)

Every teacher fact and region label on the 40 mazelab items was checked
mechanically against truth derived from the episode grids (positions,
BFS path existence, cell census; the episodes' own question bank agrees).

- **Facts: 175/400 agree — 43.8%.**
- **Region labels (dominant class + contains, both must match): 195/480 — 40.6%.**

Per-predicate agreement (of 40):

| predicate | agree | | predicate | agree |
|---|---|---|---|---|
| west_of_agent | 32 (80%) | | goal_sealed | 20 (50%) |
| goal_position | 26 (65%) | | path_exists | 20 (50%) |
| agent_position | 24 (60%) | | manhattan_distance | 8 (20%) |
| agent_adjacent_walls | 24 (60%) | | wall_count | **0 (0%)** |
| goal_direction | 21 (52.5%) | | open_count | **0 (0%)** |

Three findings matter more than the headline rate:

1. **The teacher never saw a sealed goal.** 20 of the 40 episodes have a sealed
   goal; the teacher answered `goal_sealed: false` and `path_exists: true` on
   **all 40 items** — asserting connectivity everywhere, including every episode
   where no path exists. This is precisely the failure mode the v1/v2 reading
   experiments documented in *readers*; the pilot shows it in the *teacher* too.
   It is caught only because the gradebook verifies mechanically. Unverified
   teacher output must never be consumed as truth — that is the pilot's main
   result, and it is a result about the verification layer, not about MiniMax.
2. **Exact counts are estimates.** `wall_count` and `open_count` were wrong on
   40/40 items each (e.g. ep00: teacher 32 walls vs true 58). `manhattan_distance`
   was wrong on 32/40. The teacher reads magnitudes impressionistically; anything
   requiring enumeration needs either a procedure or a mechanical check.
3. **Recoverability self-knowledge ranks but does not calibrate.** Facts the
   teacher itself labelled `recoverable` were right 58.7% of the time (149/254);
   facts labelled `hard` only 17.8% (26/146); it never once used `unrecoverable`.
   The ordering is informative, the absolute confidence is not.

Verbatim disagreement examples (teacher → truth):

- ep00 `goal_direction`: `"SW"` → `"NW"` (agent row 3 col 7, goal row 1 col 2).
- ep00 `wall_count`: `32` → `58`; `open_count`: `67` → `41`.
- ep02 `agent_position`: `{"row": 5, "col": 5}` → `{"row": 5, "col": 4}` and
  `goal_position`: `{"row": 10, "col": 10}` → `{"row": 10, "col": 9}` — a
  systematic +1 column slip on that item.

Every item file carries the per-fact/per-region verification status and, on
disagreement, the true value. **Consumption rule:** downstream users should filter
on `verification.status == "agree"` (mazelab) or `"agreed_2pass"` (docks); the
rest of the teacher output is frozen for the record, labelled, and must not be
silently trusted.

## Self-consistency — docks (no truth exists)

Docks frames have no programmatic truth, so each item was taught **twice** at
temperature 0 and only agreeing entries were kept; disagreements were dropped
from the kept facts/labels and recorded with both pass values.

- **387/440 entries kept — 88.0% agreement; 53 dropped — 12.0% disagreement.**
- Drops concentrate in the extremal-region facts: `brightest_region` and
  `darkest_region` account for most fact drops (e.g. frame 105: brightest
  `r0c3` → `r0c0` between passes, darkest `r2c0` → `r2c3`; frame 135 the same
  corners flip). Boolean scene facts (water/boats/dock/rigging present) were
  stable across all 20 frames.
- Caveat: two passes of the *same* teacher share its biases. Self-consistency
  measures stability, not correctness — the sealed-goal result above shows a
  teacher can be stably wrong.

## Cost accounting

This lane was run deliberately at full size to spend the MiniMax subscription
(Casey's standing order: the quota is barely used — burn it on purpose).

- **Teacher calls: 80** (40 mazelab × 1 pass + 20 docks × 2 passes), all first
  attempts — zero retries, zero parse failures.
- **Tokens: 264,125 total** (prompt 204,615 + completion 59,510). Mazelab:
  69,753. Docks: 194,372 (the 148×80 tone frames dominate prompt volume).
- Wall time for the full batch: ~9.5 minutes at 4 concurrent calls.

## Reconciliation notes for the frozen schema draft

The pilot's working format (`gb_version: pilot-0.1`) was written before the v1
schema freeze; the schema lane will need to reconcile:

1. **Two-teacher rule.** The synthesis requires two *different* multimodal
   teachers to agree, with human arbitration on disagreement. The pilot used one
   teacher (MiniMax-Text-01, text frames only — no image input). Docks
   self-consistency is a weaker stand-in and is labelled as such in every item.
2. **Verification annotation shape.** Pilot items carry `verification.status`
   per fact/region with truth or pass values inlined. Whether the frozen schema
   keeps annotations inside the item (pilot choice — keeps the item
   self-describing) or in a sidecar verification file is an open schema call.
3. **Recoverability vocabulary.** 3-point scale as above; the teacher never used
   `unrecoverable` and its `recoverable` meant ~59% accurate. The frozen schema
   should either define calibration expectations per label or rename the labels
   to ranks rather than claims.
4. **Region grid.** Fixed 4×3 with band boundaries by `round(i·L/k)` over the
   frame. Must be aligned with shard 0011's canonical text frame definition
   before the gradebook and the kernel agree on what a region is.
5. **Docks plane choice.** Pilot items carry the tone plane only; the canonical
   text frame joins planes (glyph/tone/Braille). Which plane(s) a gradebook item
   freezes is a schema decision; multi-plane items will be larger.
6. **Fact vocabularies are per-source closed lists** (10 mazelab predicates,
   10 docks predicates) plus a closed failure-mode list for hints (4 maze, 3
   docks). The frozen schema needs a registry mechanism for these lists, or
   every new source forks the format.
7. **Hashing.** Item id = SHA-256 over canonical JSON (sorted keys, compact
   separators, UTF-8) of the item body excluding the id field. Manifest format
   itself is unfrozen.

## Layout

```
items/            60 content-addressed item JSONs (hash-named)
manifest.json     hashes, provenance, splits, verification + cost summary
manifest.sha256   sha256 of manifest.json
work/             builder + aggregator scripts, raw teacher responses (work/raw/),
                  build log, full disagreement list (in work/stats.json)
```
