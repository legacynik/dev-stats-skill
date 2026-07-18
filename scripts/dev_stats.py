#!/usr/bin/env python3
"""Dev-stats dashboard: active work hours (local Claude Code + Codex CLI transcripts)
+ LOC contributed (git log --numstat) + token usage/estimated cost, rendered as a
boxed terminal panel, with an optional period filter and a per-repo breakdown.

Combines session_duration_stats.aggregate(), codex_repo_hours, token_stats, and
loc_stats.aggregate() — no new data collection here, just a nicer front end over
those scans. If neither transcript source exists on this machine, falls back to
LOC-only output — this tool is still useful with just git history.

Per-repo hours/tokens from Claude Code are matched by substring: Claude Code
encodes a session's cwd into its project-folder name by replacing "/" and " "
with "-", so a repo label ("My-Repo", from "My Repo") is looked up as a
substring of that folder name. Codex CLI hours/tokens are matched via the
exact cwd each rollout file records. Both are best-effort — approximate, not
a ledger.

Usage:
    python3 dev_stats.py [--vault-dir PATH] [--cap-minutes N] [--no-tokens]
                          [--days N | --since YYYY-MM-DD [--until YYYY-MM-DD]]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from codex_repo_hours import codex_hours_per_repo, session_cwd
from loc_stats import DEFAULT_EXCLUDE as DEFAULT_LOC_EXCLUDE
from loc_stats import aggregate as loc_aggregate, default_authors, find_repos
from pricing import fetch_pricing
from repo_match import labels_to_names, match_repo, match_repo_by_cwd
from session_duration_stats import aggregate as session_aggregate
from token_stats import EMPTY_TOKENS, claude_code_session_stats, codex_session_stats, tokens_for_files

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
CYAN, GREEN, YELLOW, MAGENTA, BLUE = "\033[36m", "\033[32m", "\033[33m", "\033[35m", "\033[34m"
BAR_WIDTH = 28


def resolve_period(args):
    if args.days:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        return since, None
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc) if args.until else None
    return since, until


def hours_per_repo(per_session, vault_dir, projects_dir_prefix_len, repo_exclude=None):
    names_by_label = labels_to_names(find_repos(vault_dir, repo_exclude))
    totals = {}
    for s in per_session:
        folder = s["file"][projects_dir_prefix_len:].split("/", 1)[0]
        repo = match_repo(folder, names_by_label)
        totals[repo] = totals.get(repo, 0.0) + s["active_seconds"]
    return totals


def claude_code_tokens_per_repo(per_session, vault_dir, projects_dir_prefix_len, pricing, repo_exclude=None):
    names_by_label = labels_to_names(find_repos(vault_dir, repo_exclude))
    totals, costs = {}, {}
    for s in per_session:
        folder = s["file"][projects_dir_prefix_len:].split("/", 1)[0]
        repo = match_repo(folder, names_by_label)
        tokens, cost = claude_code_session_stats(s["file"], pricing)
        totals[repo] = _add_tokens(totals.get(repo, dict(EMPTY_TOKENS)), tokens)
        if cost is not None:
            costs[repo] = costs.get(repo, 0.0) + cost
    return totals, costs


def codex_tokens_per_repo(per_session, repo_paths, pricing):
    totals, costs = {}, {}
    for s in per_session:
        cwd = session_cwd(s["file"])
        repo = match_repo_by_cwd(cwd, repo_paths) or "(other/unmatched)"
        tokens, cost = codex_session_stats(s["file"], pricing)
        totals[repo] = _add_tokens(totals.get(repo, dict(EMPTY_TOKENS)), tokens)
        if cost is not None:
            costs[repo] = costs.get(repo, 0.0) + cost
    return totals, costs


def _add_tokens(a, b):
    return {k: a[k] + b.get(k, 0) for k in a}


def merge_numeric(a, b):
    merged = dict(a)
    for k, v in b.items():
        merged[k] = merged.get(k, 0) + v
    return merged


def merge_token_dicts(a, b):
    merged = {k: dict(v) for k, v in a.items()}
    for repo, tokens in b.items():
        merged[repo] = _add_tokens(merged.get(repo, dict(EMPTY_TOKENS)), tokens)
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


def token_total(tokens):
    return sum(tokens.values())


def render_repo_table(per_repo, hours_by_repo, tokens_by_repo, show_hours, show_tokens, top_n=12):
    if not per_repo:
        return "  (no matching commits — check --author, or run git config --global user.email)"
    rows = per_repo[:top_n]
    max_net = max(r["net"] for r in rows) or 1
    hcol = "  hours" if show_hours else ""
    tcol = "    tokens" if show_tokens else ""
    lines = [f"  {'repo':<24} {'':<{BAR_WIDTH}} {'net LOC':>9}  {'commits':>7}{hcol}{tcol}"]
    for r in rows:
        b = bar(r["net"], max_net)
        row = f"  {r['repo']:<24} {GREEN}{b}{RESET} {r['net']:>9,}  {r['commits']:>7,}"
        if show_hours:
            h = hours_by_repo.get(r["repo"])
            h_txt = f"{h / 3600:>6.1f}h" if h else f"{'-':>7}"
            row += f"  {MAGENTA}{h_txt}{RESET}"
        if show_tokens:
            t = token_total(tokens_by_repo.get(r["repo"], EMPTY_TOKENS))
            t_txt = f"{t:>10,}" if t else f"{'-':>10}"
            row += f"  {BLUE}{t_txt}{RESET}"
        lines.append(row)
    if len(per_repo) > top_n:
        lines.append(f"  {DIM}... +{len(per_repo) - top_n} more repos{RESET}")
    return "\n".join(lines)


def render(name, session_result, loc_result, hours_by_repo, tokens_by_repo, total_tokens, total_cost, period_label):
    show_hours = session_result is not None
    show_tokens = total_tokens is not None
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
    if show_tokens:
        print(stat_line("Tokens", f"{token_total(total_tokens):,}", BLUE,
                         sub=f"{total_tokens['input_tokens']:,} in, {total_tokens['output_tokens']:,} out, "
                             f"{total_tokens['cache_read_tokens']:,} cache-read"))
        if total_cost is not None:
            print(stat_line("Est. cost", f"${total_cost:,.2f}", GREEN,
                             sub="pay-as-you-go API rate — NOT your bill if on a subscription plan"))
        else:
            print(f"  {DIM}(cost unavailable — pricing fetch failed and no local cache; token counts above are still real){RESET}")
    print()
    print(f"  {BOLD}Per-repo (by net LOC{', hours = best-effort match' if show_hours else ''}){RESET}")
    print(render_repo_table(loc_result["per_repo"], hours_by_repo, tokens_by_repo, show_hours, show_tokens))
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
    ap.add_argument("--no-tokens", action="store_true", help="skip token/cost accounting (faster, hours+LOC only)")
    ap.add_argument("--vault-dir", default=os.getcwd(), help="folder containing your repos (default: cwd)")
    ap.add_argument("--cap-minutes", type=float, default=5.0)
    ap.add_argument("--author", action="append", default=None)
    ap.add_argument("--name", default=None, help="display name for the header (default: git config user.name)")
    ap.add_argument("--exclude-repo", action="append", default=None)
    ap.add_argument("--exclude-glob", action="append", default=None,
                     help="repeatable; extra LOC file patterns to exclude beyond the universal defaults")
    ap.add_argument("--no-exclude", action="store_true", help="count generated files too (raw LOC numbers)")
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
    loc_exclude = [] if args.no_exclude else (DEFAULT_LOC_EXCLUDE + (args.exclude_glob or []))
    loc_result = loc_aggregate(args.vault_dir, authors, loc_period, loc_exclude, args.exclude_repo)

    has_claude = os.path.isdir(args.projects_dir)
    has_codex = not args.no_codex and os.path.isdir(args.codex_dir)
    session_result = None
    hours_by_repo = {}
    tokens_by_repo = {}
    total_tokens = None
    total_cost = None
    cost_known = False

    pricing = fetch_pricing() if not args.no_tokens else None
    if not args.no_tokens and pricing is None:
        print("  ! pricing fetch failed, no cached pricing found — token counts still work, cost won't", file=sys.stderr)

    if has_claude:
        session_result = session_aggregate(args.projects_dir, args.cap_minutes, period=(since, until))
        prefix_len = len(args.projects_dir.rstrip("/")) + 1
        hours_by_repo = hours_per_repo(session_result["per_session"], args.vault_dir, prefix_len, args.exclude_repo)
        if not args.no_tokens:
            tokens_by_repo, cc_costs = claude_code_tokens_per_repo(
                session_result["per_session"], args.vault_dir, prefix_len, pricing, args.exclude_repo)
            total_tokens = {k: sum(t[k] for t in tokens_by_repo.values()) for k in EMPTY_TOKENS}
            total_cost = sum(cc_costs.values())
            cost_known = cost_known or bool(cc_costs)

    if has_codex:
        repo_paths = find_repos(args.vault_dir, args.exclude_repo)
        codex_by_repo, codex_result = codex_hours_per_repo(args.codex_dir, repo_paths,
                                                             args.cap_minutes, (since, until))
        hours_by_repo = merge_numeric(hours_by_repo, codex_by_repo)
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
        if not args.no_tokens:
            codex_tokens, codex_costs = codex_tokens_per_repo(codex_result["per_session"], repo_paths, pricing)
            tokens_by_repo = merge_token_dicts(tokens_by_repo, codex_tokens)
            codex_total = {k: sum(t[k] for t in codex_tokens.values()) for k in EMPTY_TOKENS}
            total_tokens = merge_numeric(total_tokens, codex_total) if total_tokens else codex_total
            total_cost = (total_cost or 0.0) + sum(codex_costs.values())
            cost_known = cost_known or bool(codex_costs)

    render(name, session_result, loc_result, hours_by_repo, tokens_by_repo,
           total_tokens, total_cost if cost_known else None, period_label)


if __name__ == "__main__":
    main()
