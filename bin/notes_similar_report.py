"""Text and JSON rendering for notes-similar.

Split from the tool so the ranking logic and its presentation can each be read
on their own.
"""

import json
import os

import notes_cluster
import notes_common

_printable = notes_common.printable


def format_text(target, results, total, include_linked, vault, shape=None, grouped=False):
    name = _printable(target["name"])
    if not results:
        scope = "similar" if include_linked else "unlinked similar"
        return f"No {scope} notes found for '{name}' among {total} notes in {vault}."
    scope = "Similar" if include_linked else "Unlinked similar"
    lines = [f"{scope} to '{name}' ({len(results)} of {total} notes in {vault})"]
    if shape:
        lines.append(notes_cluster.describe_shape(shape))
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
