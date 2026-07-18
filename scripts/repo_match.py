#!/usr/bin/env python3
"""Repo-attribution matchers shared by hours and token accounting.

Two patterns, one per session-log source (see references/sources.md for why
they differ): Claude Code encodes cwd into the project-folder NAME, Codex CLI
records cwd as a FIELD inside the file.
"""


def repo_label(repo_name):
    return repo_name.replace(" ", "-")


def match_repo(folder_name, labels_to_names):
    """Claude Code: substring-match a cwd-encoded folder name against known repo labels."""
    for label, name in labels_to_names:  # caller pre-sorts longest label first
        if label in folder_name:
            return name
    return "(other/unmatched)"


def match_repo_by_cwd(cwd, repo_paths):
    """Codex CLI: exact/prefix-match a recorded cwd against known repo paths."""
    if not cwd:
        return None
    for path in sorted(repo_paths, key=len, reverse=True):
        if cwd == path or cwd.startswith(path + "/"):
            return path.rsplit("/", 1)[-1]
    return None


def labels_to_names(repo_paths):
    return sorted(
        ((repo_label(p.rsplit("/", 1)[-1]), p.rsplit("/", 1)[-1]) for p in repo_paths),
        key=lambda t: len(t[0]), reverse=True,
    )
