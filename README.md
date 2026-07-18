# dev-stats

A Claude Code skill that reports personal dev productivity: active hours
from your local Claude Code and Codex CLI session transcripts, lines of
code contributed across your repos via `git log`, and token usage with an
estimated cost. Runs entirely locally — nothing is uploaded anywhere, pricing
lookup is the only network call and it's optional (`--no-tokens` skips it).

## What it measures

- **Active hours** — from `~/.claude/projects/**/*.jsonl` and
  `~/.codex/sessions/**/*.jsonl`. Approximate, double-counts parallel
  sessions by design. Extensible to other coding agents — see
  `references/sources.md`.
- **Lines of code** — `git log --all --numstat` per repo, scoped to your git
  identity. Walks every local branch, not just the checked-out one.
- **Tokens + estimated cost** — from the same session logs (Claude Code's
  per-message `usage`, Codex CLI's cumulative `token_count` event), priced
  against LiteLLM's public pricing data (the same source ccusage uses).
  Always an estimate at pay-as-you-go API rates — **not your bill** if
  you're on a subscription plan.

Neither source is authoritative on its own — this is a personal trend
estimate, not a payroll ledger. Full detail on what each number can and
can't tell you: `references/methodology.md`.

## Install

```
/plugin marketplace add legacynik/dev-stats-skill
/plugin install dev-stats
```

Or locally, for testing: `claude --plugin-dir /path/to/dev-stats-skill`

## Use

Inside Claude Code, just ask for a dev-stats/productivity report — the skill
triggers on its own. Or run the scripts directly:

```bash
python3 scripts/dev_stats.py                          # cwd's siblings, all-time
python3 scripts/dev_stats.py --vault-dir ~/code --days 30
python3 scripts/backup_sessions.py --yes               # archive session logs before they age out
```

Full flag reference (period filters, repo/glob excludes, author aliases):
`references/flags.md`.

## Requirements

- Python 3, stdlib only — no `pip install` needed.
- `git` on PATH.
- Works with zero local session transcripts too (falls back to LOC-only).

## Privacy and the archive step

`backup_sessions.py` copies raw session transcripts to `~/.dev-stats-archive/`
and refuses to write inside a git repo. Details, and how to add your own
encrypted container on top of disk encryption: `references/privacy.md`.

## Repo layout

```
SKILL.md              — what Claude reads when this skill triggers
references/            — loaded on demand, not upfront
  sources.md           — session-log formats + how to add a new agent
  methodology.md        — what each number means, common misreadings
  flags.md              — full CLI reference
  privacy.md             — archive step, encryption
scripts/               — the actual implementation (stdlib only — pricing.py
                          makes one HTTP call via urllib, no pip installs)
evals/evals.json       — example prompts this skill should handle
```

## Credits

Built by [Niccolò Franzin](https://github.com/legacynik) with Claude Code —
paired on the design, every fix in `references/methodology.md` traces back
to something caught and verified live during that session (not just assumed
to work).
