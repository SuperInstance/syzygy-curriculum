#!/usr/bin/env python3
"""Syzygy gradebook pilot builder.

Teacher = MiniMax-Text-01 via the minimax skill's own chat() (same surrogate
credential path as bin/chat.py; imported so temperature can be set to 0).
Mazelab items: teacher facts verified mechanically against programmatic truth.
Docks items: no truth — two teacher passes at temperature 0, only agreeing
facts/labels kept; disagreement rate recorded.
Output: content-addressed items in ../items/, manifest.json, stats.json.
Raw teacher responses checkpointed in work/raw/ (reruns resume).
"""
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
ITEMS_DIR = os.path.join(PILOT, "items")
RAW_DIR = os.path.join(HERE, "raw")
EPISODES = os.path.expanduser("~/workspace/syzygy-program/reading-experiment/episodes.jsonl")
QUESTIONS = os.path.expanduser("~/workspace/syzygy-program/reading-experiment/questions.jsonl")
DOCKS_TONE = os.path.expanduser("~/workspace/syzygy-video/out/docks-text/tone")
DOCKS_SOURCE = "~/workspace/user/media_library/video/5a/5acbb9b592d6c5b15d516318b6e1a5b534fc55c36b5c71656c79d8a9539475e0.mp4"
DOCKS_SOURCE_SHA256 = "5acbb9b592d6c5b15d516318b6e1a5b534fc55c36b5c71656c79d8a9539475e0"
MODEL = "MiniMax-Text-01"
TEMPERATURE = 0.0

spec = importlib.util.spec_from_file_location(
    "minimax_chat", os.path.expanduser("~/workspace/skills/minimax/bin/chat.py"))
mm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mm)

os.makedirs(ITEMS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# ---------------------------------------------------------------- maze truth
def maze_truth(ep):
    grid = ep["value_grid"]
    ar, ac = ep["agent_pos"]          # [row, col]
    gr, gc = ep["goal_pos"]
    H, W = len(grid), len(grid[0])
    def cell(r, c):
        return grid[r][c] if 0 <= r < H and 0 <= c < W else 1
    dr, dc = gr - ar, gc - ac
    vert = "N" if dr < 0 else ("S" if dr > 0 else "")
    horiz = "W" if dc < 0 else ("E" if dc > 0 else "")
    direction = (vert + horiz) or "HERE"
    adj = sum(cell(ar + d[0], ac + d[1]) for d in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    # BFS path exists
    seen = {(ar, ac)}
    dq = deque([(ar, ac)])
    path = False
    while dq:
        r, c = dq.popleft()
        if (r, c) == (gr, gc):
            path = True
            break
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + d[0], c + d[1]
            if 0 <= nr < H and 0 <= nc < W and grid[nr][nc] == 0 and (nr, nc) not in seen:
                seen.add((nr, nc))
                dq.append((nr, nc))
    walls = sum(sum(row) for row in grid)
    return {
        "agent_position": {"row": ar, "col": ac},
        "goal_position": {"row": gr, "col": gc},
        "goal_direction": direction,
        "manhattan_distance": abs(dr) + abs(dc),
        "agent_adjacent_walls": adj,
        "west_of_agent": "wall" if cell(ar, ac - 1) == 1 else "free",
        "path_exists": path,
        "goal_sealed": ep["goal_sealed"],
        "wall_count": walls,
        "open_count": H * W - walls,
    }

def band_bounds(length, k):
    return [(round(i * length / k), round((i + 1) * length / k)) for i in range(k)]

def maze_region_truth(ep):
    grid = ep["value_grid"]
    H, W = len(grid), len(grid[0])
    rb = band_bounds(H, 3)
    cb = band_bounds(W, 4)
    out = {}
    for ri, (r0, r1) in enumerate(rb):
        for ci, (c0, c1) in enumerate(cb):
            cells = [grid[r][c] for r in range(r0, r1) for c in range(c0, c1)]
            frac = sum(cells) / len(cells)
            dom = "wall" if frac >= 0.6 else ("open" if frac <= 0.4 else "mixed")
            contains = []
            if r0 <= ep["agent_pos"][0] < r1 and c0 <= ep["agent_pos"][1] < c1:
                contains.append("agent")
            if r0 <= ep["goal_pos"][0] < r1 and c0 <= ep["goal_pos"][1] < c1:
                contains.append("goal")
            out[f"r{ri}c{ci}"] = {"dominant": dom, "contains": sorted(contains),
                                  "rows": [r0, r1], "cols": [c0, c1]}
    return out

# ---------------------------------------------------------------- prompts
MAZE_SYSTEM = (
    "You are the TEACHER in the Syzygy gradebook pilot. You examine one text frame and "
    "produce frozen teaching material: checkable facts, per-fact recoverability judgements, "
    "region appearance labels, and reader hints. Be exact — your output is verified "
    "mechanically. Respond with ONE JSON object only: no prose, no commentary."
)
MAZE_FACTS = [
    "agent_position", "goal_position", "goal_direction", "manhattan_distance",
    "agent_adjacent_walls", "west_of_agent", "path_exists", "goal_sealed",
    "wall_count", "open_count",
]

def maze_prompt(ep):
    return f"""Here is a maze as a text frame. Legend: '#' = wall, '.' = open floor, 'A' = agent, 'G' = goal.
Coordinates: row 0 is the TOP line, col 0 is the LEFTMOST character. The frame is {ep['height']} rows x {ep['width']} cols.

```
{ep['frame']}
```

Produce a JSON object with exactly these keys:

"facts": a list with ONE entry per predicate below, each {{"predicate": <name>, "value": <value>, "recoverability": <one of "recoverable", "hard", "unrecoverable">}}.
Recoverability = your judgement of whether a careful reader given ONLY this text frame could derive the fact: "recoverable" = directly readable/countable, "hard" = derivable but error-prone, "unrecoverable" = not derivable from the frame alone.
Predicates and value formats:
- "agent_position": {{"row": <int>, "col": <int>}}
- "goal_position": {{"row": <int>, "col": <int>}}
- "goal_direction": one of "N","NE","E","SE","S","SW","W","NW" — the compass direction of G from A
- "manhattan_distance": <int> steps between A and G ignoring walls
- "agent_adjacent_walls": <int 0-4>, how many of the 4 cells directly adjacent to A are walls
- "west_of_agent": "wall" or "free" — the cell immediately left of A
- "path_exists": true/false — a 4-directional path from A to G through open cells only
- "goal_sealed": true/false — every cell adjacent to G is a wall or outside the frame
- "wall_count": <int> total '#' cells in the frame
- "open_count": <int> total non-'#' cells (floor plus A and G cells)

"region_labels": divide the frame into 4 columns x 3 rows of roughly equal regions, named "r<row>c<col>" (row 0 top, col 0 left). One entry per region (12 total): {{"region": "r0c0", "dominant": "wall"|"open"|"mixed", "contains": []}} where "contains" lists "agent" and/or "goal" if that marker is in the region (empty list otherwise). "dominant" = what most of the region's cells are.

"hints": 1 or 2 entries {{"failure_mode": <one of "sealed_goal_assertion", "wall_count_constant_guess", "distance_guessing", "direction_slip">, "hint": "<one line>"}}. Each hint is one line of advice to a future reader of THIS maze, targeting that known reader failure mode where it is relevant to this maze (e.g. for sealed_goal_assertion: warn to inspect the goal's own doorstep before claiming a path exists; for wall_count_constant_guess: warn to count cell by cell rather than answering a typical number)."""

DOCKS_SYSTEM = (
    "You are the TEACHER in the Syzygy gradebook pilot. You examine one text frame rendered "
    "from a harbour photograph (a tone plane: characters from ' ' and '.' up to '@', brighter "
    "character = brighter area) and produce frozen teaching material: structured facts, "
    "per-fact recoverability judgements, region appearance labels, and reader hints. "
    "Respond with ONE JSON object only: no prose, no commentary."
)
DOCKS_FACTS = [
    "brightest_region", "darkest_region", "horizon_visible", "water_present",
    "boats_present", "dock_structure_present", "signage_present",
    "rigging_or_masts_present", "dominant_content", "overall_brightness",
]

def docks_prompt(frame_text, idx, cols, rows):
    return f"""Here is frame {idx} of a first-person walk along a harbour dock, rendered as a {rows}-row x {cols}-col character tone plane. Bright characters (@ % #) are bright areas (sky, glare, lit surfaces); sparse characters (space, '.') are dark areas. Boats, masts, rigging, dock decking, water and sky may be present. Read the frame as a picture made of characters.

```
{frame_text}
```

Produce a JSON object with exactly these keys:

"facts": a list with ONE entry per predicate below, each {{"predicate": <name>, "value": <value>, "recoverability": <one of "recoverable", "hard", "unrecoverable">}}.
Recoverability = whether a careful reader given ONLY this text frame could derive the fact.
Predicates and value formats:
- "brightest_region": region id (see region grid below) with the brightest content
- "darkest_region": region id with the darkest content
- "horizon_visible": true/false — a horizon line (sky/water or sky/land boundary) can be seen
- "water_present": true/false
- "boats_present": true/false
- "dock_structure_present": true/false — decking, pilings, piers, walkways
- "signage_present": true/false — any readable letters or numbers formed in the frame
- "rigging_or_masts_present": true/false — masts, rigging lines, spars
- "dominant_content": one of "water", "boats", "dock", "sky", "mixed"
- "overall_brightness": one of "bright", "mid", "dark"

"region_labels": divide the frame into 4 columns x 3 rows of roughly equal regions, named "r<row>c<col>" (row 0 top, col 0 left). One entry per region (12 total): {{"region": "r0c0", "appearance": <one of "bright_open", "mid_texture", "dark_mass", "vertical_lines", "horizontal_bands", "mixed">}}.

"hints": 1 or 2 entries {{"failure_mode": <one of "confabulated_tally", "bright_flat_misread", "saturation_blindness">, "hint": "<one line>"}}. Each hint is one line of advice to a future reader of THIS frame, targeting that known failure mode where relevant (confabulated_tally: do not invent counts — say what region a thing is in instead; bright_flat_misread: bright flat areas are glare/sky/water, not busy structure; saturation_blindness: the brightest close-ups wash out detail — distrust fine structure there)."""

# ---------------------------------------------------------------- teacher io
def parse_json(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        return json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            return json.loads(t[i:j + 1])
        raise

def teacher_call(key, system, prompt, max_tokens=3000):
    raw_path = os.path.join(RAW_DIR, key + ".json")
    if os.path.exists(raw_path):
        return json.load(open(raw_path))
    last = None
    for attempt in range(3):
        try:
            data = mm.chat(
                [{"role": "system", "content": system},
                 {"role": "user", "content": prompt}],
                model=MODEL, max_tokens=max_tokens, temperature=TEMPERATURE)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = parse_json(content)
            rec = {"content": content, "parsed": parsed,
                   "usage": data.get("usage"), "attempts": attempt + 1,
                   "model": data.get("model", MODEL)}
            with open(raw_path, "w") as f:
                json.dump(rec, f)
            return rec
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{key}: teacher call failed: {last}")

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def item_hash(body):
    return hashlib.sha256(canon(body).encode()).hexdigest()

# ---------------------------------------------------------------- build: maze
def build_maze_item(ep):
    key = f"maze_{ep['episode_id']}"
    rec = teacher_call(key, MAZE_SYSTEM, maze_prompt(ep))
    t = rec["parsed"]
    truth = maze_truth(ep)
    rtruth = maze_region_truth(ep)
    facts, fa, fd = [], 0, 0
    disagreements = []
    tmap = {f["predicate"]: f for f in t.get("facts", [])}
    for pred in MAZE_FACTS:
        tf = tmap.get(pred)
        if tf is None:
            facts.append({"predicate": pred, "value": None, "recoverability": None,
                          "verification": {"status": "missing_from_teacher_output",
                                           "truth": truth[pred]}})
            fd += 1
            disagreements.append({"item": key, "kind": "fact", "predicate": pred,
                                  "teacher": None, "truth": truth[pred]})
            continue
        agree = tf.get("value") == truth[pred]
        fa, fd = fa + agree, fd + (not agree)
        if not agree:
            disagreements.append({"item": key, "kind": "fact", "predicate": pred,
                                  "teacher": tf.get("value"), "truth": truth[pred]})
        facts.append({"predicate": pred, "value": tf.get("value"),
                      "recoverability": tf.get("recoverability"),
                      "verification": {"status": "agree" if agree else "disagree",
                                       "truth": truth[pred]}})
    regions, ra, rd = [], 0, 0
    trmap = {r["region"]: r for r in t.get("region_labels", [])}
    for rid in [f"r{r}c{c}" for r in range(3) for c in range(4)]:
        tr = trmap.get(rid)
        rt = rtruth[rid]
        if tr is None:
            regions.append({"region": rid, "dominant": None, "contains": None,
                            "verification": {"status": "missing_from_teacher_output",
                                             "truth": rt}})
            rd += 1
            continue
        dom_ok = tr.get("dominant") == rt["dominant"]
        cont_ok = sorted(tr.get("contains", [])) == rt["contains"]
        ok = dom_ok and cont_ok
        ra, rd = ra + ok, rd + (not ok)
        if not ok:
            disagreements.append({"item": key, "kind": "region", "region": rid,
                                  "teacher": {"dominant": tr.get("dominant"),
                                              "contains": tr.get("contains")},
                                  "truth": {"dominant": rt["dominant"],
                                            "contains": rt["contains"]}})
        regions.append({"region": rid, "dominant": tr.get("dominant"),
                        "contains": sorted(tr.get("contains", [])),
                        "cell_range": {"rows": rt["rows"], "cols": rt["cols"]},
                        "verification": {"status": "agree" if ok else "disagree",
                                         "dominant_ok": dom_ok, "contains_ok": cont_ok,
                                         "truth": {"dominant": rt["dominant"],
                                                   "contains": rt["contains"]}}})
    body = {
        "gb_version": "pilot-0.1",
        "source": {"kind": "mazelab_episode", "episode_id": ep["episode_id"],
                   "seed": ep["seed"],
                   "provenance": "syzygy-program/reading-experiment/episodes.jsonl"},
        "split": "train",
        "frame": {"format": "text", "plane": "glyph", "cols": ep["width"],
                  "rows": ep["height"], "text": ep["frame"]},
        "teacher": {"model": MODEL, "role": "teacher", "passes": 1,
                    "temperature": TEMPERATURE},
        "facts": facts,
        "region_labels": regions,
        "hints": t.get("hints", []),
    }
    h = item_hash(body)
    item = {"item_id": h, **body}
    stats = {"facts_agree": fa, "facts_disagree": fd,
             "regions_agree": ra, "regions_disagree": rd,
             "usage": rec.get("usage"), "attempts": rec.get("attempts")}
    return item, stats, disagreements

# ---------------------------------------------------------------- build: docks
def build_docks_item(idx):
    path = os.path.join(DOCKS_TONE, f"frame_{idx:04d}.txt")
    lines = open(path).read().splitlines()
    header = lines[0] if lines and lines[0].startswith("#") else ""
    frame_lines = lines[1:] if header else lines
    frame_text = "\n".join(frame_lines)
    rows = len(frame_lines)
    cols = len(frame_lines[0]) if frame_lines else 0
    prompt = docks_prompt(frame_text, idx, cols, rows)
    recs = [teacher_call(f"docks_{idx:04d}_p{p}", DOCKS_SYSTEM, prompt) for p in (1, 2)]
    p1, p2 = recs[0]["parsed"], recs[1]["parsed"]
    m1 = {f["predicate"]: f for f in p1.get("facts", [])}
    m2 = {f["predicate"]: f for f in p2.get("facts", [])}
    facts, kept, dropped = [], 0, 0
    disagreements = []
    for pred in DOCKS_FACTS:
        f1, f2 = m1.get(pred), m2.get(pred)
        v1 = f1.get("value") if f1 else None
        v2 = f2.get("value") if f2 else None
        agree = f1 is not None and f2 is not None and v1 == v2
        if agree:
            kept += 1
        else:
            dropped += 1
            disagreements.append({"item": f"docks_{idx:04d}", "kind": "fact",
                                  "predicate": pred, "pass1": v1, "pass2": v2})
        facts.append({"predicate": pred, "value": v1 if agree else None,
                      "recoverability": f1.get("recoverability") if f1 else None,
                      "verification": {"status": "agreed_2pass" if agree else "dropped_disagreement",
                                       "pass_values": [v1, v2],
                                       "truth": None, "note": "no programmatic truth; teacher-only"}})
    r1 = {r["region"]: r for r in p1.get("region_labels", [])}
    r2 = {r["region"]: r for r in p2.get("region_labels", [])}
    regions = []
    for rid in [f"r{r}c{c}" for r in range(3) for c in range(4)]:
        a1 = r1.get(rid, {}).get("appearance")
        a2 = r2.get(rid, {}).get("appearance")
        agree = a1 is not None and a1 == a2
        if agree:
            kept += 1
        else:
            dropped += 1
            disagreements.append({"item": f"docks_{idx:04d}", "kind": "region",
                                  "region": rid, "pass1": a1, "pass2": a2})
        regions.append({"region": rid, "appearance": a1 if agree else None,
                        "verification": {"status": "agreed_2pass" if agree else "dropped_disagreement",
                                         "pass_values": [a1, a2],
                                         "note": "no programmatic truth; teacher-only"}})
    body = {
        "gb_version": "pilot-0.1",
        "source": {"kind": "docks_text_frame", "frame_index": idx,
                   "plane": "tone", "fps": 6, "timestamp_s": round(idx / 6.0, 3),
                   "frame_header": header,
                   "corpus_file": f"syzygy-video/out/docks-text/tone/frame_{idx:04d}.txt",
                   "source_video": DOCKS_SOURCE,
                   "source_video_sha256": DOCKS_SOURCE_SHA256},
        "split": "train",
        "frame": {"format": "text", "plane": "tone", "cols": cols, "rows": rows,
                  "text": frame_text},
        "teacher": {"model": MODEL, "role": "teacher", "passes": 2,
                    "temperature": TEMPERATURE},
        "facts": facts,
        "region_labels": regions,
        "hints": p1.get("hints", []),
        "hints_pass2": p2.get("hints", []),
    }
    h = item_hash(body)
    item = {"item_id": h, **body}
    stats = {"kept": kept, "dropped": dropped,
             "usage": [r.get("usage") for r in recs],
             "attempts": [r.get("attempts") for r in recs]}
    return item, stats, disagreements

# ---------------------------------------------------------------- main
def main():
    eps = [json.loads(l) for l in open(EPISODES)][:40]
    docks_idx = [i * 15 for i in range(20)]  # 0,15,...,285 of 297
    jobs = []
    for ep in eps:
        jobs.append((f"maze_{ep['episode_id']}", lambda ep=ep: build_maze_item(ep)))
    for idx in docks_idx:
        jobs.append((f"docks_{idx:04d}", lambda idx=idx: build_docks_item(idx)))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        jobs = [j for j in jobs if only in j[0]]
    results = {}
    disagreements = []
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn): key for key, fn in jobs}
        for fut in cf.as_completed(futs):
            key = futs[fut]
            try:
                item, stats, dis = fut.result()
                with open(os.path.join(ITEMS_DIR, item["item_id"] + ".json"), "w") as f:
                    json.dump(item, f, indent=1)
                results[key] = {"item_id": item["item_id"], "stats": stats,
                                "source": item["source"], "split": item["split"]}
                disagreements.extend(dis)
                print(f"OK {key} {item['item_id'][:12]}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {key}: {e}", flush=True)
                results[key] = {"error": str(e)}
    stats_out = {"results": results, "disagreements": disagreements,
                 "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(HERE, "stats.json"), "w") as f:
        json.dump(stats_out, f, indent=1)
    print(f"done: {len(results)} jobs, {stats_out['wall_s']}s", flush=True)

if __name__ == "__main__":
    main()
