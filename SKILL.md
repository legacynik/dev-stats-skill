---
name: dev-stats
description: Report personal dev productivity — active hours from local Claude Code and Codex CLI session transcripts, plus lines-of-code contributed across your repos via git log. Use whenever the user asks "how much did I code", wants a coding/productivity report, a monthly recap, hours-worked or lines-of-code numbers, or a shareable stats card of their own dev activity — even if they don't name this skill directly.
allowed-tools: Bash(python3 *)
disable-model-invocation: true
---

# dev-stats

Two steps, in order, every time this skill runs.

## 1. Offer to archive session transcripts first

Local session logs (Claude Code, Codex CLI, and other coding agents) are not
guaranteed to be kept forever — retention depends on each tool's own settings,
which the user may not have touched. Reading "whatever's on disk right now"
without archiving means history quietly shrinks between runs.

Ask the user directly: **"Want me to archive your local session transcripts
first, so history doesn't get lost before your next report?"** Don't skip
this even if it feels repetitive — the answer can change, and the archive
step is cheap (incremental, a no-op if nothing changed).

- Yes: `python3 ${CLAUDE_SKILL_DIR}/scripts/backup_sessions.py --yes`
- No / unclear: skip it, move on, don't ask twice in the same run.

Details on where it archives to, and why it refuses to write inside a git
repo, are in `references/privacy.md` — read that before overriding
`--archive-dir`.

## 2. Run the report

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/dev_stats.py
```

Common flags: `--vault-dir PATH` (folder containing the user's repos, default
cwd), `--days N` / `--since YYYY-MM-DD [--until YYYY-MM-DD]` (time window),
`--author EMAIL` (repeatable, adds identity aliases), `--exclude-repo NAME`
(repeatable — e.g. a fork that isn't original work), `--no-codex`. Full flag
reference, including `loc_stats.py`'s own excludes and period filters: see
`references/flags.md`.

If the tool reports **"No author found"**: the user needs
`git config --global user.email "you@example.com"` set once, or pass
`--author`. If it falls back to **LOC-only** (no session transcripts found on
this machine), say so plainly — don't imply hours were measured when they
weren't.

## What each number means, and where it can mislead

Read `references/methodology.md` before presenting numbers as a finished
report, not just when something looks wrong. It covers: why `git log --all`
matters (unmerged branches are real work), why raw LOC without excludes is
noisy (lockfiles, vendored assets, self-regenerating files), why active
hours can exceed 24h/day (parallel sessions are summed independently, by
design), and why a repo import/rename can split one person's history across
two repo names in the per-repo table.

## Adding a new session-log source

Currently ingests Claude Code and Codex CLI. To add another coding agent
(opencode or anything else with local session logs), see
`references/sources.md` — it documents the two existing sources' formats and
the checklist for plugging in a third, generically.

## What this does NOT do

- Does not modify git history or any repo.
- Does not upload anything anywhere — everything runs and stays local.
- Does not fabricate a number it can't measure — a repo with zero matching
  commits in the window just doesn't appear, rather than showing a zero row.
