# Question bank — FROZEN v1 (navigation purpose archetype; all answers derived from ground truth)

Q1 (goal bearing, 8-way choice):
"In which direction is the goal (G) from the agent (A)? (Answer with exactly one of: N, NE, E, SE, S, SW, W, NW)"
Truth: sign(goal_row-agent_row) -> S if positive, N if negative; sign(goal_col-agent_col) -> E if positive, W if negative; combined. North = decreasing row.

Q2 (adjacent wall count, integer 0-4):
"How many of the 4 cells directly adjacent to the agent (north, south, east, west) are walls (#)? (Answer with a single digit 0-4)"
Truth: count of 4-neighbours whose value grid cell is obstacle (1); out-of-bounds counts as wall (cannot occur: border is all walls and the agent is never on the border).

Q3 (wall to the west, yes/no):
"Is the cell immediately west (left) of the agent a wall (#)? (Answer yes or no)"
Truth: value grid at (agent_row, agent_col-1) is obstacle.

Q4 (Manhattan distance, integer):
"What is the Manhattan distance between the agent and the goal (counting steps north/south/east/west only, ignoring walls)? (Answer with a number)"
Truth: |goal_row-agent_row| + |goal_col-agent_col|.

Q5 (path exists, yes/no):
"Does any path exist from the agent to the goal moving only north/south/east/west through free cells (never through walls)? (Answer yes or no)"
Truth: BFS over non-obstacle cells from agent cell reaches goal cell.
