"""Well-connected notes that have gone untouched — the inverse of the activity view.

Degree is what separates a note worth returning to from an abandoned stub, which
is why it both filters and ranks here.
"""

import json
import os

import notes_common

HOUR = 3600
DAY = 86400


def untouched_before(files, cutoff):
    """{path: mtime} for notes last modified at or before cutoff."""
    return {p: m for p, m in notes_common.note_mtimes(files).items() if m <= cutoff}


def describe_span(seconds):
    if seconds < HOUR:
        minutes = int(seconds // 60)
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    if seconds < DAY:
        hours = int(seconds // HOUR)
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    days = int(seconds // DAY)
    if days < 30:
        return f"{days} day" if days == 1 else f"{days} days"
    if days < 365:
        months = days // 30
        return f"{months} month" if months == 1 else f"{months} months"
    years = days // 365
    return f"{years} year" if years == 1 else f"{years} years"


def select(graph, stale, min_links, limit, vault, now):
    """Rank stale notes by connections, then by how long they have been untouched.

    `graph` covers the whole vault, never `stale` alone: a note linked from fifty
    recently-edited notes is well connected, and a graph scoped to the stale set
    would report it as sparse.

    `considered` counts every candidate, so a limit truncating the list stays
    visible instead of passing for the total.
    """
    entries = []
    for path, mtime in stale.items():
        degree = len(graph[path]["neighbors"])
        if degree < min_links:
            continue
        entries.append(
            {
                "name": os.path.splitext(os.path.basename(path))[0],
                "path": path,
                "rel": os.path.relpath(path, vault),
                "degree": degree,
                "mtime": mtime,
                "age_seconds": round(now - mtime),
                "age": describe_span(now - mtime),
            }
        )
    entries.sort(key=lambda e: (-e["degree"], e["mtime"], e["name"].lower()))
    considered = len(entries)
    if limit and limit > 0:
        entries = entries[:limit]
    return entries, considered


def format_text(entries, considered, window, total, vault):
    lines = [
        f"Neglected in {vault} — {considered} of {total} notes are well connected "
        f"and untouched for {window}"
    ]
    # "Untouched" is a claim about the sync setup, not about the user.
    lines.append("  (untouched = mtime, which assumes sync does not rewrite it)")
    if not entries:
        lines.append("")
        lines.append("Nothing has been neglected that long.")
        return "\n".join(lines)
    lines.append("")
    if len(entries) < considered:
        lines.append(f"Showing the {len(entries)} best connected of {considered}")
    printable = notes_common.printable
    for e in entries:
        plural = "link" if e["degree"] == 1 else "links"
        lines.append(
            f"  {printable(e['name'])}  [{e['degree']} {plural}]  "
            f"untouched {e['age']}  {printable(e['rel'])}"
        )
    return "\n".join(lines)


def format_json(entries, considered, window, total, vault):
    return json.dumps(
        {
            "vault": vault,
            "window": window,
            "total_notes": total,
            "considered": considered,
            "neglected": entries,
        },
        indent=2,
    )
