#!/usr/bin/env python3
"""Experiment-local GLM reader caller — a deliberate, documented deviation
from the stock ZAI CLI (~/workspace/skills/zai/bin/chat.py).

Why this exists (diagnosed 2026-10-11, evidence in RESULTS.md):
glm-4.5-flash is a reasoning model. On maze-grid prompts the stock CLI
returned EMPTY content with finish_reason='length': the model spent its
entire 2000-token budget on reasoning_content (5,504 chars) and never
emitted an answer; at larger budgets it exceeded the CLI's hardcoded 120 s
read timeout. The ZAI API accepts thinking={'type': 'disabled'}, which
makes the same model, same endpoint, same credential answer directly
(2.3 s, 27 completion tokens, clean format).

This caller follows the skill's documented credential pattern exactly
(dynamic_credentials.add_surrogate_to_request, host api.z.ai only) and
mirrors the CLI's interface: prompt positional arg, prints content only.
Model: glm-4.5-flash. Temperature 0.7 (same default as the stock CLI).
"""
import sys
sys.path.insert(0, '/opt/hatch/skills/skill-creator/bin')
from dynamic_credentials import add_surrogate_to_request, read_json_response
import urllib.request
import json

API_URL = 'https://api.z.ai/api/paas/v4/chat/completions'
MODEL = 'glm-4.5-flash'


def chat(messages, max_tokens=2000, temperature=0.7):
    body = json.dumps({
        'model': MODEL,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
        'thinking': {'type': 'disabled'},
    }).encode()
    req = urllib.request.Request(API_URL, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    add_surrogate_to_request(req, 'custom.zai', allowed_hosts=['api.z.ai'])
    resp = urllib.request.urlopen(req, timeout=150)
    return read_json_response(resp)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('prompt')
    p.add_argument('--model', default=None)   # accepted for CLI parity; MODEL is fixed
    p.add_argument('--system', default=None)
    p.add_argument('--max-tokens', type=int, default=2000)
    args = p.parse_args()
    messages = []
    if args.system:
        messages.append({'role': 'system', 'content': args.system})
    messages.append({'role': 'user', 'content': args.prompt})
    try:
        data = chat(messages, max_tokens=args.max_tokens)
        choice = data.get('choices', [{}])[0]
        print(choice.get('message', {}).get('content', ''))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
