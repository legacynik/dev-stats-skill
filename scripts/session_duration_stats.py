#!/usr/bin/env python3
"""Aggregate Claude Code local session-transcript stats (wall-clock + active-work estimate).

Reads every ~/.claude/projects/**/*.jsonl transcript, extracts message timestamps,
and computes per-session wall-clock span plus a capped-gap "active work" estimate
(gaps between consecutive messages longer than --cap-minutes are treated as idle,
not work, so long away-from-keyboard periods don't inflate the total).

This is an approximation, not an authoritative source (Claude Code's official
usage lives server-side / in the claude.ai account dashboard). It's local-machine
only and double-counts overlapping parallel sessions in the wall-clock figure by
design (each session's own span is summed independently).

Usage:
    python3 session_duration_stats.py [--projects-dir PATH] [--cap-minutes N] [--json-out PATH]
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone


def load_timestamps(path):
    timestamps = []
    try:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or '"timestamp"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                ts = d.get("timestamp")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:  # no offset in the source string — assume UTC
                        dt = dt.replace(tzinfo=timezone.utc)  # else sort()/period-filter crash on naive-vs-aware compare
                    timestamps.append(dt)
                except Exception:
                    continue
    except Exception:
        return None
    return timestamps


def session_stats(timestamps, cap_seconds):
    timestamps.sort()
    wall = (timestamps[-1] - timestamps[0]).total_seconds()
    active = 0.0
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if gap > 0:
            active += min(gap, cap_seconds)
    return wall, active


def aggregate(projects_dir, cap_minutes=5.0, progress=False, period=None):
    """Scan every transcript under projects_dir, return the same dict main() prints/dumps.

    period: optional (since, until) tuple of tz-aware datetimes. A session is kept
    if its span overlaps the window at all (approximate: keyed on session start/end,
    not per-message).
    """
    cap_seconds = cap_minutes * 60
    since, until = period or (None, None)
    files = glob.glob(f"{projects_dir}/**/*.jsonl", recursive=True) if os.path.isdir(projects_dir) else []
    if progress:
        print(f"Session files found: {len(files)}", file=sys.stderr)

    total_wall = 0.0
    total_active = 0.0
    sessions_with_data = 0
    first_ts = None
    last_ts = None
    per_session = []

    for i, f in enumerate(files):
        timestamps = load_timestamps(f)
        if not timestamps or len(timestamps) < 2:
            continue
        if since and timestamps[-1] < since:
            continue
        if until and timestamps[0] > until:
            continue
        wall, active = session_stats(timestamps, cap_seconds)
        if wall <= 0:
            continue
        total_wall += wall
        total_active += active
        sessions_with_data += 1
        per_session.append({"file": f, "wall_seconds": wall, "active_seconds": active,
                             "start": timestamps[0].isoformat(), "end": timestamps[-1].isoformat()})
        if first_ts is None or timestamps[0] < first_ts:
            first_ts = timestamps[0]
        if last_ts is None or timestamps[-1] > last_ts:
            last_ts = timestamps[-1]
        if progress and i % 1000 == 0:
            print(f"  ...{i}/{len(files)} processed", file=sys.stderr)

    return {
        "projects_dir": projects_dir,
        "cap_minutes": cap_minutes,
        "files_found": len(files),
        "sessions_with_data": sessions_with_data,
        "date_range": {"first": first_ts.isoformat() if first_ts else None,
                        "last": last_ts.isoformat() if last_ts else None},
        "total_wall_seconds": total_wall,
        "total_wall_hours": round(total_wall / 3600, 1),
        "total_active_seconds": total_active,
        "total_active_hours": round(total_active / 3600, 1),
        "per_session": per_session,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--cap-minutes", type=float, default=5.0)
    ap.add_argument("--json-out", default=None, help="write full result as JSON to this path")
    args = ap.parse_args()

    result = aggregate(args.projects_dir, args.cap_minutes, progress=True)

    print("\n=== RESULT ===")
    print(f"Sessions with >=2 timestamps: {result['sessions_with_data']} / {result['files_found']}")
    print(f"Date range: {result['date_range']['first']} -> {result['date_range']['last']}")
    print(f"Wall-clock sum (overlaps double-count parallel sessions): {result['total_wall_hours']:,}h")
    print(f"Active-work estimate (gaps capped at {args.cap_minutes}min): {result['total_active_hours']:,}h")

    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nFull JSON (incl. per-session breakdown) written to {args.json_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
