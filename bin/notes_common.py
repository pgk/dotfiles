"""Shared vault-walking, name-index, and link-parsing helpers for the notes-* CLI tools."""

import fnmatch
import os
import re
import sys

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")


def printable(text):
    """Strip control characters from note- or server-derived text before it reaches a terminal."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))


def require_vault(vault):
    """Resolve the vault path, refusing to invent one.

    None of the notes-* tools carry an implicit ~/notes default. A mistyped or
    option-swallowed argument must never resolve to the user's real vault, so
    the path has to be named — as an argument or via $NOTES_VAULT. Call this
    before the vault is read, so a bad invocation costs nothing.
    """
    if vault and vault.strip():
        return vault
    from_env = os.environ.get("NOTES_VAULT", "").strip()
    if from_env:
        return from_env
    raise ValueError("a VAULT path is required — pass it as an argument or set $NOTES_VAULT")


def matched_excludes(rel, patterns):
    """Which patterns exclude this vault-relative path.

    A pattern is tested against the path *and* every directory above it, so
    `--exclude journal` excludes the whole subtree rather than nothing — matching
    only whole relative paths meant a bare directory name silently excluded no
    files at all. Matching is case-insensitive because the vault normally lives on
    a case-insensitive filesystem, where `Journal` and `journal` are the same
    directory and a capitalised pattern would otherwise miss it.

    This is the only thing keeping a subtree out of notes-similar's upload, so it
    fails loudly (see the warning in iter_markdown_files) rather than silently.
    """
    targets = [rel]
    parent = os.path.dirname(rel)
    while parent:
        targets.append(parent)
        parent = os.path.dirname(parent)
    lowered = [t.lower() for t in targets]
    return {
        pattern
        for pattern in patterns
        if any(fnmatch.fnmatchcase(t, pattern.rstrip("/").lower()) for t in lowered)
    }


def iter_markdown_files(vault, excludes):
    vault_real = os.path.realpath(vault)
    used = set()
    for root, dirs, files in os.walk(vault):
        keep = []
        for name in sorted(dirs):
            if name.startswith("."):
                continue
            hit = matched_excludes(os.path.relpath(os.path.join(root, name), vault), excludes)
            if hit:
                # Pruned, not just filtered: an excluded subtree is never walked.
                used |= hit
                continue
            keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            if not os.path.realpath(path).startswith(vault_real + os.sep):
                continue
            hit = matched_excludes(os.path.relpath(path, vault), excludes)
            if hit:
                used |= hit
                continue
            yield path
    for pattern in excludes:
        if pattern not in used:
            print(f"warning: --exclude {printable(pattern)} matched nothing", file=sys.stderr)


def build_name_index(files):
    index = {}
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        if stem in index:
            print(
                f"warning: duplicate note name '{printable(stem)}', keeping {printable(index[stem])}",
                file=sys.stderr,
            )
            continue
        index[stem] = path
    return index


def extract_links(text):
    links = []
    for raw in WIKILINK_RE.findall(text):
        target = raw.split("#", 1)[0].strip()
        target = os.path.basename(target.replace("\\", "/"))
        if target:
            links.append(target)
    return links


def resolve_link(link_text, name_index):
    if link_text.lower().endswith(".md"):
        link_text = link_text[:-3]
    return name_index.get(link_text.lower())
