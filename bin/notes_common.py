"""Shared vault-walking, name-index, and link-parsing helpers for notes-graph and notes-deadlinks."""

import fnmatch
import os
import re
import sys

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")


def printable(text):
    """Strip control characters from note- or server-derived text before it reaches a terminal."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))


def iter_markdown_files(vault, excludes):
    vault_real = os.path.realpath(vault)
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            if not os.path.realpath(path).startswith(vault_real + os.sep):
                continue
            rel = os.path.relpath(path, vault)
            if any(fnmatch.fnmatch(rel, pattern) for pattern in excludes):
                continue
            yield path


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
