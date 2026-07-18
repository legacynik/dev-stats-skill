#!/usr/bin/env python3
"""Dev-stats dashboard: active work hours (local Claude Code + Codex CLI transcripts)
+ LOC contributed (git log --numstat), rendered as a boxed terminal panel, with an
optional period filter and a per-repo hours breakdown.

Combines session_duration_stats.aggregate(), codex_repo_hours, and loc_stats.aggregate()
— no new data collection here, just a nicer front end over those scans. If neither
transcript source exists on this machine, falls back to LOC-only output — this tool
is still useful with just git history.

Per-repo hours from Claude Code are matched by substring: Claude Code encodes a
session's cwd into its project-folder name by replacing "/" and " " with "-", so a
repo label ("My-Repo", from "My Repo") is looked up as a substring of that folder
name. Codex CLI hours are matched via the exact cwd each rollout file records.
Both are best-effort — approximate, not a ledger.

Usage:
    python3 dev_stats.py [--vault-dir PATH] [--cap-minutes N]
                          [--days N | --since YYYY-MM-DD [--until YYYY-MM-DD]]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from codex_repo_hours import codex_hours_per_repo
from loc_stats import aggregate as loc_aggregate, default_authors, find_repos
from session_duration_stats import aggregate as session_aggregate

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
CYAN, GREEN, YELLOW, MAGENTA = "\033[36m", "\033[32m", "\033[33m", "\033[35m"
BAR_WIDTH = 28


def resolve_period(args):
    if args.days:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        return since, None
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc) if args.until else None
    return since, until


def repo_label(repo_name):
    return repo_name.replace(" ", "-")


def match_repo(folder_name, labels_to_names):
    for label, name in labels_to_names:  # pre-sorted longest label first
        if label in folder_name:
            return name
    return "(other/unmatched)"


def hours_per_repo(per_session, vault_dir, projects_dir_prefix_len):
    names = find_repos(vault_dir)
    labels_to_names = sorted(
        ((repo_label(n.rsplit("/", 1)[-1]), n.rsplit("/", 1)[-1]) for n in names),
        key=lambda t: len(t[0]), reverse=True,
    )
    totals = {}
    for s in per_session:
        folder = s["file"][projects_dir_prefix_len:].split("/", 1)[0]
        repo = match_repo(folder, labels_to_names)
        totals[repo] = totals.get(repo, 0.0) + s["active_seconds"]
    return totals


def merge_hours(a, b):
    merged = dict(a)
    for k, v in b.items():
        merged[k] = merged.get(k, 0.0) + v
    return merged


def box(title, width=64):
    top = "╭" + "─" * (width - 2) + "╮"
    mid = f"│ {BOLD}{title}{RESET}".ljust(width - 1 + len(BOLD) + len(RESET)) + "│"
    bot = "╰" + "─" * (width - 2) + "╯"
    return "\n".join([top, mid, bot])


def stat_line(label, value, color=CYAN, sub=""):
    label_padded = f"  {label}".ljust(24)
    sub_txt = f"  {DIM}{sub}{RESET}" if sub else ""
    return f"{label_padded}{color}{BOLD}{value}{RESET}{sub_txt}"


def bar(value, max_value, width=BAR_WIDTH):
    filled = int(width * value / max_value) if max_value else 0
    return "█" * filled + "░" * (width - filled)


def render_repo_table(per_repo, hours_by_repo, show_hours, top_n=12):
    if not per_repo:
        return "  (no matching commits — check --author, or run git config --global user.email)"
    rows = per_repo[:top_n]
    max_net = max(r["net"] for r in rows) or 1
    hcol = "  hours" if show_hours else ""
    lines = [f"  {'repo':<24} {'':<{BAR_WIDTH}} {'net LOC':>9}  {'commits':>7}{hcol}"]
    for r in rows:
        b = bar(r["net"], max_net)
        row = f"  {r['repo']:<24} {GREEN}{b}{RESET} {r['net']:>9,}  {r['commits']:>7,}"
        if show_hours:
            h = hours_by_repo.get(r["repo"])
            h_txt = f"{h / 3600:>6.1f}h" if h else f"{'-':>7}"
            row += f"  {MAGENTA}{h_txt}{RESET}"
        lines.append(row)
    if len(per_repo) > top_n:
        lines.append(f"  {DIM}... +{len(per_repo) - top_n} more repos{RESET}")
    return "\n".join(lines)


def render(name, session_result, loc_result, hours_by_repo, period_label):
    show_hours = session_result is not None
    print()
    print(box(f"DEV STATS — {name}" if name else "DEV STATS"))
    print()
    if show_hours:
        dr = session_result["date_range"]
        print(f"  {DIM}window: {dr['first']} -> {dr['last']}{RESET}  {DIM}({period_label}){RESET}")
        print()
        print(stat_line("Active work (est.)", f"{session_result['total_active_hours']:,}h", MAGENTA,
                         sub=f"wall-clock sum {session_result['total_wall_hours']:,}h, "
                             f"{session_result['sessions_with_data']:,} sessions"))
    else:
        print(f"  {DIM}({period_label}, no local session transcripts found — LOC only){RESET}")
        print()
    print(stat_line("Lines added", f"+{loc_result['total_added']:,}", GREEN))
    print(stat_line("Lines removed", f"-{loc_result['total_removed']:,}", YELLOW))
    print(stat_line("Commits", f"{loc_result['total_commits']:,}", CYAN))
    print()
    print(f"  {BOLD}Per-repo (by net LOC{', hours = best-effort match' if show_hours else ''}){RESET}")
    print(render_repo_table(loc_result["per_repo"], hours_by_repo, show_hours))
    unmatched = hours_by_repo.get("(other/unmatched)", 0.0)
    if unmatched:
        print(f"\n  {DIM}{unmatched / 3600:.1f}h in sessions outside the repos above "
              f"(other machines/paths, other tooling){RESET}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--codex-dir", default=os.path.expanduser("~/.codex/sessions"))
    ap.add_argument("--no-codex", action="store_true", help="Claude Code hours only")
    ap.add_argument("--vault-dir", default=os.getcwd(), help="folder containing your repos (default: cwd)")
    ap.add_argument("--cap-minutes", type=float, default=5.0)
    ap.add_argument("--author", action="append", default=None)
    ap.add_argument("--name", default=None, help="display name for the header (default: git config user.name)")
    ap.add_argument("--exclude-repo", action="append", default=None)
    ap.add_argument("--days", type=int, default=None, help="only the last N days")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD")
    ap.add_argument("--until", default=None, help="YYYY-MM-DD")
    args = ap.parse_args()

    since, until = resolve_period(args)
    period_label = f"since {since.date()}" if since else "all-time"
    if until:
        period_label += f" until {until.date()}"

    authors = args.author or default_authors()
    if not authors:
        print("No author found — set git config --global user.email, or pass --author.", file=sys.stderr)
        sys.exit(1)
    name = args.name or authors[-1]

    print("Scanning sessions + repos...", file=sys.stderr)
    loc_period = (args.since or (since.date().isoformat() if since else None), args.until or until)
    loc_result = loc_aggregate(args.vault_dir, authors, loc_period, repo_exclude=args.exclude_repo)

    has_claude = os.path.isdir(args.projects_dir)
    has_codex = not args.no_codex and os.path.isdir(args.codex_dir)
    session_result = None
    hours_by_repo = {}

    if has_claude:
        session_result = session_aggregate(args.projects_dir, args.cap_minutes, period=(since, until))
        prefix_len = len(args.projects_dir.rstrip("/")) + 1
        hours_by_repo = hours_per_repo(session_result["per_session"], args.vault_dir, prefix_len)

    if has_codex:
        repo_paths = find_repos(args.vault_dir, args.exclude_repo)
        codex_by_repo, codex_result = codex_hours_per_repo(args.codex_dir, repo_paths,
                                                             args.cap_minutes, (since, until))
        hours_by_repo = merge_hours(hours_by_repo, codex_by_repo)
        if session_result is None:
            session_result = codex_result
        else:
            session_result["total_active_hours"] = round(
                session_result["total_active_hours"] + codex_result["total_active_hours"], 1)
            session_result["total_wall_hours"] = round(
                session_result["total_wall_hours"] + codex_result["total_wall_hours"], 1)
            session_result["sessions_with_data"] += codex_result["sessions_with_data"]
        print(f"  + Codex CLI: {codex_result['total_active_hours']}h active, "
              f"{codex_result['sessions_with_data']} sessions", file=sys.stderr)

    render(name, session_result, loc_result, hours_by_repo, period_label)


if __name__ == "__main__":
    main()
