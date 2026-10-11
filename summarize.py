#!/usr/bin/env python3
"""Summarize reader_outputs.jsonl into scores.json + a printed table.

Filter rule (stated in RESULTS.md): for each (reader, condition, episode),
the first record with error=None and non-empty raw_output is the scored one;
failed attempts are kept in the log for honesty but never scored.
"""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
QIDS = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']


def main():
    recs = [json.loads(l) for l in open(os.path.join(HERE, 'reader_outputs.jsonl'))]
    scored = {}
    n_fail = 0
    for r in recs:
        key = (r['reader'], r['condition'], r['episode_id'])
        if r.get('error') is None and r.get('raw_output'):
            scored.setdefault(key, r)
        else:
            n_fail += 1

    questions = [json.loads(l) for l in open(os.path.join(HERE, 'questions.jsonl'))]
    truth = {(q['episode_id'], q['qid']): q['answer'] for q in questions}

    # accuracy[(reader, condition)] = [correct, total]; per-question too
    acc = defaultdict(lambda: [0, 0])
    acc_q = defaultdict(lambda: [0, 0])
    parse_fail = defaultdict(int)
    failures = []  # frame-condition failures, for RESULTS.md quotes
    for (reader, cond, ep_id), r in sorted(scored.items()):
        for qid in QIDS:
            ok = bool(r['correct'][qid])
            acc[(reader, cond)][0] += ok
            acc[(reader, cond)][1] += 1
            acc_q[(reader, cond, qid)][0] += ok
            acc_q[(reader, cond, qid)][1] += 1
            if r['parsed'][qid] is None:
                parse_fail[(reader, cond)] += 1
            if cond == 'frame' and not ok:
                failures.append({'reader': reader, 'episode_id': ep_id, 'qid': qid,
                                 'truth': truth[(ep_id, qid)], 'parsed': r['parsed'][qid],
                                 'raw_output': r['raw_output']})

    out = {'n_scored_records': len(scored), 'n_failed_attempts_in_log': n_fail,
           'accuracy': {}, 'per_question': {}, 'parse_failures': {}, 'lift': {}}
    readers = sorted({k[0] for k in acc})
    for reader in readers:
        out['accuracy'][reader] = {}
        for cond in ['frame', 'blind', 'shuffled']:
            c, t = acc.get((reader, cond), [0, 0])
            out['accuracy'][reader][cond] = {'correct': c, 'total': t,
                                             'acc': round(c / t, 4) if t else None}
        fa = out['accuracy'][reader]['frame']['acc']
        ba = out['accuracy'][reader]['blind']['acc']
        if fa is not None and ba is not None:
            out['lift'][reader] = round(fa - ba, 4)
        out['per_question'][reader] = {}
        for cond in ['frame', 'blind', 'shuffled']:
            out['per_question'][reader][cond] = {}
            for qid in QIDS:
                c, t = acc_q.get((reader, cond, qid), [0, 0])
                out['per_question'][reader][cond][qid] = round(c / t, 4) if t else None
        out['parse_failures'][reader] = {cond: parse_fail.get((reader, cond), 0)
                                         for cond in ['frame', 'blind', 'shuffled']}

    with open(os.path.join(HERE, 'scores.json'), 'w') as f:
        json.dump(out, f, indent=1)
    with open(os.path.join(HERE, 'frame_failures.json'), 'w') as f:
        json.dump(failures, f, indent=1)

    print(f"scored records: {len(scored)}   failed attempts in log: {n_fail}")
    print(f"{'reader':10s} {'frame':>8s} {'blind':>8s} {'shuffled':>9s} {'LIFT':>7s}")
    for reader in readers:
        a = out['accuracy'][reader]
        print(f"{reader:10s} {a['frame']['acc']:8.3f} {a['blind']['acc']:8.3f} "
              f"{a['shuffled']['acc']:9.3f} {out['lift'].get(reader, float('nan')):+7.3f}")
    print('\nper-question (frame | blind | shuffled):')
    for reader in readers:
        for qid in QIDS:
            pq = out['per_question'][reader]
            print(f"  {reader:9s} {qid}: {pq['frame'][qid]:.3f} | {pq['blind'][qid]:.3f} | {pq['shuffled'][qid]:.3f}")
    print('\nparse failures:', dict(out['parse_failures']))
    print(f'frame-condition failures total: {len(failures)} (see frame_failures.json)')


if __name__ == '__main__':
    main()
