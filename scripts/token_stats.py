#!/usr/bin/env python3
"""Token usage + estimated cost from Claude Code + Codex CLI local session logs.

Claude Code: every assistant message line carries its own `message.model` and
`message.usage` (input_tokens, cache_creation_input_tokens,
cache_read_input_tokens, output_tokens) — priced per message, since one
session can mix models (e.g. a Haiku subagent call inside a Sonnet session).

Codex CLI: periodic `token_count` events carry a CUMULATIVE
total_token_usage snapshot for the whole session so far — only the LAST one
per file is needed for a session total. `cached_input_tokens` is a SUBSET of
`input_tokens`, not additional (verified: input_tokens + output_tokens ==
total_tokens on real data) — billed as fresh-input minus cached, plus
cache-read at the discount rate. No cache-CREATION tokens are exposed by
this event, so that cost component is always 0 for Codex — a real gap, not
an oversight; see references/methodology.md.
"""
import glob
import json

from pricing import estimate_cost_usd, lookup_model_pricing

EMPTY_TOKENS = {"input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}


def _add(a, b):
    return {k: a[k] + b.get(k, 0) for k in a}


def claude_code_session_stats(path, pricing_data):
    tokens = dict(EMPTY_TOKENS)
    cost = 0.0
    cost_known = False
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                msg = d.get("message") or {}
                u = msg.get("usage")
                if not u:
                    continue
                t = {
                    "input_tokens": u.get("input_tokens", 0) or 0,
                    "output_tokens": u.get("output_tokens", 0) or 0,
                    "cache_creation_tokens": u.get("cache_creation_input_tokens", 0) or 0,
                    "cache_read_tokens": u.get("cache_read_input_tokens", 0) or 0,
                }
                tokens = _add(tokens, t)
                entry = lookup_model_pricing(msg.get("model"), pricing_data)
                c = estimate_cost_usd(entry, t["input_tokens"], t["output_tokens"],
                                       t["cache_creation_tokens"], t["cache_read_tokens"])
                if c is not None:
                    cost += c
                    cost_known = True
    except Exception:
        pass
    return tokens, (cost if cost_known else None)


def codex_session_stats(path, pricing_data):
    last_usage, model = None, None
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                if '"turn_context"' in line:
                    try:
                        d = json.loads(line)
                    except Exception:
                        d = {}
                    if d.get("type") == "turn_context":
                        model = (d.get("payload") or {}).get("model") or model
                    continue
                if '"token_count"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                payload = d.get("payload") or {}
                if payload.get("type") != "token_count":
                    continue
                info = (payload.get("info") or {}).get("total_token_usage")
                if info:
                    last_usage = info
    except Exception:
        pass
    if not last_usage:
        return dict(EMPTY_TOKENS), None
    cached = last_usage.get("cached_input_tokens", 0) or 0
    tokens = {
        "input_tokens": max(0, (last_usage.get("input_tokens", 0) or 0) - cached),
        "output_tokens": last_usage.get("output_tokens", 0) or 0,
        "cache_creation_tokens": 0,  # not exposed by this event, see module docstring
        "cache_read_tokens": cached,
    }
    entry = lookup_model_pricing(model, pricing_data)
    cost = estimate_cost_usd(entry, tokens["input_tokens"], tokens["output_tokens"],
                              0, tokens["cache_read_tokens"])
    return tokens, cost
