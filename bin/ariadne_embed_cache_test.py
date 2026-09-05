#!/usr/bin/env python3

"""Tests for bin/ariadne_embed_cache, run against synthetic data only (never ~/notes)."""

import json
import math
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_embed_cache


def vector(*values):
    return ariadne_embed_cache.normalize(list(values))


def make_notes(count=3, dims=4, chunks=1):
    notes = [
        {"name": f"n{i}", "path": f"/v/n{i}.md", "hash": f"h{i}", "chunks": [f"n{i}-{c}" for c in range(chunks)]}
        for i in range(count)
    ]
    cached = {
        (n["path"], n["hash"]): ariadne_embed_cache.note_entry(
            [vector(*([float(i + c + 1)] * (dims - 1)), 1.0) for c in range(chunks)]
        )
        for i, n in enumerate(notes)
    }
    return notes, cached


def vector_files(cdir):
    return sorted(p.name for p in Path(cdir).glob("vectors-*.f32"))


def counting_embedder(dims=8, calls=None, fail_after=None):
    """Deterministic vectors; `fail_after` makes it raise once that many texts are seen."""
    seen = []

    def embed(texts):
        if fail_after is not None and len(seen) + len(texts) > fail_after:
            raise ariadne_embed_cache.EmbedUnavailable("stub failure")
        vectors = []
        for text in texts:
            seen.append(text)
            if calls is not None:
                calls.append(text)
            values = [float(len(text))] * dims
            values[0] += 1.0
            vectors.append(ariadne_embed_cache.normalize(values))
        return vectors

    return embed


class NormalizeTests(unittest.TestCase):
    def test_unit_length(self):
        self.assertAlmostEqual(sum(v * v for v in vector(3.0, 4.0)), 1.0, places=5)

    def test_zero_vector_is_left_alone(self):
        self.assertEqual(list(vector(0.0, 0.0)), [0.0, 0.0])


class BestChunkMatchTests(unittest.TestCase):
    """Chunks on the query side, one vector on the document side."""

    def test_the_best_matching_query_chunk_wins(self):
        chunks = [vector(1.0, 0.0), vector(0.0, 1.0)]
        self.assertAlmostEqual(
            ariadne_embed_cache.best_chunk_match(chunks, vector(0.0, 1.0)), 1.0, places=5
        )

    def test_a_single_chunk_query_is_the_plain_dot_product(self):
        self.assertAlmostEqual(
            ariadne_embed_cache.best_chunk_match([vector(1.0, 0.0)], vector(1.0, 1.0)),
            math.sqrt(0.5),
            places=5,
        )


class NoteEntryTests(unittest.TestCase):
    """An entry is the centroid, then the chunks -- and one vector when there is one chunk."""

    def test_a_single_chunk_note_stores_exactly_one_vector(self):
        vec = vector(0.3, 0.9, 0.1)
        entry = ariadne_embed_cache.note_entry([vec])
        self.assertEqual(len(entry), 1)
        self.assertIs(ariadne_embed_cache.note_vector(entry), vec)
        self.assertEqual(list(ariadne_embed_cache.chunk_vectors(entry)), [vec])

    def test_a_multi_chunk_note_leads_with_its_centroid(self):
        chunks = [vector(1.0, 0.0), vector(0.0, 1.0)]
        entry = ariadne_embed_cache.note_entry(chunks)
        self.assertEqual(len(entry), 3)
        self.assertEqual(
            list(ariadne_embed_cache.note_vector(entry)),
            list(ariadne_embed_cache.centroid(chunks)),
        )
        self.assertEqual(
            [list(v) for v in ariadne_embed_cache.chunk_vectors(entry)],
            [list(v) for v in chunks],
        )

    def test_the_stored_centroid_survives_a_round_trip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        chunks = [vector(1.0, 0.0), vector(0.0, 1.0)]
        notes = [{"path": "/v/a.md", "hash": "h", "chunks": ["a", "b"]}]
        cached = {("/v/a.md", "h"): ariadne_embed_cache.note_entry(chunks)}
        ariadne_embed_cache.save_cache(cdir, "m", 2, notes, cached)
        loaded, _ = ariadne_embed_cache.load_cache(cdir, "m")
        entry = loaded[("/v/a.md", "h")]
        self.assertEqual(
            list(ariadne_embed_cache.note_vector(entry)),
            list(ariadne_embed_cache.centroid(chunks)),
        )


class CentroidTests(unittest.TestCase):
    def test_a_single_chunk_note_keeps_its_own_vector(self):
        vec = vector(0.3, 0.9, 0.1)
        self.assertIs(ariadne_embed_cache.centroid([vec]), vec)

    def test_the_mean_is_renormalised_to_unit_length(self):
        result = ariadne_embed_cache.centroid([vector(1.0, 0.0), vector(0.0, 1.0)])
        self.assertAlmostEqual(sum(v * v for v in result), 1.0, places=5)
        self.assertAlmostEqual(result[0], result[1], places=5)

    def test_the_centroid_sits_between_its_chunks(self):
        near, far = vector(1.0, 0.0), vector(0.0, 1.0)
        result = ariadne_embed_cache.centroid([near, near, far])
        self.assertGreater(math.sumprod(result, near), math.sumprod(result, far))


class DimsOfTests(unittest.TestCase):
    def test_the_width_comes_from_any_entry(self):
        _, cached = make_notes(count=2, dims=4, chunks=3)
        self.assertEqual(ariadne_embed_cache.dims_of(cached), 4)

    def test_an_empty_cache_has_no_width(self):
        self.assertEqual(ariadne_embed_cache.dims_of({}), 0)


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cdir = os.path.join(tmp.name, "cache")

    def test_round_trip_preserves_vectors(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        loaded, dims = ariadne_embed_cache.load_cache(self.cdir, "m")
        self.assertEqual(dims, 4)
        self.assertEqual(set(loaded), set(cached))
        for key, vecs in cached.items():
            self.assertEqual([list(v) for v in loaded[key]], [list(v) for v in vecs])

    def test_round_trip_keeps_each_note_chunks_in_order(self):
        notes, cached = make_notes(count=3, chunks=4)
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        loaded, _ = ariadne_embed_cache.load_cache(self.cdir, "m")
        for key, vecs in cached.items():
            self.assertEqual([list(v) for v in loaded[key]], [list(v) for v in vecs])

    def test_notes_with_different_chunk_counts_stay_paired(self):
        """The bug the chunk counts exist to prevent: one note's vectors read as another's."""
        notes, cached = make_notes(count=3, chunks=1)
        notes[1]["chunks"] = ["a", "b", "c"]
        key = (notes[1]["path"], notes[1]["hash"])
        cached[key] = ariadne_embed_cache.note_entry(
            [vector(0.0, 0.0, 0.0, 1.0), vector(0.0, 0.0, 1.0, 0.0), vector(0.0, 1.0, 0.0, 0.0)]
        )
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        loaded, _ = ariadne_embed_cache.load_cache(self.cdir, "m")
        for k, vecs in cached.items():
            self.assertEqual([list(v) for v in loaded[k]], [list(v) for v in vecs])

    def test_a_pre_chunking_cache_invalidates_rather_than_mispairing(self):
        notes, cached = make_notes(count=3, chunks=2)
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta_path = Path(self.cdir) / "index.json"
        meta = json.loads(meta_path.read_text())
        # Exactly the old format: one entry per note, no chunk count. Reading it
        # as one vector per note would hand note 1 note 0's second chunk.
        meta["notes"] = [{"path": e["path"], "hash": e["hash"]} for e in meta["notes"]]
        meta_path.write_text(json.dumps(meta))
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_a_nonsense_chunk_count_is_rejected(self):
        notes, cached = make_notes()
        for bad in (0, -1, "2", True, None, 1.0):
            ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
            meta_path = Path(self.cdir) / "index.json"
            meta = json.loads(meta_path.read_text())
            meta["notes"][1]["count"] = bad
            meta_path.write_text(json.dumps(meta))
            self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0), f"count={bad!r}")

    def test_an_over_cap_count_is_rejected_by_the_cap_not_by_the_file_size(self):
        """Sized to match, so only MAX_VECTORS can reject it."""
        over = ariadne_embed_cache.MAX_VECTORS + 1
        os.makedirs(self.cdir, exist_ok=True)
        (Path(self.cdir) / "v.f32").write_bytes(b"\x00" * (over * 4))
        (Path(self.cdir) / "index.json").write_text(
            json.dumps({"model": "m", "dims": 1, "vectors": "v.f32",
                        "notes": [{"path": "/v/a.md", "hash": "h", "count": over}]})
        )
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_save_refuses_a_note_the_cache_could_never_load_back(self):
        """Writing it would drop the whole cache on every later read, so every run
        would re-embed and re-upload the entire vault with no diagnostic.

        Both ends of load_cache's bound, not just the top: an empty entry is
        rejected there too, and would fail exactly the same way.
        """
        over = ariadne_embed_cache.MAX_VECTORS + 1
        for entry in ([vector(1.0, 0.0)] * over, []):
            notes = [{"path": "/v/a.md", "hash": "h", "chunks": ["c"] * len(entry)}]
            with self.assertRaises(ariadne_embed_cache.EmbedUnavailable) as caught:
                ariadne_embed_cache.save_cache(self.cdir, "m", 2, notes, {("/v/a.md", "h"): entry})
            self.assertIn("/v/a.md", str(caught.exception))
            self.assertFalse((Path(self.cdir) / "index.json").exists())

    def test_a_boolean_dims_is_not_a_width(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta_path = Path(self.cdir) / "index.json"
        meta = json.loads(meta_path.read_text())
        meta["dims"] = True
        meta_path.write_text(json.dumps(meta))
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_different_model_invalidates_cache(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "other"), ({}, 0))

    def test_missing_cache_is_empty_not_an_error(self):
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_corrupt_index_json_is_empty_not_an_error(self):
        os.makedirs(self.cdir)
        (Path(self.cdir) / "index.json").write_text("{not json")
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_save_prunes_entries_for_removed_notes(self):
        notes, cached = make_notes(count=3)
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes[:2], cached)
        loaded, _ = ariadne_embed_cache.load_cache(self.cdir, "m")
        self.assertEqual(len(loaded), 2)
        self.assertNotIn(("/v/n2.md", "h2"), loaded)

    def test_index_json_holds_only_paths_and_hashes_no_note_body(self):
        notes = [{"name": "n0", "path": "/v/n0.md", "hash": "h0", "chunks": ["SECRET BODY TEXT"]}]
        cached = {("/v/n0.md", "h0"): ariadne_embed_cache.note_entry([vector(1.0, 0.0, 0.0, 0.0)])}
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        raw = (Path(self.cdir) / "index.json").read_text()
        self.assertNotIn("SECRET BODY TEXT", raw)
        meta = json.loads(raw)
        # Paths are stored, and in this vault a path *is* the note title — hence 0600.
        # The vector count is a count, not text.
        self.assertEqual(sorted(meta["notes"][0]), ["count", "hash", "path"])


class PairingTests(unittest.TestCase):
    """index.json must never be readable against another run's vector file."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cdir = os.path.join(tmp.name, "cache")

    def test_index_names_its_own_vector_file(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta = json.loads((Path(self.cdir) / "index.json").read_text())
        self.assertEqual(vector_files(self.cdir), [meta["vectors"]])

    def test_each_save_uses_a_fresh_generation_and_prunes_the_old_one(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        first = json.loads((Path(self.cdir) / "index.json").read_text())["vectors"]
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        second = json.loads((Path(self.cdir) / "index.json").read_text())["vectors"]
        self.assertNotEqual(first, second)
        self.assertEqual(vector_files(self.cdir), [second])

    def test_a_legacy_unversioned_vector_file_is_pruned(self):
        notes, cached = make_notes()
        os.makedirs(self.cdir, exist_ok=True)
        legacy = Path(self.cdir) / "vectors.f32"
        legacy.write_bytes(b"\x00" * 32)
        legacy.chmod(0o644)
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        self.assertFalse(legacy.exists())

    def test_an_orphaned_index_yields_an_empty_cache_rather_than_wrong_vectors(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        # Simulate a concurrent run having replaced the vector file this index names.
        for name in vector_files(self.cdir):
            os.remove(os.path.join(self.cdir, name))
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_size_mismatch_is_rejected_in_both_directions(self):
        notes, cached = make_notes()
        for delta in (-8, +8):
            ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
            path = Path(self.cdir) / vector_files(self.cdir)[0]
            raw = path.read_bytes()
            path.write_bytes(raw[:delta] if delta < 0 else raw + b"\x00" * delta)
            self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_a_vectors_field_with_a_path_separator_is_rejected(self):
        """The outside file is sized to match, so only the basename check can reject it —
        with `../../../etc/passwd` the size check does the work and the guard is untested."""
        outside = Path(self.cdir).parent / "secret.bin"
        outside.write_bytes(b"\x00\x00\x80\x3f" * 4)
        os.makedirs(self.cdir, exist_ok=True)
        (Path(self.cdir) / "index.json").write_text(
            json.dumps({"model": "m", "dims": 4, "vectors": "../secret.bin",
                        "notes": [{"path": "/v/a.md", "hash": "h", "count": 1}]})
        )
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_absurd_dims_are_rejected_without_allocating(self):
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta_path = Path(self.cdir) / "index.json"
        meta = json.loads(meta_path.read_text())
        meta["dims"] = 2**40
        meta_path.write_text(json.dumps(meta))
        self.assertEqual(ariadne_embed_cache.load_cache(self.cdir, "m"), ({}, 0))


class PermissionTests(unittest.TestCase):
    def test_a_cache_dir_left_world_readable_by_an_older_version_is_tightened(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        os.makedirs(cdir, mode=0o755)
        os.chmod(cdir, 0o755)
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(cdir, "m", 4, notes, cached)
        self.assertEqual(stat.S_IMODE(os.stat(cdir).st_mode), 0o700)

    def test_cache_is_not_readable_by_other_users(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(cdir, "m", 4, notes, cached)

        self.assertEqual(stat.S_IMODE(os.stat(cdir).st_mode), 0o700)
        for name in ["index.json"] + vector_files(cdir):
            mode = stat.S_IMODE(os.stat(os.path.join(cdir, name)).st_mode)
            self.assertEqual(mode, 0o600, f"{name} is {oct(mode)}")

    def test_no_temp_files_are_left_behind(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        notes, cached = make_notes()
        ariadne_embed_cache.save_cache(cdir, "m", 4, notes, cached)
        self.assertEqual([p.name for p in Path(cdir).glob("*.tmp")], [])


class RefreshTests(unittest.TestCase):
    def test_only_uncached_notes_are_embedded(self):
        notes = [{"path": f"/v/n{i}.md", "hash": f"h{i}", "chunks": [f"note {i}"]} for i in range(3)]
        cached = {("/v/n0.md", "h0"): ariadne_embed_cache.note_entry([vector(*([1.0] * 8))])}
        calls = []
        dims, embedded = ariadne_embed_cache.refresh(notes, cached, 8, counting_embedder(calls=calls))
        self.assertEqual((dims, embedded), (8, 2))
        self.assertEqual(calls, ["note 1", "note 2"])
        self.assertEqual(len(cached), 3)

    def test_nothing_to_do_when_all_cached(self):
        notes = [{"path": "/v/a.md", "hash": "h", "chunks": ["a"]}]
        cached = {("/v/a.md", "h"): ariadne_embed_cache.note_entry([vector(*([1.0] * 8))])}
        calls = []
        _, embedded = ariadne_embed_cache.refresh(notes, cached, 8, counting_embedder(calls=calls))
        self.assertEqual((embedded, calls), (0, []))

    def test_dims_are_inferred_from_the_first_batch(self):
        notes = [{"path": "/v/a.md", "hash": "h", "chunks": ["a"]}]
        dims, _ = ariadne_embed_cache.refresh(notes, {}, 0, counting_embedder(dims=16))
        self.assertEqual(dims, 16)

    def test_changed_embedding_size_points_at_the_recovery_flag(self):
        notes = [{"path": "/v/a.md", "hash": "h", "chunks": ["a"]}]
        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable) as caught:
            ariadne_embed_cache.refresh(notes, {}, 32, counting_embedder(dims=8))
        self.assertIn("--rebuild", str(caught.exception))

    def test_batching_covers_every_note(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "chunks": [f"note {i}"]} for i in range(10)]
        calls = []
        _, embedded = ariadne_embed_cache.refresh(notes, {}, 0, counting_embedder(calls=calls), batch_size=3)
        self.assertEqual((embedded, len(calls)), (10, 10))

    def test_a_short_response_is_rejected_rather_than_silently_truncating(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "chunks": [f"note {i}"]} for i in range(3)]

        def short(texts):
            return [vector(*([1.0] * 8))]

        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable):
            ariadne_embed_cache.refresh(notes, {}, 0, short)

    def test_work_done_before_a_failure_is_kept_in_the_cache(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "chunks": [f"note {i}"]} for i in range(10)]
        cached = {}
        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable):
            ariadne_embed_cache.refresh(notes, cached, 0, counting_embedder(fail_after=6), batch_size=3)
        self.assertEqual(len(cached), 6)

    def test_a_note_half_embedded_when_the_server_dies_is_not_cached(self):
        """A half-note would be stored under the note's real hash, so it is never
        re-embedded: every later score against it uses a centroid of half the note."""
        notes = [
            {"path": f"/v/n{i}.md", "hash": "h", "chunks": [f"n{i}-a", f"n{i}-b", f"n{i}-c"]}
            for i in range(4)
        ]
        cached = {}
        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable):
            ariadne_embed_cache.refresh(notes, cached, 0, counting_embedder(fail_after=5), batch_size=2)
        self.assertEqual(list(cached), [("/v/n0.md", "h")])
        self.assertEqual(len(cached[("/v/n0.md", "h")]), 4)  # centroid + 3 chunks, never a stub

    def test_a_note_spanning_several_batches_is_embedded_whole(self):
        notes = [{"path": "/v/a.md", "hash": "h", "chunks": [f"c{i}" for i in range(7)]}]
        cached = {}
        dims, embedded = ariadne_embed_cache.refresh(
            notes, cached, 0, counting_embedder(), batch_size=2
        )
        self.assertEqual(len(cached[("/v/a.md", "h")]), 8)
        self.assertEqual(embedded, 1, "the count is notes, not chunks")


class NonFiniteEmbeddingTests(unittest.TestCase):
    """A NaN vector would be cached and poison every later score until --rebuild."""

    def test_nan_is_refused(self):
        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable) as ctx:
            ariadne_embed_cache.normalize([float("nan"), 1.0])
        self.assertIn("NaN", str(ctx.exception))

    def test_infinity_is_refused(self):
        for bad in (float("inf"), float("-inf")):
            with self.assertRaises(ariadne_embed_cache.EmbedUnavailable):
                ariadne_embed_cache.normalize([bad, 1.0])

    def test_a_nan_does_not_trip_the_zero_norm_guard(self):
        # sqrt(nan) is not 0, so without the explicit check the NaN would sail
        # past `if norm == 0` and be normalised into every component.
        self.assertNotEqual(math.sqrt(float("nan")), 0)

    def test_an_all_zero_vector_is_still_allowed(self):
        self.assertEqual(list(ariadne_embed_cache.normalize([0.0, 0.0])), [0.0, 0.0])

    def test_ordinary_vectors_are_unaffected(self):
        self.assertEqual([round(v, 4) for v in ariadne_embed_cache.normalize([3.0, 4.0])], [0.6, 0.8])


if __name__ == "__main__":
    unittest.main()
