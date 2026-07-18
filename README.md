# dev-stats

A Claude Code skill (plugin) that reports personal dev productivity: active
hours from your local Claude Code and Codex CLI session transcripts, plus
lines of code contributed across your repos via `git log`. Runs entirely
locally — nothing is uploaded anywhere.

## What it measures

- **Active hours** — from `~/.claude/projects/**/*.jsonl` and
  `~/.codex/sessions/**/*.jsonl`. Gaps between consecutive messages longer than
  `--cap-minutes` (default 5) count as idle, not work. This is an
  approximation, not an authoritative source, and double-counts overlapping
  parallel sessions by design (if you run several sessions at once, their
  active time is summed independently — daily totals can exceed 24h).
- **Lines of code** — `git log --all --numstat` per repo, scoped to your git
  identity (`git config --global user.email`/`user.name`, or `--author`).
  `--all` walks every local branch, not just the checked-out one, so unmerged
  feature-branch work is counted too.

Neither source is authoritative on its own — this is a personal trend
estimate, not a payroll ledger.

## Install

```
/plugin marketplace add <your-org>/dev-stats-skill
/plugin install dev-stats
```

Or locally, for testing:

```
claude --plugin-dir /path/to/dev-stats-skill
```

## Use

Inside Claude Code: ask for a dev-stats report, or run the scripts directly:

```bash
python3 scripts/dev_stats.py                          # cwd's siblings, all-time
python3 scripts/dev_stats.py --vault-dir ~/code --days 30
python3 scripts/backup_sessions.py --yes               # archive session logs before they age out
```

See `python3 scripts/dev_stats.py --help` and `scripts/loc_stats.py --help`
for the full flag list (period filters, repo/glob excludes, author aliases).

## Requirements

- Python 3, stdlib only — no `pip install` needed.
- `git` on PATH.
- Works with zero local session transcripts too (falls back to LOC-only).

## Privacy

`backup_sessions.py` copies raw session transcripts (which may contain full
conversation/code text) to `~/.dev-stats-archive/` on your own machine. It
does not compress, encrypt, upload, or transmit anything — it refuses to
write inside any git repo (raw transcripts landing somewhere a later
`git add -A` could commit/push is the actual risk, not the copy itself).
Treat that directory like you'd treat the original `~/.claude/projects/` —
it's your data, kept local.

If your disk isn't already fully encrypted at rest (macOS: FileVault —
check with `fdesetup status`), or you want the archive in its own encrypted
container regardless, create one yourself (this prompts for a password
interactively — run it in your own terminal, not through an agent, so the
password never passes through anything else):

```bash
# macOS — encrypted sparse bundle, grows as needed up to 10g
hdiutil create -size 10g -encryption AES-256 -type SPARSEBUNDLE -fs APFS \
  -volname DevStatsArchive ~/DevStatsArchive

hdiutil attach ~/DevStatsArchive.sparsebundle          # mounts at /Volumes/DevStatsArchive, asks for password
python3 scripts/backup_sessions.py --yes --archive-dir /Volumes/DevStatsArchive
hdiutil detach /Volumes/DevStatsArchive                # unmount when done — locks it back up
```
