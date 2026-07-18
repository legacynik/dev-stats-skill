---
name: dev-stats
description: Report personal dev productivity — active hours from local Claude Code and Codex CLI session transcripts, plus lines-of-code contributed across your repos via git log. Use when the user asks for a coding/productivity report, "how much did I code", monthly recap, or similar.
allowed-tools: Bash(python3 *)
disable-model-invocation: true
---

# dev-stats

Two things happen in order, every time this skill runs.

## 1. Offer to archive session transcripts first

Local session logs (Claude Code, Codex CLI) are not guaranteed to be kept forever —
retention depends on the install's own settings, which the user may not have
touched. If you only ever read "whatever's currently on disk", history quietly
shrinks between runs and old months become unrecoverable.

Ask the user directly: **"Want me to archive your local session transcripts first,
so history doesn't get lost before your next report?"** Do not skip this ask even if
it feels repetitive across sessions — the user's answer can change, and running it
is cheap (it's incremental, a no-op if nothing changed since last time).

- If yes: `python3 ${CLAUDE_SKILL_DIR}/scripts/backup_sessions.py --yes`
- If no or unclear: skip it, move on. Don't nag a second time in the same run.

## 2. Run the report

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/dev_stats.py
```

Useful flags (pass through if the user asks for a specific slice):
- `--vault-dir PATH` — folder containing the user's repos (default: cwd)
- `--days N` / `--since YYYY-MM-DD [--until YYYY-MM-DD]` — time window
- `--author EMAIL` (repeatable) — add aliases beyond the git global identity
- `--exclude-repo NAME` (repeatable) — skip a repo (e.g. a fork that isn't original work)
- `--no-codex` — Claude Code hours only, skip Codex CLI

If the tool reports **"No author found"**, tell the user to run
`git config --global user.email "you@example.com"` once, or pass `--author`.

If it falls back to **LOC-only** (no session transcripts found on this machine),
say so plainly — don't imply hours were measured when they weren't.

## What this does NOT do

- Does not modify git history or any repo.
- Does not upload anything anywhere — everything runs and stays local.
- Does not guess at numbers it can't measure (a repo with zero matching commits
  in the window just doesn't appear, rather than showing a fabricated zero row).
