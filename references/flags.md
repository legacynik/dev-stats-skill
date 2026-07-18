# Flag reference

## `dev_stats.py` — the combined report

| Flag | Default | Meaning |
|---|---|---|
| `--vault-dir PATH` | cwd | Folder containing the repos to scan (one level deep) |
| `--projects-dir PATH` | `~/.claude/projects` | Claude Code session-log root |
| `--codex-dir PATH` | `~/.codex/sessions` | Codex CLI session-log root |
| `--no-codex` | off | Skip Codex CLI entirely |
| `--no-tokens` | off | Skip token/cost accounting (faster — reads only timestamps, not full file content) |
| `--cap-minutes N` | 5 | Gap-capping threshold for active-hours estimate |
| `--author EMAIL` | git global identity | Repeatable; add aliases for commits under other emails/names |
| `--name STR` | last `--author` value | Display name for the report header |
| `--exclude-repo NAME` | none | Repeatable; skip a repo by folder name (e.g. a fork) |
| `--days N` | none | Only the last N days (mutually exclusive with `--since`) |
| `--since YYYY-MM-DD` | none | Start of the window |
| `--until YYYY-MM-DD` | none | End of the window |

## `loc_stats.py` — LOC only, more exclude control

Same `--vault-dir`, `--author`, `--exclude-repo`, `--since`/`--until` as
above, plus:

| Flag | Default | Meaning |
|---|---|---|
| `--exclude-glob PATTERN` | none | Repeatable; extra file patterns to exclude from LOC (fnmatch syntax, e.g. `*/references/*/transcript-*.json`) |
| `--no-exclude` | off | Ignore all excludes, including the universal defaults — raw git numbers |
| `--json-out PATH` | none | Write the full result (including per-repo breakdown) as JSON |

## `backup_sessions.py` — archive before it ages out

| Flag | Default | Meaning |
|---|---|---|
| `--yes` | off | Required to actually copy files (otherwise dry-run report only) |
| `--archive-dir PATH` | `~/.dev-stats-archive` | Destination — must not be inside a git repo |
| `--dry-run` | off | Report what would be copied, never write, even with `--yes` |
| `--force` | off | Override the git-repo-destination refusal (not recommended — see `references/privacy.md`) |

## Pricing cache (`pricing.py`)

Not a CLI of its own — `dev_stats.py` calls it automatically unless
`--no-tokens` is set. Caches LiteLLM's pricing JSON at
`~/.cache/dev-stats-skill/litellm-pricing.json`, refetched if older than 24h;
falls back to a stale cache (or gives up gracefully, cost becomes
unavailable, token counts stay intact) if the network is down. Delete that
file to force a refetch on the next run.

## Worked example: excluding a project-specific noise pattern

Found via `git log --numstat`, summed by file, top offenders inspected (see
`references/methodology.md` for the "verify before excluding" rule). Note the
pattern has no leading `*/` — `git log --numstat` paths are relative to the
repo root with no prefix, so `*/references/...` would never match a path that
starts exactly with `references/...`; `fnmatch`'s `*` already spans `/`, so a
bare `*transcript-raw.json` matches at any depth:

```bash
python3 scripts/dev_stats.py --vault-dir ~/code \
  --exclude-glob '*transcript-raw.json' \
  --exclude-glob '*transcript-sentences.json'
```
