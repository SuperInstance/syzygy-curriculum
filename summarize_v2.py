#!/usr/bin/env python3
"""Summarize v1 vs v2 with the v1 filter rule (first successful record per
(reader, condition, episode); failed attempts kept in the logs, never scored).

Outputs scores_v2.json and prints the delta tables RESULTS-V2.md needs:
overall + per-question v1 -> v2, Q5 split by goal_sealed, Q4 error profile.
"""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
QIDS = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
CONDS = ['frame', 'blind', 'shuffled']


def load_scored(path):
    scored = {}
    n_fail = 0
    for l in open(path):
        try:
            r = json.loads(l)
        except Exception:
            continue
        key = (r['reader'], r['condition'], r['episode_id'])
        if r.get('error') is None and r.get('raw_output'):
            scored.setdefault(key, r)
        else:
            n_fail += 1
    return scored, n_fail


def stats(scored, truth, sealed):
    acc, acc_q, pf = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), defaultdict(int)
    q5_split = defaultdict(lambda: [0, 0])   # (reader, sealed?) -> [correct, total], frame only
    q4_err = defaultdict(list)               # reader -> list of (parsed-truth), frame only
    for (reader, cond, ep_id), r in sorted(scored.items()):
        for qid in QIDS:
            ok = bool(r['correct'][qid])
            acc[(reader, cond)][0] += ok
            acc[(reader, cond)][1] += 1
            acc_q[(reader, cond, qid)][0] += ok
            acc_q[(reader, cond, qid)][1] += 1
            if r['parsed'][qid] is None:
                pf[(reader, cond)] += 1
            if cond == 'frame' and qid == 'Q5':
                s = q5_split[(reader, sealed[ep_id])]
                s[0] += ok
                s[1] += 1
            if cond == 'frame' and qid == 'Q4' and r['parsed'][qid] is not None:
                q4_err[reader].append(int(r['parsed'][qid]) - int(truth[(ep_id, 'Q4')]))
    return acc, acc_q, pf, q5_split, q4_err


def pct(c, t):
    return round(c / t, 4) if t else None


def main():
    episodes = [json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))]
    sealed = {ep['episode_id']: bool(ep['goal_sealed']) for ep in episodes}
    questions = [json.loads(l) for l in open(os.path.join(HERE, 'questions.jsonl'))]
    truth = {(q['episode_id'], q['qid']): q['answer'] for q in questions}

    out = {}
    tables = {}
    for ver, fname in [('v1', 'reader_outputs.jsonl'), ('v2', 'reader_outputs_v2.jsonl')]:
        scored, n_fail = load_scored(os.path.join(HERE, fname))
        acc, acc_q, pf, q5_split, q4_err = stats(scored, truth, sealed)
        readers = sorted({k[0] for k in acc})
        d = {'n_scored': len(scored), 'n_failed_attempts': n_fail, 'accuracy': {},
             'per_question': {}, 'parse_failures': {}, 'lift': {},
             'q5_frame_split': {}, 'q4_frame_errors': {}}
        for reader in readers:
            d['accuracy'][reader] = {c: {'correct': acc[(reader, c)][0], 'total': acc[(reader, c)][1],
                                         'acc': pct(*acc[(reader, c)])} for c in CONDS}
            if d['accuracy'][reader]['frame']['acc'] is not None and d['accuracy'][reader]['blind']['acc'] is not None:
                d['lift'][reader] = round(d['accuracy'][reader]['frame']['acc'] -
                                          d['accuracy'][reader]['blind']['acc'], 4)
            d['per_question'][reader] = {c: {q: pct(*acc_q[(reader, c, q)]) for q in QIDS} for c in CONDS}
            d['parse_failures'][reader] = {c: pf.get((reader, c), 0) for c in CONDS}
            d['q5_frame_split'][reader] = {
                'sealed': {'correct': q5_split[(reader, True)][0], 'total': q5_split[(reader, True)][1],
                           'acc': pct(*q5_split[(reader, True)])},
                'unsealed': {'correct': q5_split[(reader, False)][0], 'total': q5_split[(reader, False)][1],
                             'acc': pct(*q5_split[(reader, False)])}}
            errs = q4_err.get(reader, [])
            if errs:
                d['q4_frame_errors'][reader] = {
                    'n_parsed': len(errs), 'exact': sum(1 for e in errs if e == 0),
                    'off_by_one': sum(1 for e in errs if abs(e) == 1),
                    'mean_abs_err': round(sum(abs(e) for e in errs) / len(errs), 3),
                    'max_abs_err': max(abs(e) for e in errs)}
        out[ver] = d
        tables[ver] = (acc, acc_q, pf)

    with open(os.path.join(HERE, 'scores_v2.json'), 'w') as f:
        json.dump(out, f, indent=1)

    for reader in ['glm', 'minimax']:
        print(f"\n===== {reader} =====")
        for ver in ['v1', 'v2']:
            a = out[ver]['accuracy'].get(reader)
            if not a:
                print(f" {ver}: no data")
                continue
            print(f" {ver}: frame {a['frame']['acc']:.3f} | blind {a['blind']['acc']:.3f} | "
                  f"shuffled {a['shuffled']['acc']:.3f} | LIFT {out[ver]['lift'].get(reader, float('nan')):+.3f} | "
                  f"fail-attempts {out[ver]['n_failed_attempts']}")
            pq = out[ver]['per_question'][reader]['frame']
            print(f"     frame per-Q: " + '  '.join(f"{q} {pq[q]:.3f}" for q in QIDS))
            s = out[ver]['q5_frame_split'][reader]
            print(f"     Q5 frame: sealed {s['sealed']['correct']}/{s['sealed']['total']} ({s['sealed']['acc']}) | "
                  f"unsealed {s['unsealed']['correct']}/{s['unsealed']['total']} ({s['unsealed']['acc']})")
            e = out[ver]['q4_frame_errors'].get(reader)
            if e:
                print(f"     Q4 frame errors: exact {e['exact']}/{e['n_parsed']}, off-by-one {e['off_by_one']}, "
                      f"mean|err| {e['mean_abs_err']}, max {e['max_abs_err']}")
            print(f"     parse failures: {out[ver]['parse_failures'][reader]}")


if __name__ == '__main__':
    main()
