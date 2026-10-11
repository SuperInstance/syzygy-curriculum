#!/usr/bin/env python3
"""Stage-1 reading experiment v2: same episodes, same questions, same scorer
— the reading guide is the only scored variable.

Differences from run_readers.py (v1), deliberately exhaustive:
  1. The guide is READING_GUIDE_V2.md (v1 vocabulary + procedures + worked
     example + an answer format that permits Work lines before each answer).
  2. Every prompt is preceded by the cross-feed block: the three
     writing-break pieces from the program (claude/minimax/glm), included as
     session reading per program doctrine. Constant across ALL v2
     conditions, so it cannot explain any within-v2 difference; it is a
     confound on the v1->v2 delta and is disclosed as such in RESULTS-V2.md.
  3. Records carry guide_version/stories_in_context provenance fields and go
     to reader_outputs_v2.jsonl. Failed attempts are retained, as in v1.

Scoring is the v1 pure function imported from run_readers (parse_answers),
and reader calls use v1's call_reader (same CLIs, same --max-tokens 2000,
same retry/backoff). Resumable: successful combos already in the output
file are skipped; failures are retried on a later invocation.
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_readers import parse_answers, call_reader, READERS, SHUFFLE_ROT  # noqa: E402

GUIDE_V2 = open(os.path.join(HERE, 'READING_GUIDE_V2.md')).read().split('\n', 2)[2].strip()
# (same strip convention as v1: drop the markdown title + blank line)

WRITINGS_DIR = os.path.expanduser('~/workspace/syzygy-program/writings')
PIECES = [
    ('"The Morning Count" by Muse', 'claude-piece.md'),
    ('"The Weight of Shadows" by MiniMax', 'minimax-piece.md'),
    ('"Harbor Hash" by GLM', 'glm-piece.md'),
]


def stories_block():
    parts = ["Some reading before today's session: three short pieces written "
             "by colleagues working on this same program, left here as session "
             "reading. Read them first; the task follows after.", '']
    for label, fname in PIECES:
        parts.append(f'--- {label} ---')
        parts.append(open(os.path.join(WRITINGS_DIR, fname)).read().strip())
        parts.append('')
    parts.append('=== End of the reading. The task follows. ===')
    return '\n'.join(parts)


STORIES = stories_block()

TAIL_V2 = """Answer the questions in order, following the guide: for each question, write its Work lines first (the checks, each starting with "Work"), then its answer line in exactly this form:
Q1: <answer>
...
Q5: <answer>
If you cannot determine an answer, still write what you checked and give your best guess in the same form."""


def build_prompt_v2(ep_frame, questions):
    parts = [STORIES, '', GUIDE_V2, '']
    if ep_frame is not None:
        parts += ['Map:', '```', ep_frame, '```', '']
    parts.append('Questions about the map:')
    for q in questions:
        parts.append(f"{q['qid']}. {q['question']}")
    parts += ['', TAIL_V2]
    return '\n'.join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--readers', default='minimax,glm')
    ap.add_argument('--conditions', default='frame,blind,shuffled')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--out', default=os.path.join(HERE, 'reader_outputs_v2.jsonl'))
    args = ap.parse_args()

    all_episodes = [json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))]
    episodes = all_episodes[:args.limit] if args.limit else all_episodes
    keep = {ep['episode_id'] for ep in episodes}
    questions = [json.loads(l) for l in open(os.path.join(HERE, 'questions.jsonl'))
                 if not args.limit or json.loads(l)['episode_id'] in keep]
    q_by_ep = {}
    for q in questions:
        q_by_ep.setdefault(q['episode_id'], []).append(q)
    truth = {(q['episode_id'], q['qid']): q['answer'] for q in questions}
    n_all = len(all_episodes)

    done = set()
    if os.path.exists(args.out):
        for l in open(args.out):
            try:
                r = json.loads(l)
                if r.get('error') is None and r.get('raw_output'):
                    done.add((r['reader'], r['condition'], r['episode_id']))
            except Exception:
                pass

    jobs = []
    for reader in args.readers.split(','):
        cli, model = READERS[reader]
        for cond in args.conditions.split(','):
            for ep in episodes:
                key = (reader, cond, ep['episode_id'])
                if key in done:
                    continue
                if cond == 'frame':
                    frame, frame_ep = ep['frame'], ep['episode_id']
                elif cond == 'shuffled':
                    idx = int(ep['episode_id'][2:])
                    src = all_episodes[(idx + SHUFFLE_ROT) % n_all]
                    frame, frame_ep = src['frame'], src['episode_id']
                else:
                    frame, frame_ep = None, None
                prompt = build_prompt_v2(frame, q_by_ep[ep['episode_id']])
                jobs.append((reader, model, cli, cond, ep['episode_id'], frame_ep, prompt))

    print(f'{len(jobs)} calls to make ({len(done)} already done)', flush=True)

    import threading
    write_lock = threading.Lock()

    def do(job):
        reader, model, cli, cond, ep_id, frame_ep, prompt = job
        raw, err, dt = call_reader(cli, prompt)
        rec = {'reader': reader, 'model': model, 'condition': cond,
               'episode_id': ep_id, 'frame_episode_id': frame_ep,
               'guide_version': 'v2', 'stories_in_context': True,
               'prompt': prompt, 'raw_output': raw, 'error': err,
               'latency_s': round(dt, 2)}
        if raw is not None:
            parsed = parse_answers(raw)
            rec['parsed'] = parsed
            rec['correct'] = {qid: (parsed[qid] is not None and parsed[qid] == truth[(ep_id, qid)])
                              for qid in parsed}
        with write_lock:
            with open(args.out, 'a') as f:
                f.write(json.dumps(rec) + '\n')
        status = 'ERR' if raw is None else f"{sum(rec.get('correct', {}).values())}/5"
        print(f'{reader:8s} {cond:8s} {ep_id} -> {status} ({dt:.0f}s)', flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(do, j) for j in jobs]
        for _ in as_completed(futs):
            pass
    print('done')


if __name__ == '__main__':
    main()
