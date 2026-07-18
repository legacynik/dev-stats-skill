# Privacy — the archive step

`backup_sessions.py` copies raw session transcripts (`~/.claude/projects/**/*.jsonl`,
`~/.codex/sessions/**/*.jsonl`) to `~/.dev-stats-archive/` by default. These
files can contain the full text of conversations and code discussed in them
— treat the archive like you'd treat the originals.

## Why it refuses to write inside a git repo

The realistic risk here isn't the copy itself (same machine, same user
permissions as the source) — it's a LATER `git add -A` in whatever repo the
archive happens to sit inside, which would stage and potentially push those
raw transcripts to a remote. `inside_git_repo()` walks up from
`--archive-dir` looking for a `.git`, and refuses to proceed if it finds one
(`--force` overrides this — don't, unless you have a specific reason and
know what you're doing).

The default (`~/.dev-stats-archive`) sits directly under the user's home
directory, outside any repo, specifically to make this the automatic safe
case rather than something the user has to remember to get right.

## Extra encryption on top of disk encryption

If the disk isn't already encrypted at rest (macOS: check with
`fdesetup status` — if FileVault is already on, the archive is already
covered for "device lost/stolen while off"), or a dedicated encrypted
container is wanted regardless, create one manually — this prompts for a
password interactively, so run it yourself rather than through an agent, so
the password stays only with you:

```bash
# macOS — encrypted sparse bundle, grows as needed up to 10g
hdiutil create -size 10g -encryption AES-256 -type SPARSEBUNDLE -fs APFS \
  -volname DevStatsArchive ~/DevStatsArchive

hdiutil attach ~/DevStatsArchive.sparsebundle    # mounts at /Volumes/DevStatsArchive, asks for password
python3 scripts/backup_sessions.py --yes --archive-dir /Volumes/DevStatsArchive
hdiutil detach /Volumes/DevStatsArchive          # unmount when done — locks it back up
```
