"""Text and JSON rendering for ariadne-similar.

Split from the tool so the ranking logic and its presentation can each be read
on their own.
"""

import json
import os

import ariadne_cluster
import ariadne_common

_printable = ariadne_common.printable


def format_text(target, results, total, include_linked, vault, shape=None, grouped=False):
    name = _printable(target["name"])
    if not results:
        scope = "similar" if include_linked else "unlinked similar"
        return f"No {scope} notes found for '{name}' among {total} notes in {vault}."
    scope = "Similar" if include_linked else "Unlinked similar"
    lines = [f"{scope} to '{name}' ({len(results)} of {total} notes in {vault})"]
    if shape:
        lines.append(ariadne_cluster.describe_shape(shape))
    for title, rows in (_grouped(results) if grouped else [(None, results)]):
        lines.append("")
        if title:
            lines.append(f"{title} ({len(rows)})")
        for r in rows:
            lines += _result_lines(r, vault)
    return "\n".join(lines)


def _grouped(results):
    """(title, rows) pairs. Every non-crossing row is in the target's own cluster."""
    crossing = [r for r in results if r["crosses"]]
    within = [r for r in results if not r["crosses"]]
    groups = []
    if crossing:
        groups.append(("Bridging other clusters", crossing))
    if within:
        where = within[0]["cluster"]
        groups.append((f"Within cluster {where}" if where is not None else "Within the same cluster", within))
    return groups


def _result_lines(r, vault):
    mark = " [linked]" if r["linked"] else ""
    if r["crosses"] and r["cluster"] is not None:
        mark += f" [cluster {r['cluster']}]"
    lines = [f"  {r['score']:.4f}  {_printable(r['name'])}{mark}"]
    if r["preview"]:
        lines.append(f"          {_printable(r['preview'])}")
    lines.append(f"          {_printable(os.path.relpath(r['path'], vault))}")
    return lines


def format_json(target, results, include_linked, vault, model, error=None, shape=None):
    return json.dumps(
        {
            "vault": vault,
            "model": model,
            "available": error is None,
            "error": error,
            "unlinked_only": not include_linked,
            "shape": shape,
            "target": {"name": _printable(target["name"]), "path": target["path"]} if target else None,
            "similar": [dict(r, name=_printable(r["name"]), preview=_printable(r["preview"])) for r in results],
        },
        indent=2,
    )


def _pair_lines(p, vault):
    return [
        f"  {p['score']:.4f}  {_printable(p['a'])} <-> {_printable(p['b'])}  [titles {p['title']:.2f}]",
        f"          {_printable(os.path.relpath(p['a_path'], vault))}",
        f"          {_printable(os.path.relpath(p['b_path'], vault))}",
    ]


def format_duplicates_text(found, total, vault, embed_min, title_min):
    duplicates, possible = found["duplicates"], found["possible"]
    head = (
        f"Scanned {total} notes in {vault} "
        f"({found['duplicate_total']} duplicate pair(s), {found['possible_total']} possible; "
        f"cosine >= {embed_min:.2f}, titles >= {title_min:.2f} to call it a duplicate)"
    )
    if not duplicates and not possible:
        return head
    lines = [head]
    for heading, rows, found_total in (
        ("Duplicates", duplicates, found["duplicate_total"]),
        ("Possibly the same idea", possible, found["possible_total"]),
    ):
        if not rows:
            continue
        count = f"{len(rows)} of {found_total}" if len(rows) < found_total else str(len(rows))
        lines.append("")
        lines.append(f"{heading} ({count})")
        for p in rows:
            lines += _pair_lines(p, vault)
    return "\n".join(lines)


def format_duplicates_json(
    pairs, total, vault, model, embed_min, title_min, error=None, possible_total=None, duplicate_total=None
):
    return json.dumps(
        {
            "vault": vault,
            "model": model,
            "available": error is None,
            "error": error,
            "scanned": total,
            "embed_min": embed_min,
            "title_min": title_min,
            # How many candidates the limit hid, so a picker can say "N of M"
            # rather than implying the band it shows is the whole band.
            "possible_total": possible_total,
            "duplicate_total": duplicate_total,
            "pairs": [dict(p, a=_printable(p["a"]), b=_printable(p["b"])) for p in pairs],
        },
        indent=2,
    )
