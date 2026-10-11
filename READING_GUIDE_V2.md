# Reading guide — v2 (vocabulary from frozen v1 + procedures & worked example; the v2 treatment)

You are shown a top-down map of a maze as a grid of characters, one character per cell.

- '#' is a wall (impassable).
- '.' is free floor.
- 'A' is the agent (a robot) standing on a free cell.
- 'G' is the goal, on a free cell.

Rows are printed top to bottom; the top row is the north edge of the map. Columns run west (left) to east (right). North = toward the top of the grid, south = toward the bottom, west = left, east = right.

Distances count cells. "Adjacent" means the 4 cells directly north, south, east and west of a cell (not the diagonals). The agent can move north, south, east or west through free cells ('.', 'A', 'G'), but never through walls ('#').

## How to answer: check first, then answer

Do not answer any question from a first impression. For EVERY question, first write your checks as "Work" lines, then write the answer line. The checks are how you know; the answer line is only the result.

- A Work line starts with the word Work and the question label, like this: `Work Q4: ...`
- After a question's Work lines, write its answer line in exactly this form: `Q4: <answer>`
- Answer the questions in order, Q1 to Q5, each with its own Work lines and answer line.

To locate cells, number the rows from the top starting at 1, and the columns from the left starting at 1. A cell is named (row, column). First find A and G: scan the map row by row and note each one's row and column.

## Procedure for each question

**Q1 — direction of G from A.** In your Work line, state A's (row, column) and G's (row, column). Then state the row difference (G's row minus A's row): if it is positive, G is SOUTH of A; if negative, NORTH; if zero, same row. Then state the column difference (G's column minus A's column): positive means EAST, negative means WEST, zero means same column. Combine the two parts (for example south + east = SE; same row + east = E) and answer with the combined direction.

**Q2 — how many of A's 4 adjacent cells are walls.** Check the four neighbours ONE AT A TIME and name each in your Work line: the cell north of A — write what character it is and whether it is a wall; then south; then east; then west. Then total the walls and answer with the total (a single digit 0-4).

**Q3 — is the cell west of A a wall.** Look at exactly one cell: the one west (left) of A. Name it in your Work line. Answer yes if it is '#', no if it is '.' or 'G'.

**Q4 — Manhattan distance from A to G.** Count it in steps, out loud, in your Work line. First count the row steps: starting at A's row, step one row at a time toward G's row, tallying each step (1, 2, 3, ...) until you reach G's row. Then count the column steps the same way, from A's column to G's column. Add the two tallies and answer with the sum. Never guess the distance from how far apart A and G look — always count the steps.

**Q5 — does a path exist from A to G.** Do this in two stages, and NEVER answer yes from a general impression that the map "looks connected".
- Stage 1 — inspect the goal first. In your Work line, name the four cells adjacent to G (north, south, east, west) and what each one is. If ALL FOUR are walls '#', the goal is sealed in: answer no, and stop — no route tracing is needed.
- Stage 2 — if any neighbour of G is open, trace a route. In your Work lines, walk step by step from A: each step names the direction (N, S, E or W) and the (row, column) you land on, and you may only step onto '.', 'A' or 'G' cells — never '#'. Keep going until you land on G or you are stuck. If you get stuck, go back to an earlier cell in your route and try a different direction. Answer yes ONLY if your written route actually reaches G; if every route you trace gets stuck, answer no.

## Worked example

Map:
```
#########
#.......#
#.##.##.#
#..A....#
#.##.##.#
#....G..#
#########
```

Work Q1: A is at (row 4, column 4). G is at (row 6, column 6). Row difference: 6 - 4 = +2, positive, so G is SOUTH of A. Column difference: 6 - 4 = +2, positive, so G is EAST of A. South + east = SE.
Q1: SE
Work Q2: Neighbours of A (row 4, column 4): north cell (row 3, column 4) is '#' — wall. South cell (row 5, column 4) is '#' — wall. East cell (row 4, column 5) is '.' — open. West cell (row 4, column 3) is '.' — open. Total walls: 2.
Q2: 2
Work Q3: The cell west of A is (row 4, column 3), which is '.', not a wall.
Q3: no
Work Q4: Row steps from A's row 4 toward G's row 6: step 1 -> row 5, step 2 -> row 6. That is 2 row steps. Column steps from A's column 4 toward G's column 6: step 1 -> column 5, step 2 -> column 6. That is 2 column steps. Total: 2 + 2 = 4.
Q4: 4
Work Q5: Stage 1 — neighbours of G (row 6, column 6): north (row 5, column 6) is '#' — wall. South (row 7, column 6) is '#' — wall. East (row 6, column 7) is '.' — open. West (row 6, column 5) is '.' — open. Not all four are walls, so G is not sealed. Stage 2 — route from A (row 4, column 4): step 1 E to (row 4, column 5), '.'. Step 2 S to (row 5, column 5), '.'. Step 3 S to (row 6, column 5), '.'. Step 4 E to (row 6, column 6) — that is G. The written route reaches G.
Q5: yes

## Standing rules

- No written route reaching G, no "yes" on Q5.
- No step-by-step tally, no number on Q4.
- No named neighbours, no count on Q2.
- If you cannot complete a check, say so in the Work line and still give your best answer on the answer line.
