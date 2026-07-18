# Session-log sources

`dev_stats.py` ingests active-hours data from any tool that keeps a local,
per-session log of timestamped events. Two are wired in today, verified
against real files on disk. This doc describes both, plus the checklist for
adding a third.

## Claude Code — `~/.claude/projects/**/*.jsonl`

- **Layout**: one directory per project, named by cwd-encoding — every `/`
  and space in the working-directory path is replaced with `-`
  (`/Users/me/code/My Repo` → `-Users-me-code-My-Repo`). Under each project
  directory, one `.jsonl` file per session (plus a `subagents/` subfolder for
  subagent transcripts, same format).
- **Timestamp field**: every line that's a message event has a top-level
  `"timestamp"` key, ISO 8601 (`2026-06-12T10:36:21.888Z`).
- **Repo attribution**: from the project-directory NAME, not file content —
  `session_duration_stats.py` doesn't need to know this; `dev_stats.py`'s
  `hours_per_repo()` does the folder-name substring match (see
  `references/methodology.md` for why substring, not exact match).
- Implemented in: `scripts/session_duration_stats.py` (`load_timestamps`,
  `aggregate`) + the folder-matching in `scripts/dev_stats.py`
  (`hours_per_repo`).

## Codex CLI — `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`

- **Layout**: organized by DATE, not by project — every rollout file from
  every cwd lands under the same year/month/day tree.
- **Timestamp field**: also a top-level `"timestamp"` key, ISO 8601 — this is
  why `session_duration_stats.aggregate()` works UNMODIFIED when pointed at
  this directory instead of Claude Code's; the core scan only ever looks for
  that one field.
- **Repo attribution**: NOT from the file path (dates don't tell you the
  repo). The first `session_meta` event in each file carries a `"cwd"` field
  with the absolute working directory. `scripts/codex_repo_hours.py` reads
  just that one line per file and matches `cwd` against known repo paths
  (exact match or `cwd.startswith(repo_path + "/")` for worktrees/subdirs).
- Implemented in: `scripts/codex_repo_hours.py`.

## Adding a third source

Before wiring anything in, verify — don't assume a tool's local storage
looks like either of the above. Find where it keeps session data, open a
real file, and check two things:

1. **Does each session file carry parseable timestamps?** If there's a
   top-level `"timestamp"` key (any ISO-8601-ish format
   `datetime.fromisoformat` can parse after a `Z`→`+00:00` swap), you can
   likely reuse `session_duration_stats.aggregate()` directly — pass the
   tool's log directory as `projects_dir`. If the field is named differently
   or nested, you need a small variant of `load_timestamps()`, not a
   rewrite of the gap-capping math in `session_stats()`.

2. **How is a session tied to a repo/cwd?** Three patterns exist in
   practice (Claude Code and Codex CLI each show one):
   - Encoded in the **directory/file path** itself (Claude Code) — write a
     matcher like `dev_stats.py`'s `match_repo()`.
   - A **field inside the file** (Codex CLI's `session_meta.cwd`) — write a
     matcher like `codex_repo_hours.py`'s `session_cwd()` +
     `match_repo_by_cwd()`.
   - Not recorded at all — hours from that source can only be reported as a
     grand total, not broken down per repo. Say so; don't guess an
     attribution the data doesn't support.

Once both are known, wire it into `dev_stats.py` the same way Codex CLI is:
a `--<tool>-dir` flag defaulting to the tool's real path, an
`os.path.isdir()` check before scanning (never crash because a machine
doesn't have that tool installed), and a merge into `hours_by_repo` /
`session_result` totals via `merge_hours()`.

**Not yet done for any other agent** (opencode or otherwise) — this section
is the recipe, not a claim that it's already wired in. Verify the actual
format before writing the integration; don't infer it from this doc's
Claude Code/Codex CLI examples.
