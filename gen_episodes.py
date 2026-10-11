#!/usr/bin/env python3
"""Generate the stage-1 reading-experiment episodes.

Reuses the vetted mazelab harness pattern (vetting/mazelab-capture/capture.py):
the clone is imported read-only via sys.path and never modified. Frame and
ground truth are two projections of one mazelab object, so pairing is exact.

For each episode: a seeded random_maze at a scheduled size/difficulty, agent
and goal placed on distinct free cells, the symbolic text frame (glyph
projection of to_name()), the full value grid, and the 5 frozen questions with
answers derived programmatically from the ground-truth grid — never from a
model.
"""
import sys, os, json
from collections import deque

import numpy as np

VET = os.path.expanduser('~/workspace/syzygy-program/vetting/mazelab')
sys.path.insert(0, VET)
from mazelab import BaseMaze, Object
from mazelab import DeepMindColor as color

# random_maze loaded directly (the generators package __init__ is broken by
# modern scikit-image; random_maze itself needs only numpy) — same as capture.py
import importlib.util
_spec = importlib.util.spec_from_file_location(
    'random_maze_mod', os.path.join(VET, 'mazelab/generators/random_maze.py'))
_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
random_maze = _mod.random_maze

HERE = os.path.dirname(os.path.abspath(__file__))
GLYPH = {'free': '.', 'obstacle': '#', 'agent': 'A', 'goal': 'G'}

# Difficulty schedule: (width, height) x (complexity, density), cycled.
SIZES = [(11, 9), (13, 11), (15, 13), (17, 15)]
PARAMS = [(0.3, 0.3), (0.5, 0.5), (0.7, 0.5), (0.5, 0.8), (0.8, 0.7)]
N_EPISODES = 60
SEED0 = 2000


def make_maze_class(x):
    class Maze(BaseMaze):
        @property
        def size(self):
            return x.shape

        def make_objects(self):
            free = Object('free', 0, color.free, False, np.stack(np.where(x == 0), axis=1))
            obstacle = Object('obstacle', 1, color.obstacle, True, np.stack(np.where(x == 1), axis=1))
            agent = Object('agent', 2, color.agent, False, [])
            goal = Object('goal', 3, color.goal, False, [])
            return free, obstacle, agent, goal
    return Maze


def text_frame(maze):
    names = maze.to_name()
    return '\n'.join(''.join(GLYPH[cell] for cell in row) for row in names)


def derive_answers(grid, agent, goal):
    """grid: 2D list of ints (0 free, 1 obstacle; agent/goal cells are 0 in the
    raw maze and placed on free cells). agent/goal: [row, col]."""
    ar, ac = agent
    gr, gc = goal
    H, W = len(grid), len(grid[0])

    def is_wall(r, c):
        if r < 0 or r >= H or c < 0 or c >= W:
            return True
        return grid[r][c] == 1

    # Q1: 8-way bearing
    dr, dc = gr - ar, gc - ac
    ns = 'S' if dr > 0 else 'N' if dr < 0 else ''
    ew = 'E' if dc > 0 else 'W' if dc < 0 else ''
    q1 = ns + ew

    # Q2: adjacent wall count
    q2 = sum(1 for (r, c) in [(ar - 1, ac), (ar + 1, ac), (ar, ac - 1), (ar, ac + 1)] if is_wall(r, c))

    # Q3: wall immediately west
    q3 = 'yes' if is_wall(ar, ac - 1) else 'no'

    # Q4: Manhattan distance
    q4 = str(abs(dr) + abs(dc))

    # Q5: path exists (BFS over non-wall cells)
    seen = {(ar, ac)}
    dq = deque([(ar, ac)])
    found = False
    while dq:
        r, c = dq.popleft()
        if (r, c) == (gr, gc):
            found = True
            break
        for nr, nc in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]:
            if (nr, nc) not in seen and not is_wall(nr, nc):
                seen.add((nr, nc))
                dq.append((nr, nc))
    q5 = 'yes' if found else 'no'

    return {'Q1': q1, 'Q2': str(q2), 'Q3': q3, 'Q4': q4, 'Q5': q5}


QUESTIONS = [
    ('Q1', "In which direction is the goal (G) from the agent (A)? (Answer with exactly one of: N, NE, E, SE, S, SW, W, NW)"),
    ('Q2', "How many of the 4 cells directly adjacent to the agent (north, south, east, west) are walls (#)? (Answer with a single digit 0-4)"),
    ('Q3', "Is the cell immediately west (left) of the agent a wall (#)? (Answer yes or no)"),
    ('Q4', "What is the Manhattan distance between the agent and the goal (counting steps north/south/east/west only, ignoring walls)? (Answer with a number)"),
    ('Q5', "Does any path exist from the agent to the goal moving only north/south/east/west through free cells (never through walls)? (Answer yes or no)"),
]


def gen_episode(i):
    seed = SEED0 + i
    width, height = SIZES[i % len(SIZES)]
    complexity, density = PARAMS[i % len(PARAMS)]
    np.random.seed(seed)  # random_maze uses the global RNG
    x = random_maze(width=width, height=height, complexity=complexity, density=density)
    rng = np.random.RandomState(seed * 31 + 7)

    free_cells = [tuple(p) for p in np.argwhere(x == 0)]
    min_dist = max(4, (x.shape[0] + x.shape[1]) // 4)
    agent = goal = None
    for _ in range(2000):
        a = free_cells[rng.randint(len(free_cells))]
        g = free_cells[rng.randint(len(free_cells))]
        if a != g and abs(a[0] - g[0]) + abs(a[1] - g[1]) >= min_dist:
            agent, goal = a, g
            break
    if agent is None:  # relax rather than fail
        a = free_cells[rng.randint(len(free_cells))]
        g = max(free_cells, key=lambda c: abs(c[0] - a[0]) + abs(c[1] - a[1]))
        agent, goal = a, g

    # Q5 repair: this generator's free space was connected in 60/60 pilot
    # episodes (Q5 would be constant 'yes', pure prior). For half the
    # episodes, seal the goal: wall its 4 neighbours in the raw grid BEFORE
    # the maze object (and hence the frame) is built, so frame and truth
    # stay paired by construction. Agent is >=4 cells away, so its own
    # neighbourhood (Q2/Q3) is untouched.
    goal_sealed = (i % 2 == 1)
    if goal_sealed:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            x[goal[0] + dr, goal[1] + dc] = 1

    Maze = make_maze_class(x)
    maze = Maze()
    maze.objects.agent.positions = [list(agent)]
    maze.objects.goal.positions = [list(goal)]
    frame = text_frame(maze)
    grid = x.astype(int).tolist()  # raw maze grid: 0 free / 1 obstacle (agent+goal stand on free cells)
    answers = derive_answers(grid, list(agent), list(goal))

    ep = {
        'episode_id': f'ep{i:02d}',
        'seed': seed,
        'width': int(x.shape[1]),
        'height': int(x.shape[0]),
        'complexity': complexity,
        'density': density,
        'agent_pos': [int(agent[0]), int(agent[1])],
        'goal_pos': [int(goal[0]), int(goal[1])],
        'goal_sealed': goal_sealed,
        'frame': frame,
        'value_grid': grid,
    }
    qs = [{'episode_id': ep['episode_id'], 'qid': qid, 'question': qtext, 'answer': answers[qid]}
          for qid, qtext in QUESTIONS]
    return ep, qs


def main():
    episodes, questions = [], []
    for i in range(N_EPISODES):
        ep, qs = gen_episode(i)
        episodes.append(ep)
        questions.extend(qs)
        # sanity: frame contains exactly one A and one G, and they sit at the recorded positions
        rows = ep['frame'].split('\n')
        assert rows[ep['agent_pos'][0]][ep['agent_pos'][1]] == 'A', ep['episode_id']
        assert rows[ep['goal_pos'][0]][ep['goal_pos'][1]] == 'G', ep['episode_id']
        assert ep['frame'].count('A') == 1 and ep['frame'].count('G') == 1
    with open(os.path.join(HERE, 'episodes.jsonl'), 'w') as f:
        for ep in episodes:
            f.write(json.dumps(ep) + '\n')
    with open(os.path.join(HERE, 'questions.jsonl'), 'w') as f:
        for q in questions:
            f.write(json.dumps(q) + '\n')
    from collections import Counter
    for qid in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
        dist = Counter(q['answer'] for q in questions if q['qid'] == qid)
        print(qid, dict(sorted(dist.items())))
    print(f"wrote {len(episodes)} episodes, {len(questions)} questions")


if __name__ == '__main__':
    main()
