#!/usr/bin/env python3
"""Archive local Claude Code + Codex CLI session transcripts before they age out.

Claude Code and Codex CLI keep local session logs, but they are not guaranteed
to stick around forever — cleanup settings vary per install (see each tool's
own docs/config for its current default). If a report only ever looks at
"whatever's on disk right now", history quietly shrinks between runs. This
copies the raw .jsonl files to a persistent archive directory, incrementally
(skips a file already archived at the same size), so a monthly dev-stats
report can look back further than the live retention window.

This is a plain copy of raw session transcripts — they may contain the full
text of your conversations/code. The archive directory is created with your
normal user permissions, nothing is uploaded anywhere.

Usage:
    python3 backup_sessions.py --yes [--archive-dir PATH] [--dry-run]
"""
import argparse
import glob
import os
import shutil
import sys

DEFAULT_ARCHIVE = os.path.expanduser("~/.dev-stats-archive")
SOURCES = {
    "claude-projects": os.path.expanduser("~/.claude/projects"),
    "codex-sessions": os.path.expanduser("~/.codex/sessions"),
}


def inside_git_repo(path):
    """Walk up from path looking for a .git — raw transcripts must never land
    somewhere a later `git add -A` could scoop them into a commit/push."""
    cur = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def plan_copy(source_dir, dest_dir):
    to_copy = []
    already = 0
    for src in glob.glob(f"{source_dir}/**/*.jsonl", recursive=True):
        rel = os.path.relpath(src, source_dir)
        dst = os.path.join(dest_dir, rel)
        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
            already += 1
            continue
        to_copy.append((src, dst))
    return to_copy, already


def do_copy(to_copy):
    for src, dst in to_copy:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true", help="required to actually copy files")
    ap.add_argument("--archive-dir", default=DEFAULT_ARCHIVE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="allow --archive-dir inside a git repo (not recommended)")
    args = ap.parse_args()

    repo_root = inside_git_repo(args.archive_dir)
    if repo_root and not args.force:
        print(f"Refusing: {args.archive_dir} is inside a git repo ({repo_root}).\n"
              f"Raw session transcripts can contain full conversation/code text — a later\n"
              f"`git add -A` in that repo could commit and push them. Pick a path outside any\n"
              f"git repo (the default, {DEFAULT_ARCHIVE}, already is), or pass --force to override.",
              file=sys.stderr)
        sys.exit(1)

    total_new = 0
    for label, source_dir in SOURCES.items():
        if not os.path.isdir(source_dir):
            continue
        dest_dir = os.path.join(args.archive_dir, label)
        to_copy, already = plan_copy(source_dir, dest_dir)
        print(f"{label}: {len(to_copy)} new/changed, {already} already archived", file=sys.stderr)
        total_new += len(to_copy)
        if to_copy and args.yes and not args.dry_run:
            do_copy(to_copy)
            print(f"  -> copied to {dest_dir}", file=sys.stderr)

    if total_new and not args.yes:
        print(f"\n{total_new} files would be archived to {args.archive_dir} "
              f"— rerun with --yes to actually copy.", file=sys.stderr)
    elif not total_new:
        print("Nothing new to archive.", file=sys.stderr)


if __name__ == "__main__":
    main()
