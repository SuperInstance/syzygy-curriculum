# Reading guide — FROZEN v1 (written once, never edited during the run)

You are shown a top-down map of a maze as a grid of characters, one character per cell.

- '#' is a wall (impassable).
- '.' is free floor.
- 'A' is the agent (a robot) standing on a free cell.
- 'G' is the goal, on a free cell.

Rows are printed top to bottom; the top row is the north edge of the map. Columns run west (left) to east (right). North = toward the top of the grid, south = toward the bottom, west = left, east = right.

Distances count cells. "Adjacent" means the 4 cells directly north, south, east and west of a cell (not the diagonals). The agent can move north, south, east or west through free cells ('.', 'A', 'G'), but never through walls ('#').
