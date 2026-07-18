#!/usr/bin/env python3
"""Aggregate lines-added/removed + commit counts per repo for a given git author.

Scans every git repo directly under --vault-dir (one level deep) and runs
`git log --all --numstat`, OR-matching every --author pattern given (git log's
--author is itself an OR when repeated). --all walks every local branch/ref,
not just the checked-out one — a repo with unmerged feature branches otherwise
hides most commits. git dedupes by SHA across refs, so this does not double-count
a commit reachable from two branches; it CAN double-count if a branch was
squash-merged and the pre-squash branch ref is still around locally (delete
merged branches to avoid that — not auto-detected here).

Binary-file numstat rows ("-\t-\tpath") are skipped, they carry no line count.
Worktrees are skipped (their `.git` is a file pointing at the main repo's
gitdir, not a real repo — counting both double-counts shared history).

By default, no author is assumed: run once with no flags and it uses your
global git identity (`git config --global user.email`/`user.name`). Add
aliases with repeatable --author if you commit under more than one email.

Usage:
    python3 loc_stats.py [--vault-dir PATH] [--author EMAIL ...]
                          [--exclude-repo NAME ...] [--exclude-glob PATTERN ...]
                          [--json-out PATH]
"""
import argparse
import fnmatch
import glob
import json
import os
import subprocess
import sys

# Diffs that inflate LOC without being hand-written work, true regardless of
# project: package-manager lockfiles, vendored 3D mesh/geometry data. Anything
# more project-specific (a wiki index that self-regenerates, eval data dumps,
# ...) is NOT assumed here — add it per-project with --exclude-glob.
DEFAULT_EXCLUDE = [
    "*pnpm-lock.yaml", "*package-lock.json", "*yarn.lock", "*.lock",
    "*.obj", "*.stl", "*.fbx",
]


def git_config(key):
    try:
        out = subprocess.run(["git", "config", "--global", "--get", key],
                              capture_output=True, text=True, timeout=5).stdout.strip()
        return out or None
    except Exception:
        return None


def default_authors():
    return [a for a in (git_config("user.email"), git_config("user.name")) if a]


def is_excluded(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def find_repos(vault_dir, repo_exclude=None):
    repos = (p.rsplit("/.git", 1)[0] for p in glob.glob(f"{vault_dir}/*/.git") if os.path.isdir(p))
    return sorted(r for r in repos if r.rsplit("/", 1)[-1] not in (repo_exclude or []))


def repo_loc(repo_path, authors, period=None, exclude=DEFAULT_EXCLUDE):
    since, until = period or (None, None)
    cmd = ["git", "-C", repo_path, "log", "--all"]
    for a in authors:
        cmd.append(f"--author={a}")
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    cmd += ["--pretty=tformat:__COMMIT__", "--numstat"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return None
    added = removed = commits = excluded_lines = 0
    for line in out.splitlines():
        if line == "__COMMIT__":
            commits += 1
            continue
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-":
            continue
        if exclude and is_excluded(parts[2], exclude):
            excluded_lines += int(parts[0]) + int(parts[1])
            continue
        added += int(parts[0])
        removed += int(parts[1])
    if commits == 0:
        return None
    return {"repo": repo_path.rsplit("/", 1)[-1], "added": added, "removed": removed,
            "net": added - removed, "commits": commits, "excluded_lines": excluded_lines}


def aggregate(vault_dir, authors, period=None, exclude=DEFAULT_EXCLUDE, repo_exclude=None):
    repos = find_repos(vault_dir, repo_exclude)
    per_repo = [r for r in (repo_loc(p, authors, period, exclude) for p in repos) if r]
    per_repo.sort(key=lambda r: r["net"], reverse=True)
    return {
        "vault_dir": vault_dir,
        "authors": authors,
        "repos_scanned": len(repos),
        "total_added": sum(r["added"] for r in per_repo),
        "total_removed": sum(r["removed"] for r in per_repo),
        "total_commits": sum(r["commits"] for r in per_repo),
        "per_repo": per_repo,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault-dir", default=os.getcwd(), help="folder containing your repos (default: cwd)")
    ap.add_argument("--author", action="append", default=None,
                     help="repeatable; defaults to your global git identity")
    ap.add_argument("--exclude-repo", action="append", default=None, help="repeatable; skip a repo by name")
    ap.add_argument("--exclude-glob", action="append", default=None, help="repeatable; extra file patterns to skip")
    ap.add_argument("--since", default=None, help="git log --since date, e.g. 2026-07-01")
    ap.add_argument("--until", default=None, help="git log --until date")
    ap.add_argument("--no-exclude", action="store_true", help="count generated files too (raw git numbers)")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    authors = args.author or default_authors()
    if not authors:
        print("No author found — set git config --global user.email, or pass --author.", file=sys.stderr)
        sys.exit(1)

    exclude = [] if args.no_exclude else (DEFAULT_EXCLUDE + (args.exclude_glob or []))
    result = aggregate(args.vault_dir, authors, (args.since, args.until), exclude, args.exclude_repo)
    excluded = sum(r["excluded_lines"] for r in result["per_repo"])
    print(f"Author(s): {', '.join(authors)}", file=sys.stderr)
    print(f"Repos scanned: {result['repos_scanned']}, "
          f"with matching commits: {len(result['per_repo'])}", file=sys.stderr)
    if excluded:
        print(f"Excluded (generated files): {excluded:,} lines", file=sys.stderr)
    print(f"Total: +{result['total_added']:,} -{result['total_removed']:,} lines, "
          f"{result['total_commits']:,} commits")

    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"Full JSON written to {args.json_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
