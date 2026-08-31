#!/usr/bin/env python3

"""Tests for bin/notes_embed_cache, run against synthetic data only (never ~/notes)."""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_embed_cache


def vector(*values):
    return notes_embed_cache.normalize(list(values))


def make_notes(count=3, dims=4):
    notes = [{"name": f"n{i}", "path": f"/v/n{i}.md", "hash": f"h{i}", "text": f"n{i}"} for i in range(count)]
    cached = {(n["path"], n["hash"]): vector(*([float(i + 1)] * dims)) for i, n in enumerate(notes)}
    return notes, cached


def vector_files(cdir):
    return sorted(p.name for p in Path(cdir).glob("vectors-*.f32"))


def counting_embedder(dims=8, calls=None, fail_after=None):
    """Deterministic vectors; `fail_after` makes it raise once that many texts are seen."""
    seen = []

    def embed(texts):
        if fail_after is not None and len(seen) + len(texts) > fail_after:
            raise notes_embed_cache.EmbedUnavailable("stub failure")
        vectors = []
        for text in texts:
            seen.append(text)
            if calls is not None:
                calls.append(text)
            values = [float(len(text))] * dims
            values[0] += 1.0
            vectors.append(notes_embed_cache.normalize(values))
        return vectors

    return embed


class NormalizeTests(unittest.TestCase):
    def test_unit_length(self):
        self.assertAlmostEqual(sum(v * v for v in vector(3.0, 4.0)), 1.0, places=5)

    def test_zero_vector_is_left_alone(self):
        self.assertEqual(list(vector(0.0, 0.0)), [0.0, 0.0])


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cdir = os.path.join(tmp.name, "cache")

    def test_round_trip_preserves_vectors(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        loaded, dims = notes_embed_cache.load_cache(self.cdir, "m")
        self.assertEqual(dims, 4)
        self.assertEqual(set(loaded), set(cached))
        for key, vec in cached.items():
            self.assertEqual(list(loaded[key]), list(vec))

    def test_different_model_invalidates_cache(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "other"), ({}, 0))

    def test_missing_cache_is_empty_not_an_error(self):
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_corrupt_index_json_is_empty_not_an_error(self):
        os.makedirs(self.cdir)
        (Path(self.cdir) / "index.json").write_text("{not json")
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_save_prunes_entries_for_removed_notes(self):
        notes, cached = make_notes(count=3)
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes[:2], cached)
        loaded, _ = notes_embed_cache.load_cache(self.cdir, "m")
        self.assertEqual(len(loaded), 2)
        self.assertNotIn(("/v/n2.md", "h2"), loaded)

    def test_index_json_holds_only_paths_and_hashes_no_note_body(self):
        notes = [{"name": "n0", "path": "/v/n0.md", "hash": "h0", "text": "SECRET BODY TEXT"}]
        cached = {("/v/n0.md", "h0"): vector(1.0, 0.0, 0.0, 0.0)}
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        raw = (Path(self.cdir) / "index.json").read_text()
        self.assertNotIn("SECRET BODY TEXT", raw)
        meta = json.loads(raw)
        # Paths are stored, and in this vault a path *is* the note title — hence 0600.
        self.assertEqual(sorted(meta["notes"][0]), ["hash", "path"])


class PairingTests(unittest.TestCase):
    """index.json must never be readable against another run's vector file."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cdir = os.path.join(tmp.name, "cache")

    def test_index_names_its_own_vector_file(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta = json.loads((Path(self.cdir) / "index.json").read_text())
        self.assertEqual(vector_files(self.cdir), [meta["vectors"]])

    def test_each_save_uses_a_fresh_generation_and_prunes_the_old_one(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        first = json.loads((Path(self.cdir) / "index.json").read_text())["vectors"]
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        second = json.loads((Path(self.cdir) / "index.json").read_text())["vectors"]
        self.assertNotEqual(first, second)
        self.assertEqual(vector_files(self.cdir), [second])

    def test_a_legacy_unversioned_vector_file_is_pruned(self):
        notes, cached = make_notes()
        os.makedirs(self.cdir, exist_ok=True)
        legacy = Path(self.cdir) / "vectors.f32"
        legacy.write_bytes(b"\x00" * 32)
        legacy.chmod(0o644)
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        self.assertFalse(legacy.exists())

    def test_an_orphaned_index_yields_an_empty_cache_rather_than_wrong_vectors(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        # Simulate a concurrent run having replaced the vector file this index names.
        for name in vector_files(self.cdir):
            os.remove(os.path.join(self.cdir, name))
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_size_mismatch_is_rejected_in_both_directions(self):
        notes, cached = make_notes()
        for delta in (-8, +8):
            notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
            path = Path(self.cdir) / vector_files(self.cdir)[0]
            raw = path.read_bytes()
            path.write_bytes(raw[:delta] if delta < 0 else raw + b"\x00" * delta)
            self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_a_vectors_field_with_a_path_separator_is_rejected(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta_path = Path(self.cdir) / "index.json"
        meta = json.loads(meta_path.read_text())
        meta["vectors"] = "../../../etc/passwd"
        meta_path.write_text(json.dumps(meta))
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))

    def test_absurd_dims_are_rejected_without_allocating(self):
        notes, cached = make_notes()
        notes_embed_cache.save_cache(self.cdir, "m", 4, notes, cached)
        meta_path = Path(self.cdir) / "index.json"
        meta = json.loads(meta_path.read_text())
        meta["dims"] = 2**40
        meta_path.write_text(json.dumps(meta))
        self.assertEqual(notes_embed_cache.load_cache(self.cdir, "m"), ({}, 0))


class PermissionTests(unittest.TestCase):
    def test_cache_is_not_readable_by_other_users(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        notes, cached = make_notes()
        notes_embed_cache.save_cache(cdir, "m", 4, notes, cached)

        self.assertEqual(stat.S_IMODE(os.stat(cdir).st_mode), 0o700)
        for name in ["index.json"] + vector_files(cdir):
            mode = stat.S_IMODE(os.stat(os.path.join(cdir, name)).st_mode)
            self.assertEqual(mode, 0o600, f"{name} is {oct(mode)}")

    def test_no_temp_files_are_left_behind(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cdir = os.path.join(tmp.name, "cache")
        notes, cached = make_notes()
        notes_embed_cache.save_cache(cdir, "m", 4, notes, cached)
        self.assertEqual([p.name for p in Path(cdir).glob("*.tmp")], [])


class RefreshTests(unittest.TestCase):
    def test_only_uncached_notes_are_embedded(self):
        notes = [{"path": f"/v/n{i}.md", "hash": f"h{i}", "text": f"note {i}"} for i in range(3)]
        cached = {("/v/n0.md", "h0"): vector(*([1.0] * 8))}
        calls = []
        dims, embedded = notes_embed_cache.refresh(notes, cached, 8, counting_embedder(calls=calls))
        self.assertEqual((dims, embedded), (8, 2))
        self.assertEqual(calls, ["note 1", "note 2"])
        self.assertEqual(len(cached), 3)

    def test_nothing_to_do_when_all_cached(self):
        notes = [{"path": "/v/a.md", "hash": "h", "text": "a"}]
        cached = {("/v/a.md", "h"): vector(*([1.0] * 8))}
        calls = []
        _, embedded = notes_embed_cache.refresh(notes, cached, 8, counting_embedder(calls=calls))
        self.assertEqual((embedded, calls), (0, []))

    def test_dims_are_inferred_from_the_first_batch(self):
        notes = [{"path": "/v/a.md", "hash": "h", "text": "a"}]
        dims, _ = notes_embed_cache.refresh(notes, {}, 0, counting_embedder(dims=16))
        self.assertEqual(dims, 16)

    def test_changed_embedding_size_points_at_the_recovery_flag(self):
        notes = [{"path": "/v/a.md", "hash": "h", "text": "a"}]
        with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
            notes_embed_cache.refresh(notes, {}, 32, counting_embedder(dims=8))
        self.assertIn("--rebuild", str(caught.exception))

    def test_batching_covers_every_note(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "text": f"note {i}"} for i in range(10)]
        calls = []
        _, embedded = notes_embed_cache.refresh(notes, {}, 0, counting_embedder(calls=calls), batch_size=3)
        self.assertEqual((embedded, len(calls)), (10, 10))

    def test_a_short_response_is_rejected_rather_than_silently_truncating(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "text": f"note {i}"} for i in range(3)]

        def short(texts):
            return [vector(*([1.0] * 8))]

        with self.assertRaises(notes_embed_cache.EmbedUnavailable):
            notes_embed_cache.refresh(notes, {}, 0, short)

    def test_work_done_before_a_failure_is_kept_in_the_cache(self):
        notes = [{"path": f"/v/n{i}.md", "hash": "h", "text": f"note {i}"} for i in range(10)]
        cached = {}
        with self.assertRaises(notes_embed_cache.EmbedUnavailable):
            notes_embed_cache.refresh(notes, cached, 0, counting_embedder(fail_after=6), batch_size=3)
        self.assertEqual(len(cached), 6)


if __name__ == "__main__":
    unittest.main()
