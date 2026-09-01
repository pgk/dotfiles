"""On-disk embedding cache and vector helpers for ariadne-similar.

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


def cache_dir(vault):
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "ariadne-similar", hashlib.sha256(vault.encode("utf-8")).hexdigest()[:16])


def load_cache(cdir, model):
    """Return ((path, hash) -> vector, dims). Any inconsistency yields an empty cache."""
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
    if not isinstance(dims, int) or not 0 < dims <= MAX_DIMS or not isinstance(entries, list):
        return {}, 0
    # index.json names the vector file it was written with, so a crash or a
    # concurrent run can never pair one run's index with another run's vectors.
    if not isinstance(name, str) or not name or os.path.basename(name) != name:
        return {}, 0

    path = os.path.join(cdir, name)
    expected = len(entries) * dims * FLOAT_BYTES
    vectors = array.array("f")
    try:
        if os.path.getsize(path) != expected:
            return {}, 0
        with open(path, "rb") as f:
            vectors.fromfile(f, len(entries) * dims)
    except (OSError, EOFError, ValueError, MemoryError):
        return {}, 0
    if sys.byteorder != "little":
        vectors.byteswap()

    cached = {}
    for i, entry in enumerate(entries):
        if isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("hash"), str):
            cached[(entry["path"], entry["hash"])] = vectors[i * dims : (i + 1) * dims]
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
    os.makedirs(cdir, mode=0o700, exist_ok=True)
    os.chmod(cdir, 0o700)

    def write_vectors(f):
        for note in notes:
            vec = cached[(note["path"], note["hash"])]
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
        "notes": [{"path": n["path"], "hash": n["hash"]} for n in notes],
    }
    payload = json.dumps(meta).encode("utf-8")
    os.replace(_write_private(cdir, "index.", lambda f: f.write(payload)), os.path.join(cdir, "index.json"))
    _prune_vectors(cdir, name)


def refresh(notes, cached, dims, embedder, batch_size=BATCH_SIZE, progress=False):
    """Embed only notes absent from the cache, mutating `cached`. Returns (dims, count).

    On failure `cached` keeps every vector embedded so far, so a caller can persist
    partial progress rather than discard a long run.
    """
    missing = [n for n in notes if (n["path"], n["hash"]) not in cached]
    for start in range(0, len(missing), batch_size):
        chunk = missing[start : start + batch_size]
        vectors = embedder([n["text"] for n in chunk])
        if len(vectors) != len(chunk):
            raise EmbedUnavailable(f"expected {len(chunk)} embeddings, got {len(vectors)}")
        for note, vec in zip(chunk, vectors):
            if dims == 0:
                dims = len(vec)
            elif len(vec) != dims:
                raise EmbedUnavailable(
                    f"embedding size changed ({len(vec)} vs {dims}) — re-run with --rebuild"
                )
            cached[(note["path"], note["hash"])] = vec
        if progress:
            print(f"  embedded {min(start + batch_size, len(missing))}/{len(missing)}", file=sys.stderr)
    return dims, len(missing)
