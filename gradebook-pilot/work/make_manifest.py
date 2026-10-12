#!/usr/bin/env python3
"""Aggregate pilot stats -> manifest.json (+ sha256 sidecar) and README.md."""
import collections
import glob
import hashlib
import json
import os

PILOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
items = {}
for p in sorted(glob.glob(os.path.join(PILOT, "items", "*.json"))):
    it = json.load(open(p))
    items[it["item_id"]] = it
st = json.load(open(os.path.join(PILOT, "work", "stats.json")))
res = st["results"]

maze_items = {k: v for k, v in res.items() if k.startswith("maze")}
docks_items = {k: v for k, v in res.items() if k.startswith("docks")}

def pct(a, b):
    return round(a / b, 4) if b else None

fa = sum(v["stats"]["facts_agree"] for v in maze_items.values())
fd = sum(v["stats"]["facts_disagree"] for v in maze_items.values())
ra = sum(v["stats"]["regions_agree"] for v in maze_items.values())
rd = sum(v["stats"]["regions_disagree"] for v in maze_items.values())
kept = sum(v["stats"]["kept"] for v in docks_items.values())
dropped = sum(v["stats"]["dropped"] for v in docks_items.values())

per_pred = collections.defaultdict(lambda: [0, 0])
for it in items.values():
    if it["source"]["kind"] != "mazelab_episode":
        continue
    for f in it["facts"]:
        v = f["verification"]
        if v["status"] == "agree":
            per_pred[f["predicate"]][0] += 1
        elif v["status"] == "disagree":
            per_pred[f["predicate"]][1] += 1
per_pred = {k: {"agree": a, "disagree": d, "rate": pct(a, a + d)}
            for k, (a, d) in sorted(per_pred.items())}

docks_drop_pred = collections.Counter()
for d in st["disagreements"]:
    if d["kind"] == "fact" and "pass1" in d:
        docks_drop_pred[d["predicate"]] += 1

def tok_split(u):
    if isinstance(u, list):
        return (sum(x.get("prompt_tokens", 0) for x in u if x),
                sum(x.get("completion_tokens", 0) for x in u if x))
    if u:
        return u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    return 0, 0

mp = mc = dp = dc = 0
for v in maze_items.values():
    a, b = tok_split(v["stats"]["usage"]); mp += a; mc += b
for v in docks_items.values():
    a, b = tok_split(v["stats"]["usage"]); dp += a; dc += b
calls = sum(v["stats"]["attempts"] if isinstance(v["stats"]["attempts"], int)
            else sum(x for x in v["stats"]["attempts"] if x)
            for v in res.values())

manifest_items = []
for key in sorted(res):
    v = res[key]
    if "item_id" not in v:
        continue
    it = items[v["item_id"]]
    entry = {"item_id": v["item_id"], "file": f"items/{v['item_id']}.json",
             "key": key, "source": it["source"], "split": it["split"],
             "frame": {k: it["frame"][k] for k in ("format", "plane", "cols", "rows")}}
    if key.startswith("maze"):
        s = v["stats"]
        entry["verification"] = {"mode": "programmatic_truth",
                                 "facts_agree": s["facts_agree"],
                                 "facts_disagree": s["facts_disagree"],
                                 "regions_agree": s["regions_agree"],
                                 "regions_disagree": s["regions_disagree"]}
    else:
        s = v["stats"]
        entry["verification"] = {"mode": "two_pass_self_consistency",
                                 "kept": s["kept"], "dropped": s["dropped"]}
    manifest_items.append(entry)

manifest = {
    "gb_version": "pilot-0.1",
    "created": "2026-10-12",
    "teacher": {"model": "MiniMax-Text-01", "via": "minimax skill bin/chat.py chat()",
                "temperature": 0.0,
                "passes": {"mazelab_episode": 1, "docks_text_frame": 2}},
    "corpus": {
        "mazelab": {"episodes": "ep00-ep39 (first 40 of 60 in episodes.jsonl)",
                    "count": 40, "split": "train",
                    "held_out_untouched": "ep40-ep59",
                    "provenance": "syzygy-program/reading-experiment/episodes.jsonl"},
        "docks": {"frame_indices": [i * 15 for i in range(20)], "count": 20,
                  "plane": "tone", "fps": 6, "split": "train",
                  "provenance": "syzygy-video/out/docks-text/tone/",
                  "source_video_sha256":
                      "5acbb9b592d6c5b15d516318b6e1a5b534fc55c36b5c71656c79d8a9539475e0"},
    },
    "verification_summary": {
        "mazelab_facts": {"agree": fa, "disagree": fd, "rate": pct(fa, fa + fd)},
        "mazelab_regions": {"agree": ra, "disagree": rd, "rate": pct(ra, ra + rd)},
        "mazelab_per_predicate": per_pred,
        "mazelab_sealed_goal": {"truly_sealed_items": 20,
                                "teacher_detected_sealed": 0,
                                "teacher_path_exists_true": 40,
                                "items_total": 40},
        "docks_consistency": {"kept": kept, "dropped": dropped,
                              "agreement_rate": pct(kept, kept + dropped),
                              "disagreement_rate": pct(dropped, kept + dropped),
                              "dropped_by_predicate": dict(docks_drop_pred)},
    },
    "cost": {"teacher_calls": calls, "retries_beyond_first_attempt": 0,
             "tokens": {"mazelab": {"prompt": mp, "completion": mc, "total": mp + mc},
                        "docks": {"prompt": dp, "completion": dc, "total": dp + dc},
                        "total": mp + mc + dp + dc},
             "wall_s_full_batch": st["wall_s"]},
    "items": manifest_items,
}
mpath = os.path.join(PILOT, "manifest.json")
with open(mpath, "w") as f:
    json.dump(manifest, f, indent=1)
mh = hashlib.sha256(open(mpath, "rb").read()).hexdigest()
with open(os.path.join(PILOT, "manifest.sha256"), "w") as f:
    f.write(f"{mh}  manifest.json\n")
print("manifest sha256:", mh)
print(json.dumps(manifest["verification_summary"], indent=1)[:600])
print("cost:", json.dumps(manifest["cost"]))
