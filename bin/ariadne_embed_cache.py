"""On-disk embedding cache and vector helpers for ariadne-similar.

A note is embedded in chunks, so every entry here is `(path, hash) -> [vector,
...]`: the note's centroid first, then its chunks. A note short enough not to
be split stores one vector, which is both. Read entries through `note_vector()`
and `chunk_vectors()` rather than by index.
Vectors are L2-normalised on the way in, so a similarity query is a plain dot
product. The cache holds no note text, but note *paths* are titles in this vault,
so it is written 0600 inside a 0700 directory and should be treated as private.
"""

import array
import hashlib
import json
import math
import os
import sys
import tempfile

MAX_DIMS = 8192
# A per-note vector count this large means a corrupt or hostile index.json, not
# a note. Allocation is already gated by the file-size check below, so this buys
# no memory safety -- it rejects counts that could never have been written.
# save_cache checks the same predicate before writing, because an entry this
# side would reject invalidates the whole cache rather than one note.
MAX_VECTORS = 4096
BATCH_SIZE = 32
FLOAT_BYTES = 4


class EmbedUnavailable(Exception):
    """No usable embedding server, model, or index — callers degrade to an empty result."""


def normalize(values):
    vec = array.array("f", values)
    # A NaN survives normalisation -- sqrt(nan) is not 0, so the zero-norm guard
    # below does not fire -- and would be written to the cache, where it poisons
    # every later score until --rebuild. Refuse it at the door instead.
    if not all(math.isfinite(v) for v in vec):
        raise EmbedUnavailable("malformed embedding: contains NaN or infinity")
    norm = math.sqrt(math.sumprod(vec, vec))
    if norm == 0:
        return vec
    return array.array("f", [v / norm for v in vec])


def centroid(vectors):
    """A note's chunks summarised as one vector: their mean, renormalised.

    For the single-chunk case this is the vector itself, untouched -- there is
    nothing to average, and renormalising a unit vector would only add
    floating-point noise.
    """
    if len(vectors) == 1:
        return vectors[0]
    total = [0.0] * len(vectors[0])
    for vec in vectors:
        for i, value in enumerate(vec):
            total[i] += value
    return normalize(total)


def note_entry(chunks):
    """The cache entry for one note: its centroid, then the chunks it averages.

    The centroid is stored rather than derived because every comparison against
    a note uses it, and recomputing them all costs ~0.5 s per invocation on a
    vault of a few thousand notes -- more than a whole query. A single-chunk
    note *is* its own centroid, so it stores one vector serving both roles.
    """
    return list(chunks) if len(chunks) == 1 else [centroid(chunks), *chunks]


def note_vector(entry):
    """The note as one vector: the centroid of everything it says."""
    return entry[0]


def dims_of(cached):
    """Vector width of a loaded cache, from any entry. Zero when there is nothing cached."""
    for entry in cached.values():
        return len(note_vector(entry))
    return 0


def chunk_vectors(entry):
    """The note's own chunks, without the centroid that leads the entry."""
    return entry[1:] if len(entry) > 1 else entry


def best_chunk_match(query_chunks, doc_vector):
    """Score a note against a query's chunks: whichever chunk matches it best.

    Deliberately asymmetric -- chunks on the query side, one centroid on the
    document side. Taking the max on *both* sides is ColBERT's MaxSim, and it
    was measured worse here: a max over k samples rises with k, so a note that
    splits into 59 chunks outscores a one-chunk note against everything. On a
    326-note public vault with the author's own wikilinks as ground truth, that
    background level was 0.295 for one-chunk notes against 0.379 for notes of
    four chunks or more, and MRR fell from 0.206 to 0.181. Scoring documents by
    their centroid removes the bias (MRR 0.225) while keeping the query side
    free to match on any one of its sections, which is worth another 0.208 ->
    0.225. See doc/plans/PLAN-0008-chunked-embedding-index.md.
    """
    return max(math.sumprod(chunk, doc_vector) for chunk in query_chunks)


def cache_dir(vault):
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "ariadne-similar", hashlib.sha256(vault.encode("utf-8")).hexdigest()[:16])


def _whole_number(value, limit):
    """A JSON integer usable as a size. `True` is an int in Python and is not one here."""
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= limit


def _counts(entries):
    """Per-note vector counts, or None if any entry is unusable.

    The counts are what say where one note's vectors end and the next note's
    begin, so one bad entry invalidates the whole file rather than shifting
    every later note onto another note's vectors. A cache written before
    chunking carries no counts and lands here.
    """
    if not isinstance(entries, list):
        return None
    counts = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        if not isinstance(entry.get("path"), str) or not isinstance(entry.get("hash"), str):
            return None
        if not _whole_number(entry.get("count"), MAX_VECTORS):
            return None
        counts.append(entry["count"])
    return counts


def load_cache(cdir, model):
    """Return ((path, hash) -> [vector, ...], dims). Any inconsistency yields an empty cache."""
    try:
        with open(os.path.join(cdir, "index.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return {}, 0
    if not isinstance(meta, dict) or meta.get("model") != model:
        return {}, 0

    dims = meta.get("dims")
    entries = meta.get("notes")
    name = meta.get("vectors")
    if not _whole_number(dims, MAX_DIMS):
        return {}, 0
    # index.json names the vector file it was written with, so a crash or a
    # concurrent run can never pair one run's index with another run's vectors.
    if not isinstance(name, str) or not name or os.path.basename(name) != name:
        return {}, 0
    counts = _counts(entries)
    if counts is None:
        return {}, 0

    path = os.path.join(cdir, name)
    total = sum(counts)
    expected = total * dims * FLOAT_BYTES
    vectors = array.array("f")
    try:
        if os.path.getsize(path) != expected:
            return {}, 0
        with open(path, "rb") as f:
            vectors.fromfile(f, total * dims)
    except (OSError, EOFError, ValueError, MemoryError):
        return {}, 0
    if sys.byteorder != "little":
        vectors.byteswap()

    cached = {}
    at = 0
    for entry, count in zip(entries, counts):
        cached[(entry["path"], entry["hash"])] = [
            vectors[(at + i) * dims : (at + i + 1) * dims] for i in range(count)
        ]
        at += count
    return cached, dims


def _write_private(cdir, prefix, write):
    """mkstemp + chmod 0600: no symlink race on a predictable name, and the vectors
    are derived from private notes, so they must not land world-readable."""
    fd, tmp = tempfile.mkstemp(dir=cdir, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            write(f)
        os.chmod(tmp, 0o600)
    except BaseException:
        os.unlink(tmp)
        raise
    return tmp


def _is_vector_file(name):
    # "vectors.f32" is the pre-generation layout: still pruned, since a cache written
    # by an older version is world-readable and holds embeddings of private notes.
    return name == "vectors.f32" or (name.startswith("vectors-") and name.endswith(".f32"))


def _prune_vectors(cdir, keep):
    for name in os.listdir(cdir):
        if _is_vector_file(name) and name != keep:
            try:
                os.remove(os.path.join(cdir, name))
            except OSError:
                pass


def save_cache(cdir, model, dims, notes, cached):
    """Vectors first under a fresh generation name, then index.json as the commit point."""
    counts = [len(cached[(n["path"], n["hash"])]) for n in notes]
    # Exactly load_cache's predicate, because load_cache drops the *whole* cache
    # on a count it will not accept -- writing one would mean re-embedding and
    # re-uploading the entire vault on every run, for ever, with no diagnostic.
    # ariadne_note_text.MAX_CHUNKS is what keeps this unreachable from above.
    for note, count in zip(notes, counts):
        if not _whole_number(count, MAX_VECTORS):
            raise EmbedUnavailable(
                f"{note['path']} has {count} vectors, which the cache cannot store "
                f"(expected 1 to {MAX_VECTORS})"
            )
    os.makedirs(cdir, mode=0o700, exist_ok=True)
    os.chmod(cdir, 0o700)

    def write_vectors(f):
        for note in notes:
            for vec in cached[(note["path"], note["hash"])]:
                if sys.byteorder != "little":
                    vec = array.array("f", vec)
                    vec.byteswap()
                vec.tofile(f)

    name = f"vectors-{os.urandom(8).hex()}.f32"
    os.replace(_write_private(cdir, "vectors.", write_vectors), os.path.join(cdir, name))

    meta = {
        "model": model,
        "dims": dims,
        "vectors": name,
        # "count", not "vectors": the top-level "vectors" above is a filename.
        "notes": [{"path": n["path"], "hash": n["hash"], "count": c} for n, c in zip(notes, counts)],
    }
    payload = json.dumps(meta).encode("utf-8")
    os.replace(_write_private(cdir, "index.", lambda f: f.write(payload)), os.path.join(cdir, "index.json"))
    _prune_vectors(cdir, name)


def refresh(notes, cached, dims, embedder, batch_size=BATCH_SIZE, progress=False):
    """Embed every chunk of the notes absent from the cache, mutating `cached`.

    Returns (dims, notes embedded). Batches run over chunks so that a note with
    more sections than `batch_size` still goes out in whole batches, but the
    count and the progress line stay in *notes* -- that is the unit the caller
    announced, and the unit --max-refresh guards.

    On failure `cached` keeps every note finished so far, so a caller can persist
    partial progress rather than discard a long run. A note enters the cache only
    once all of its chunks are back, so a failure mid-note never leaves half of it
    behind for a later run to trust.
    """
    missing = [n for n in notes if (n["path"], n["hash"]) not in cached]
    pending = [(note, text) for note in missing for text in note["chunks"]]
    partial = {}
    done = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        vectors = embedder([text for _, text in batch])
        if len(vectors) != len(batch):
            raise EmbedUnavailable(f"expected {len(batch)} embeddings, got {len(vectors)}")
        for (note, _), vec in zip(batch, vectors):
            if dims == 0:
                dims = len(vec)
            elif len(vec) != dims:
                raise EmbedUnavailable(
                    f"embedding size changed ({len(vec)} vs {dims}) — re-run with --rebuild"
                )
            key = (note["path"], note["hash"])
            chunks = partial.setdefault(key, [])
            chunks.append(vec)
            if len(chunks) == len(note["chunks"]):
                cached[key] = note_entry(partial.pop(key))
                done += 1
        if progress:
            print(f"  embedded {done}/{len(missing)}", file=sys.stderr)
    return dims, len(missing)
