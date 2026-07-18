#!/usr/bin/env python3
"""Model pricing from LiteLLM's community-maintained, hourly-updated JSON —
the same source ccusage (the established Claude Code/Codex usage tool) uses,
fetched directly instead of vendoring a table we'd have to maintain by hand.

Cached locally with a max-age; falls back to a stale cache (or gives up
gracefully, cost just becomes unavailable) if the network is down — pricing
is an enrichment, never something that should break a token-count report.
"""
import json
import os
import re
import time
import urllib.request

LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
DEFAULT_CACHE_PATH = os.path.expanduser("~/.cache/dev-stats-skill/litellm-pricing.json")
DATE_SUFFIX = re.compile(r"-\d{8}$")


def fetch_pricing(cache_path=DEFAULT_CACHE_PATH, max_age_hours=24, timeout=10):
    fresh = os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < max_age_hours * 3600
    if fresh:
        try:
            return json.load(open(cache_path))
        except Exception:
            pass  # corrupt cache, fall through to refetch

    try:
        with urllib.request.urlopen(LITELLM_URL, timeout=timeout) as resp:
            data = json.loads(resp.read())
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as fh:
            json.dump(data, fh)
        return data
    except Exception:
        if os.path.exists(cache_path):
            try:
                return json.load(open(cache_path))  # stale beats nothing
            except Exception:
                return None
        return None


def lookup_model_pricing(model, pricing_data):
    # isinstance guard: a corrupted cache file or an unexpected upstream JSON
    # shape (e.g. a list) would otherwise crash every caller's .get(model)
    if not model or not isinstance(pricing_data, dict):
        return None
    if model in pricing_data:
        return pricing_data[model]
    stripped = DATE_SUFFIX.sub("", model)  # e.g. claude-haiku-4-5-20251001 -> claude-haiku-4-5
    return pricing_data.get(stripped)


def estimate_cost_usd(pricing_entry, input_tokens=0, output_tokens=0,
                       cache_creation_tokens=0, cache_read_tokens=0):
    if not pricing_entry:
        return None
    return (
        input_tokens * pricing_entry.get("input_cost_per_token", 0)
        + output_tokens * pricing_entry.get("output_cost_per_token", 0)
        + cache_creation_tokens * pricing_entry.get("cache_creation_input_token_cost", 0)
        + cache_read_tokens * pricing_entry.get("cache_read_input_token_cost", 0)
    )
