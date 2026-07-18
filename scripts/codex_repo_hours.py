#!/usr/bin/env python3
"""Per-repo hours from Codex CLI's local session logs (~/.codex/sessions/**/*.jsonl).

Reuses session_duration_stats' timestamp/gap-capping math (Codex rollout files
carry the same top-level "timestamp" field) for the totals, then reads each
file's session_meta.cwd line separately for per-repo attribution — Codex
organizes sessions by date, not by cwd-encoded folder name like Claude Code,
so there is no folder-name substring trick available here.
"""
import json

from session_duration_stats import aggregate as session_aggregate


def session_cwd(path):
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                if '"cwd"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                cwd = (d.get("payload") or {}).get("cwd") or d.get("cwd")
                if cwd:
                    return cwd
    except Exception:
        return None
    return None


def match_repo_by_cwd(cwd, repo_paths):
    if not cwd:
        return None
    for path in sorted(repo_paths, key=len, reverse=True):
        if cwd == path or cwd.startswith(path + "/"):
            return path.rsplit("/", 1)[-1]
    return None


def codex_hours_per_repo(sessions_dir, repo_paths, cap_minutes=5.0, period=None):
    result = session_aggregate(sessions_dir, cap_minutes, period=period)
    totals = {}
    for s in result["per_session"]:
        cwd = session_cwd(s["file"])
        repo = match_repo_by_cwd(cwd, repo_paths) or "(other/unmatched)"
        totals[repo] = totals.get(repo, 0.0) + s["active_seconds"]
    return totals, result
