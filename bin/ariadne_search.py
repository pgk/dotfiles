"""Semantic search: rank notes against a free-text phrase, grouped by cluster.

Ranking alone would let one tight cluster's near-duplicate notes bury a good
match sitting in a different part of the vault; grouping surfaces the spread
of relevant clusters instead of just the single highest-scoring hit. Knows
nothing about clustering, embedding, or the cache -- same reason
ariadne_duplicates.py only takes (notes, cached): testable with hand-built
inputs, no need to mock the pipeline around it.
"""

import math

import ariadne_embed_cache
import ariadne_note_text
import ariadne_similar_report

DEFAULT_PER_CLUSTER = 3
# EmbeddingGemma is trained asymmetrically: a retrieval query is meant to arrive
# under this prefix, documents under their own. Prefixing the query alone is
# worth +1.5% MRR (24 queries better, 9 worse) on a 495-note public corpus, and
# costs no re-index -- the query is embedded fresh per call and never cached.
QUERY_PREFIX = "task: search result | query: "


def query_text(phrase):
    """The search phrase as the model expects a query, not a document."""
    return f"{QUERY_PREFIX}{phrase}"


def query_texts(phrase, *, lifted, name=None):
    """The strings to embed for `phrase`, in the shape the model wants them.

    `lifted` says the text was taken out of a note (`--search --from`) rather
    than typed, and the two differ in both ways that matter here.

    The prefix: QUERY_PREFIX is worth +1.5% MRR on the title-shaped queries it
    was measured on (PLAN-0008), and that gain does not survive the change of
    shape. Over 522 source notes in four public corpora, two seeds, a lifted
    passage gains nothing from it: pooled -0.6% and -0.8%, both intervals
    spanning zero. The corpora disagree rather than agreeing on zero -- the
    326-note wiki loses ~1.5% under the prefix both times, a 23-note vault gains
    ~9% -- so this is the weaker of the calls here, taken on the grounds that a
    prefix whose only measured benefit was for a different query shape should
    not be applied on faith. bin/CLAUDE.md carries the numbers.

    The length: a typed phrase is one vector, but a selection can run past what
    the model reads, so it is chunked and scored on its best chunk -- the same
    asymmetry `--similar` already uses for a multi-section target note. `name`
    is the note it was lifted from, which `passage_chunks` prefixes when it says
    anything; a typed phrase has no such note and never gets one.
    """
    if lifted:
        return ariadne_note_text.passage_chunks(phrase, name)
    return [query_text(phrase)]


def rank_by_cluster(query_vec, notes, cached, clusters, *, per_cluster, limit):
    """Every embedded note scored against `query_vec`, grouped by `clusters[path]`.

    Clusters are ordered by their own best-scoring hit; within a cluster only the
    top `per_cluster` hits survive, and only the top `limit` clusters are kept --
    otherwise a large vault returns as many groups as it has clusters.
    """
    by_cluster = {}
    for note in notes:
        entry = cached.get((note["path"], note["hash"]))
        if not entry:
            continue
        # A typed phrase has no sections of its own, so this is one vector against
        # each note as a whole -- see ariadne_embed_cache.best_chunk_match.
        score = round(math.sumprod(query_vec, ariadne_embed_cache.note_vector(entry)), 4)
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
        "--from",
        dest="from_note",
        metavar="NOTE",
        default=None,
        help="With --search, the note the phrase was lifted out of. That note is "
        "left out of its own results, and supplies the cluster and the existing "
        "links, so the ranking is crossing-vs-within as for a whole-note query "
        "rather than grouped by cluster",
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
    if args.from_note is not None and args.search is None:
        raise ValueError("--from names where a --search phrase came from, so it needs --search")
    if args.from_note is not None and not args.from_note.strip():
        raise ValueError("--from note cannot be blank")


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
