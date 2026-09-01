"""Near-duplicate detection over an embedded vault, on two signals rather than one.

Embedding similarity alone cannot tell "the same note twice" from "a
neighbouring idea"; the title is what separates them. Measured on a 37-note
corpus in the project this was salvaged from:

    |                            | embedding cosine | title similarity |
    | the one genuine duplicate  |            0.842 |            1.000 |
    | every other pair over 0.80 |      0.80 - 0.87 |         <= 0.430 |

So a pair is worth *looking* at above `EMBED_MIN` cosine, and worth *merging*
without asking above `TITLE_MIN` title similarity. Between the two is a
question for a human, and on a real vault that band is the wide part.

Both numbers are borrowed calibration, not a measurement of this vault. They
are flags on `ariadne-similar --duplicates` so they can be re-tuned here.
"""

import difflib
import heapq
import math

import ariadne_similar_report

EMBED_MIN = 0.80
TITLE_MIN = 0.85
# Duplicates are shown in full, but 'in full' still needs a ceiling: a vault of
# near-identical stubs makes this list quadratic too.
MAX_DUPLICATES = 1000


def title_similarity(a, b):
    return difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def find_duplicates(notes, cached, *, embed_min=EMBED_MIN, title_min=TITLE_MIN, limit=None):
    """Split the over-`embed_min` pairs into confirmed duplicates and the noisy band.

    Quadratic with no index structure — about forty seconds at three thousand
    notes with a 768-dim model — which is why this is its own mode and not
    something a query pays for. Notes with no cached embedding are skipped rather
    than embedded; the caller decides whether to refresh first.

    Both output lists are bounded while scanning, not afterwards: at `embed_min`
    0 every pair qualifies, and materialising all of them is gigabytes on a vault
    of a few thousand. The totals are counted in full regardless, so a caller can
    always say how much it is not showing.
    """
    embedded = []
    for note in notes:
        vec = cached.get((note["path"], note["hash"]))
        if vec is not None:
            embedded.append((note["name"], note["path"], vec))
    embedded.sort(key=lambda e: e[1])

    duplicates, duplicate_total = [], 0
    band, possible_total = [], 0
    seen = 0
    for i, (a_name, a_path, a_vec) in enumerate(embedded):
        for b_name, b_path, b_vec in embedded[i + 1 :]:
            score = math.sumprod(a_vec, b_vec)
            if score < embed_min:
                continue
            title = title_similarity(a_name, b_name)
            pair = {
                "a": a_name,
                "a_path": a_path,
                "b": b_name,
                "b_path": b_path,
                "score": round(score, 4),
                "title": round(title, 4),
                "verdict": "duplicate" if title >= title_min else "possible",
            }
            if title >= title_min:
                duplicate_total += 1
                if len(duplicates) < MAX_DUPLICATES:
                    duplicates.append(pair)
            else:
                possible_total += 1
                if limit is None:
                    band.append(pair)
                else:
                    # Min-heap on score, so the weakest candidate is the one evicted.
                    # `seen` only breaks ties; the survivors are sorted properly below.
                    seen += 1
                    heapq.heappush(band, (score, seen, pair))
                    if len(band) > limit:
                        heapq.heappop(band)

    possible = band if limit is None else [entry[2] for entry in band]
    duplicates.sort(key=_rank)
    possible.sort(key=_rank)
    return {
        "duplicates": duplicates,
        "duplicate_total": duplicate_total,
        "possible": possible,
        "possible_total": possible_total,
    }


def _rank(pair):
    return (-pair["score"], pair["a"].lower(), pair["b"].lower())



def add_arguments(parser):
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Report near-duplicate pairs across the whole vault instead of querying one note",
    )
    parser.add_argument(
        "--dup-min",
        type=float,
        default=EMBED_MIN,
        metavar="COSINE",
        help=f"With --duplicates, cosine bar for a pair to be worth looking at (default: {EMBED_MIN})",
    )
    parser.add_argument(
        "--dup-title-min",
        type=float,
        default=TITLE_MIN,
        metavar="RATIO",
        help=f"With --duplicates, title similarity at which a candidate is a duplicate rather than a question (default: {TITLE_MIN})",
    )


def check_arguments(args):
    for name, value in (("--dup-min", args.dup_min), ("--dup-title-min", args.dup_title_min)):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")


def run(args, vault, notes, cached):
    found = find_duplicates(
        notes, cached, embed_min=args.dup_min, title_min=args.dup_title_min, limit=args.limit
    )
    if args.json:
        print(
            ariadne_similar_report.format_duplicates_json(
                found["duplicates"] + found["possible"], len(notes), vault, args.model,
                args.dup_min, args.dup_title_min,
                possible_total=found["possible_total"], duplicate_total=found["duplicate_total"],
            )
        )
    else:
        print(
            ariadne_similar_report.format_duplicates_text(
                found, len(notes), vault, args.dup_min, args.dup_title_min
            )
        )
    return 0


def report_unavailable(args, vault, total, error):
    print(
        ariadne_similar_report.format_duplicates_json(
            [], total, vault, args.model, args.dup_min, args.dup_title_min,
            error=error, possible_total=0, duplicate_total=0,
        )
    )
