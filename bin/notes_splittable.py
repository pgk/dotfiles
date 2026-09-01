"""Long, multi-section notes that are not themselves an index — split candidates.

Structural signal only: headers and word count say a note has grown past one
idea's worth of content; out-degree says whether it is organising other notes
(a map of content) rather than sprawling on its own. No claim is made about
where one idea ends and another begins — that's for the reader, at the note.
"""

import os
import re
import sys

import notes_common

# [ \t]+, not \s+: \s crosses newlines, so a blank "## " line would otherwise
# consume the following blank line and capture the next paragraph as its title.
HEADER_RE = re.compile(r"^#{2,}[ \t]+(.+?)[ \t]*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def note_stats(path, raw, name_index, files):
    """words/headers from the frontmatter- and fence-stripped body; out_degree from raw links."""
    body = FENCE_RE.sub("", notes_common.strip_frontmatter(raw))
    words = len(body.split())
    headers = HEADER_RE.findall(body)
    out = set()
    for link_text in notes_common.extract_links(raw):
        target = notes_common.resolve_link(link_text, name_index)
        if target is not None and target != path and target in files:
            out.add(target)
    return {
        "name": os.path.splitext(os.path.basename(path))[0],
        "path": path,
        "words": words,
        "headers": headers,
        "out_degree": len(out),
    }


def select(files, name_index, min_headers, min_words, max_out_degree, vault):
    """Notes past the header/word gate that aren't themselves acting as an index."""
    files_set = set(files)
    candidates = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError as exc:
            print(f"warning: skipping unreadable note {notes_common.printable(path)}: "
                  f"{notes_common.printable(exc)}", file=sys.stderr)
            continue
        stats = note_stats(path, raw, name_index, files_set)
        past_gate = len(stats["headers"]) >= min_headers or stats["words"] >= min_words
        if past_gate and stats["out_degree"] < max_out_degree:
            stats["rel"] = os.path.relpath(path, vault)
            candidates.append(stats)
    candidates.sort(key=lambda e: (-e["words"], e["name"].lower()))
    return candidates


def format_lines(entries):
    """Picker/report rows for a 'Splittable' section — for notes-graph to splice in."""
    printable = notes_common.printable
    lines = [f"Splittable ({len(entries)})"]
    for e in entries:
        plural = "link" if e["out_degree"] == 1 else "links"
        lines.append(
            f"  {printable(e['name'])}  [{e['words']} words, {len(e['headers'])} sections, "
            f"{e['out_degree']} outbound {plural}]  {printable(e['rel'])}"
        )
        if e["headers"]:
            sections = " / ".join(printable(h) for h in e["headers"])
            lines.append(f"      sections: {sections}")
    return lines
