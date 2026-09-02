"""Semantic search: rank notes against a free-text phrase, grouped by cluster.

Ranking alone would let one tight cluster's near-duplicate notes bury a good
match sitting in a different part of the vault; grouping surfaces the spread
of relevant clusters instead of just the single highest-scoring hit. Knows
nothing about clustering, embedding, or the cache -- same reason
ariadne_duplicates.py only takes (notes, cached): testable with hand-built
inputs, no need to mock the pipeline around it.
"""

import math

import ariadne_similar_report

DEFAULT_PER_CLUSTER = 3


def rank_by_cluster(query_vec, notes, cached, clusters, *, per_cluster, limit):
    """Every embedded note scored against `query_vec`, grouped by `clusters[path]`.

    Clusters are ordered by their own best-scoring hit; within a cluster only the
    top `per_cluster` hits survive, and only the top `limit` clusters are kept --
    otherwise a large vault returns as many groups as it has clusters.
    """
    by_cluster = {}
    for note in notes:
        vec = cached.get((note["path"], note["hash"]))
        if vec is None:
            continue
        score = round(math.sumprod(query_vec, vec), 4)
        cluster = clusters.get(note["path"])
        by_cluster.setdefault(cluster, []).append(
            {"name": note["name"], "path": note["path"], "score": score, "cluster": cluster}
        )

    groups = []
    for cluster, hits in by_cluster.items():
        hits.sort(key=lambda r: (-r["score"], r["name"].lower()))
        groups.append({"cluster": cluster, "cluster_total": len(hits), "hits": hits[:per_cluster]})
    groups.sort(key=lambda g: (-g["hits"][0]["score"], g["hits"][0]["name"].lower()))
    return groups[:limit]


def add_arguments(parser):
    parser.add_argument(
        "--search",
        metavar="PHRASE",
        default=None,
        help="Semantic search: rank notes by similarity to PHRASE, grouped by "
        "cluster, instead of querying one note",
    )
    parser.add_argument(
        "--per-cluster",
        type=int,
        default=DEFAULT_PER_CLUSTER,
        help=f"With --search, hits shown per cluster (default: {DEFAULT_PER_CLUSTER})",
    )


def check_arguments(args):
    if args.per_cluster < 1:
        raise ValueError(f"--per-cluster must be at least 1, got {args.per_cluster}")
    if args.search is not None and not args.search.strip():
        raise ValueError("--search phrase cannot be blank")


def run(args, vault, notes, cached, clusters, shape, query_vec):
    groups = rank_by_cluster(
        query_vec, notes, cached, clusters, per_cluster=args.per_cluster, limit=args.limit
    )
    if args.json:
        print(
            ariadne_similar_report.format_search_json(
                args.search, groups, len(notes), vault, args.model, shape=shape
            )
        )
    else:
        print(
            ariadne_similar_report.format_search_text(args.search, groups, len(notes), vault, shape=shape)
        )
    return 0


def report_unavailable(args, vault, total, error):
    print(ariadne_similar_report.format_search_json(args.search, [], total, vault, args.model, error=error))
