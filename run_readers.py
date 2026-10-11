#!/usr/bin/env python3
"""Run the stage-1 reading experiment: fleet text models answer frozen,
ground-truth-derived questions about mazelab text frames, under 3 conditions:

  frame    — the episode's own text frame
  blind    — no frame (prior/guessing baseline)
  shuffled — a DIFFERENT episode's frame (frame-use control)

One batched call per (reader, condition, episode): all 5 questions at once.
Resumable: completed combos in reader_outputs.jsonl are skipped.
Scoring is exact-match after per-question-type normalization, done by this
pure function — never by a model.
"""
import argparse, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
READERS = {
    'minimax': ('~/workspace/skills/minimax/bin/chat.py', 'MiniMax-Text-01'),
    # glm goes through the experiment-local caller (same API/model/credential,
    # thinking disabled) — the stock CLI returns empty content on grid prompts;
    # see glm_call.py docstring and RESULTS.md.
    'glm': ('~/workspace/syzygy-program/reading-experiment/glm_call.py',
            'glm-4.5-flash (thinking disabled)'),
}
SHUFFLE_ROT = 23  # episode i is graded against frame of episode (i+23) % N

GUIDE = open(os.path.join(HERE, 'READING_GUIDE.md')).read().split('\n', 2)[2].strip()
# (strip the markdown title + frozen banner; the guide body is what readers saw)

ANSWER_TAIL = """Answer with exactly 5 lines, in this form:
Q1: <answer>
Q2: <answer>
Q3: <answer>
Q4: <answer>
Q5: <answer>
Give only those 5 lines. If you cannot determine an answer, give your best guess in the same form."""


def build_prompt(ep_frame, questions):
    parts = [GUIDE, '']
    if ep_frame is not None:
        parts += ['Map:', '```', ep_frame, '```', '']
    parts.append('Questions about the map:')
    for q in questions:
        parts.append(f"{q['qid']}. {q['question']}")
    parts += ['', ANSWER_TAIL]
    return '\n'.join(parts)


# ---------- parsing / scoring (pure functions) ----------
DIR_WORDS = [('northeast', 'NE'), ('north-east', 'NE'), ('north east', 'NE'),
             ('northwest', 'NW'), ('north-west', 'NW'), ('north west', 'NW'),
             ('southeast', 'SE'), ('south-east', 'SE'), ('south east', 'SE'),
             ('southwest', 'SW'), ('south-west', 'SW'), ('south west', 'SW'),
             ('north', 'N'), ('south', 'S'), ('east', 'E'), ('west', 'W')]


def norm_direction(text):
    t = ' ' + text.lower().strip() + ' '
    for word, tok in DIR_WORDS:
        if f' {word} ' in t or f' {word}:' in t or t.strip().startswith(word):
            return tok
    m = re.search(r'\b(NE|NW|SE|SW|N|S|E|W)\b', text.upper())
    return m.group(1) if m else None


def norm_int(text):
    m = re.search(r'-?\d+', text)
    return str(int(m.group(0))) if m else None


def norm_yesno(text):
    m = re.search(r'\b(yes|no)\b', text.lower())
    return m.group(1) if m else None


NORMALIZERS = {'Q1': norm_direction, 'Q2': norm_int, 'Q3': norm_yesno,
               'Q4': norm_int, 'Q5': norm_yesno}


def parse_answers(raw):
    """Extract {qid: normalized answer or None} from a reader's raw output."""
    segs = {}
    for line in raw.splitlines():
        m = re.match(r'\s*\**Q\s*([1-5])\s*[:\.\)]\**\s*(.*)', line, re.IGNORECASE)
        if m and m.group(1) not in segs:
            segs[m.group(1)] = m.group(2).strip()
    out = {}
    for n in '12345':
        qid = f'Q{n}'
        out[qid] = NORMALIZERS[qid](segs[n]) if n in segs else None
    return out


def call_reader(cli, prompt, timeout=240, attempts=3):
    """Call a reader CLI with retries + backoff. An EMPTY stdout counts as a
    failure (glm-4.5-flash intermittently returns empty content with exit 0;
    counting it as a 0/5 answer would corrupt the measurement)."""
    total_dt = 0.0
    last_err = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(5 * attempt * attempt)  # 5s, 20s backoff (429 relief)
        t0 = time.time()
        try:
            r = subprocess.run([os.path.expanduser(cli), prompt, '--max-tokens', '2000'],
                               capture_output=True, text=True, timeout=timeout)
            dt = time.time() - t0
            total_dt += dt
            if r.returncode != 0:
                last_err = f'exit {r.returncode}: {r.stderr.strip()[:300]}'
                continue
            out = r.stdout.strip()
            if not out:
                last_err = 'empty output (exit 0)'
                continue
            return out, None, total_dt
        except subprocess.TimeoutExpired:
            total_dt += time.time() - t0
            last_err = f'timeout after {timeout}s'
    return None, last_err, total_dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--readers', default='minimax,glm')
    ap.add_argument('--conditions', default='frame,blind,shuffled')
    ap.add_argument('--limit', type=int, default=None, help='only first N episodes')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--out', default=os.path.join(HERE, 'reader_outputs.jsonl'))
    args = ap.parse_args()

    episodes = [json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))]
    questions = [json.loads(l) for l in open(os.path.join(HERE, 'questions.jsonl'))]
    if args.limit:
        keep = {ep['episode_id'] for ep in episodes[:args.limit]}
        episodes = episodes[:args.limit]
        questions = [q for q in questions if q['episode_id'] in keep]
    q_by_ep = {}
    for q in questions:
        q_by_ep.setdefault(q['episode_id'], []).append(q)
    truth = {(q['episode_id'], q['qid']): q['answer'] for q in questions}
    ep_by_id = {ep['episode_id']: ep for ep in episodes}
    n_all = len([json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))])

    done = set()
    if os.path.exists(args.out):
        for l in open(args.out):
            try:
                r = json.loads(l)
                # only successful records count as done; failures get retried
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
                    src_id = f'ep{(idx + SHUFFLE_ROT) % n_all:02d}'
                    all_eps = [json.loads(l) for l in open(os.path.join(HERE, 'episodes.jsonl'))]
                    frame, frame_ep = all_eps[(idx + SHUFFLE_ROT) % n_all]['frame'], src_id
                else:
                    frame, frame_ep = None, None
                prompt = build_prompt(frame, q_by_ep[ep['episode_id']])
                jobs.append((reader, model, cli, cond, ep['episode_id'], frame_ep, prompt))

    print(f'{len(jobs)} calls to make ({len(done)} already done)', flush=True)

    lock_path = args.out + '.lock'
    import threading
    write_lock = threading.Lock()

    def do(job):
        reader, model, cli, cond, ep_id, frame_ep, prompt = job
        raw, err, dt = call_reader(cli, prompt)
        rec = {'reader': reader, 'model': model, 'condition': cond,
               'episode_id': ep_id, 'frame_episode_id': frame_ep,
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
