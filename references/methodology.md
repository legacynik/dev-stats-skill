# Methodology — what each number means, and where it lies to you

## Tokens and cost estimate

Token counts come straight from each tool's own accounting, not a re-count:
Claude Code's `message.usage` per assistant message (priced per-message, since
one session can mix models — a Haiku subagent call inside a Sonnet session,
for example), Codex CLI's cumulative `token_count` event (the LAST one per
session file is that session's running total — no need to sum deltas).

Cost is estimated against **LiteLLM's public, hourly-updated pricing JSON**
(`scripts/pricing.py`) — the same source ccusage (the established Claude
Code/Codex usage tool) uses, fetched directly instead of a hand-maintained
table that would go stale. Two things this number is NOT:

- **Not your actual bill if you're on a subscription plan** (Claude
  Pro/Max, a flat-rate Codex plan, etc.) — it's what the same token volume
  would cost at pay-as-you-go API rates. Present it labeled as an estimate,
  every time, never as "what you paid."
- **Not complete for Codex CLI.** The `token_count` event exposes
  `input_tokens`, `cached_input_tokens` (a SUBSET of input_tokens, verified:
  `input_tokens + output_tokens == total_tokens` on real data — billed as
  fresh-input-minus-cached at the input rate, cached at the discount rate),
  and `output_tokens` — but no cache-CREATION count. Codex sessions that
  wrote a lot of new cache this session will under-estimate cost; there's no
  way to recover that from this event, it's a real gap in the source data,
  not something `token_stats.py` failed to parse.

If a model name in the transcripts doesn't match anything in LiteLLM's
table (exact match first, then the name with a trailing `-YYYYMMDD` date
suffix stripped), that message/session's tokens are still counted in the
token total, but its cost is silently excluded from the cost sum — a new or
very recently released model not in LiteLLM's table yet will under-state
the total cost, not error out. The aggregate cost line only goes fully
"unavailable" when NOTHING could be priced at all (pricing fetch failed and
there's no local cache) — partial coverage looks like a normal number, it
just isn't complete. Don't present it as exact.

## `git log --all`, not just the checked-out branch

`loc_stats.py` walks every local branch/ref (`--all`), not only `HEAD`. On a
repo with unmerged feature branches — normal, not an edge case — HEAD-only
undercounts badly: verified on one real repo, 760 commits on HEAD vs 1,262
with `--all` over the same 44 days. git dedupes by commit SHA across refs, so
`--all` itself does not double-count a commit reachable from two branches.

It CAN double-count if a branch was squash-merged and the pre-squash branch
ref is still around locally — both the squash commit and the originals are
unique SHAs, and `--all` walks both. Delete merged branches to avoid this;
nothing here detects or collapses squash-duplicates automatically.

## Excludes are a menu, not a universal truth

`loc_stats.py`'s `DEFAULT_EXCLUDE` only contains patterns that are noise
*everywhere*: package-manager lockfiles, vendored 3D mesh formats. Everything
else that inflates a specific repo's line count — a wiki index that
self-regenerates on every commit, eval/debug data dumps, scraped YouTube
transcripts saved as reference material — is real in ONE project's
conventions and would be a false exclusion in someone else's. Those go
through `--exclude-glob`, decided per project, never assumed by default.

Two confirmed examples from real repos, both found by checking WHERE the
lines actually came from before excluding anything (`git log --numstat`,
sum by file, look at the top offenders — never exclude on a hunch):

- A `.wiki/.manifest.json` rewritten by a post-commit hook on ~every commit:
  39 commits, ~1,964 lines/commit average, in a repo where it was inflating
  the total by roughly 10%.
- `references/**/transcript-raw.json` + `transcript-sentences.json` (scraped
  YouTube transcripts, saved as research reference material): 62,059 of one
  repo's 121,502 lines over 44 days — over half the "code" in that repo was
  downloaded, not typed.

The inverse mistake is just as real: `.excalidraw`/`.excalidrawlib` files
LOOK like generated JSON (verbose, full of coordinates) but are hand-drawn
diagrams (source: excalidraw.com, real dragged shapes) — excluding those by
default would hide genuine work. Verify before excluding; don't pattern-match
on "looks like data."

## Active hours: gaps, caps, and why days can show >24h

`session_duration_stats.py` sums, per session, the gaps between consecutive
message timestamps — capped at `--cap-minutes` (default 5) so a long
away-from-keyboard gap doesn't count as work. This is deliberately an
UNDER-estimate of "time thinking about the problem" and an approximation of
"time actively driving the tool."

Sessions run in parallel are summed independently, by design — if the user
runs 3 Claude Code panels and 2 Codex sessions at once, that's up to 5x
simultaneous active-hour accumulation for the same wall-clock hour. A
44-day total of ~28h/day active work is not a data bug if the user genuinely
runs several sessions in parallel; say so plainly if a number implies more
than 24h/day, don't silently round it away.

## A repo rename/import can split one person's history in two

If a project started life inside a monorepo and was later split out into its
own repo (`git log --reverse` on the new repo shows an early commit like
"initial import from X monorepo"), the pre-split commits are still in the
OLD repo's own git history under the old repo's name — not lost, just
attributed to a different label in the per-repo table than the user might
expect. Check `git log --reverse --format="%ci %s" | head -3` on a repo
before concluding its low numbers mean "I didn't work on this much" — it
might mean "most of the history lives under a different name."

## Repo-name matching is best-effort, not exact

- Claude Code: repo attribution is a SUBSTRING match against the
  cwd-encoded project-folder name — a worktree checked out under a
  differently-named path can still match its parent repo's label correctly,
  but a repo whose name is a substring of an unrelated folder name could
  theoretically mismatch. Worktrees are explicitly excluded from
  `find_repos()` (their `.git` is a file, not a directory) specifically to
  avoid double-counting the same history under two labels.
- Codex CLI: repo attribution is an exact/prefix match against each
  session's recorded `cwd` — more precise than the Claude Code substring
  match, but only as good as what `cwd` the session actually ran from
  (a session invoked from a script or a different shell context might not
  match a repo path at all — see the "(other/unmatched)" bucket).

Never present a per-repo number as more precise than this — "best-effort
match" belongs in the same breath as the number, not as fine print nobody
reads.
