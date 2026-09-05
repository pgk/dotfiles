"""Ranking a vault's notes against a query, and the bridge-first ordering.

Split out of `ariadne-similar` when adding `--from` pushed that script past the
400-line limit -- the same reason `ariadne_note_text.py` came out of it earlier.
Knows nothing about argparse, the cache files or the report format: it takes
vectors and note dicts and returns ranked rows, so it is testable with
hand-built inputs.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common
import ariadne_embed_cache

EmbedUnavailable = ariadne_embed_cache.EmbedUnavailable
_printable = ariadne_common.printable


def linked_paths(target, notes, name_index):
    """Paths linked to the target in either direction."""
    linked = set()
    for link in target["links"]:
        path = ariadne_common.resolve_link(link, name_index)
        if path:
            linked.add(path)
    for note in notes:
        if note["path"] == target["path"]:
            continue
        for link in note["links"]:
            if ariadne_common.resolve_link(link, name_index) == target["path"]:
                linked.add(note["path"])
                break
    return linked


def _bridged(results, limit):
    """Cross-cluster pairs first.

    A link into a neighbourhood the target is already part of adds little, while
    one that bridges clusters is structurally novel. A hard partition rather than
    a weighted blend, because a weight would be a number tuned against a vault
    that is never measured — but the limit applies to each side separately, or
    the far larger cross-cluster pool would bury the within-cluster hits entirely
    and there would be nothing to compare against.
    """
    crossing = [r for r in results if r["crosses"]]
    within = [r for r in results if not r["crosses"]]
    return crossing[:limit] + within[:limit]


def rank_against(query_chunks, origin, notes, cached, name_index, limit, include_linked, *, clusters=None, bridge_first=True):
    """`notes` ranked against `query_chunks`, seen from `origin`.

    `origin` is the note the query came from: the note itself for a whole-note
    query, the note a passage was lifted out of under `--search --from`. It
    supplies everything the ranking knows beyond the vectors -- which note to
    leave out of its own results, which notes are already linked, and which
    cluster counts as "within" -- none of which the query text can answer.

    The query gets to match on any one of its chunks; every candidate is scored
    as a whole note. See ariadne_embed_cache.best_chunk_match for why the
    asymmetry is deliberate.
    """
    # Always computed: under --all it still labels each row, it just stops filtering.
    linked = linked_paths(origin, notes, name_index)
    # No cluster data means no bridging signal, so every pair scores alike and
    # ranking falls back to similarity alone.
    clusters = clusters or {}
    origin_cluster = clusters.get(origin["path"])
    results = []
    for note in notes:
        if note["path"] == origin["path"]:
            continue
        if note["path"] in linked and not include_linked:
            continue
        entry = cached.get((note["path"], note["hash"]))
        if not entry:
            continue
        cluster = clusters.get(note["path"])
        score = ariadne_embed_cache.best_chunk_match(
            query_chunks, ariadne_embed_cache.note_vector(entry)
        )
        results.append(
            {
                "name": note["name"],
                "path": note["path"],
                "score": round(score, 4),
                "linked": note["path"] in linked,
                "crosses": cluster != origin_cluster,
                "cluster": cluster,
                "preview": note["preview"],
            }
        )
    results.sort(key=lambda r: (-r["score"], r["name"].lower()))
    return _bridged(results, limit) if bridge_first else results[:limit]


def find_similar(target, notes, cached, name_index, limit, include_linked, *, clusters=None, bridge_first=True):
    """A whole note as the query: its own stored chunk vectors, ranked from itself."""
    target_entry = cached.get((target["path"], target["hash"]))
    if not target_entry:
        raise EmbedUnavailable(f"no embedding for target note: {_printable(target['name'])}")
    return rank_against(
        ariadne_embed_cache.chunk_vectors(target_entry), target, notes, cached, name_index,
        limit, include_linked, clusters=clusters, bridge_first=bridge_first,
    )
