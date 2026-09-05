#!/usr/bin/env python3

"""Tests for bin/ariadne-similar, run against synthetic notes only (never ~/notes).

No test may require a live embedding server: `fake_embedder` supplies deterministic
vectors and the CLI cases point at a closed loopback port. Cache and HTTP behaviour
live in ariadne_embed_cache_test.py and ariadne_embed_client_test.py.
"""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common
import ariadne_embed_cache
import ariadne_note_text
import ariadne_similar_report
from ariadne_similar_testkit import (
    fake_embedder,
    ariadne_similar,
    write_vault,
)


class ScanVaultTests(unittest.TestCase):
    def scan(self, files, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            return ariadne_similar.scan_vault(tmp, excludes or [])

    def test_collects_name_hash_and_links_in_one_pass(self):
        notes = self.scan({"a.md": "Links to [[b]] and [[c]].", "b.md": "Body b."})
        by_name = {n["name"]: n for n in notes}
        self.assertEqual(sorted(by_name), ["a", "b"])
        self.assertEqual(by_name["a"]["links"], ["b", "c"])
        self.assertEqual(
            by_name["a"]["hash"],
            ariadne_note_text.content_hash(ariadne_note_text.note_chunks("a", "Links to [[b]] and [[c]].")),
        )
        self.assertNotEqual(by_name["a"]["hash"], by_name["b"]["hash"])

    def test_excludes_are_honoured(self):
        notes = self.scan({"a.md": "a", "skip/b.md": "b"}, excludes=["skip/*"])
        self.assertEqual([n["name"] for n in notes], ["a"])

    def test_a_note_carries_the_chunks_that_will_be_embedded(self):
        raw = "## Alpha\n" + "a" * 900 + "\n\n## Beta\n" + "b" * 900 + "\n"
        notes = self.scan({"long.md": raw, "short.md": "Body."})
        by_name = {n["name"]: n for n in notes}
        self.assertEqual(by_name["long"]["chunks"], ariadne_note_text.note_chunks("long", raw))
        self.assertEqual(by_name["short"]["chunks"], ["short\n\nBody."])

    def test_the_preview_comes_from_the_first_chunk(self):
        """A multi-chunk note, so 'first' is distinguishable from 'last'."""
        raw = "## Opening\n\nFirst real line.\n" + "a " * 500 + "\n\n## Later\n\nA different line.\n" + "b " * 500
        notes = self.scan({"a.md": raw})
        self.assertGreater(len(notes[0]["chunks"]), 1)
        self.assertEqual(notes[0]["preview"], "First real line.")


class FindSimilarTests(unittest.TestCase):
    def prepare(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_vault(tmp.name, files)
        notes = ariadne_similar.scan_vault(tmp.name, [])
        name_index = ariadne_common.build_name_index([n["path"] for n in notes])
        cached = {}
        ariadne_embed_cache.refresh(notes, cached, 0, fake_embedder())
        return tmp.name, notes, name_index, cached

    def similar(self, files, target_name, limit=10, include_linked=False):
        _, notes, name_index, cached = self.prepare(files)
        target = ariadne_similar.resolve_target(target_name, notes, name_index)
        return ariadne_similar.find_similar(target, notes, cached, name_index, limit, include_linked)

    def test_self_is_excluded(self):
        results = self.similar({"a.md": "alpha beta", "b.md": "alpha beta"}, "a")
        self.assertNotIn("a", [r["name"] for r in results])

    def test_results_are_sorted_by_descending_score(self):
        results = self.similar(
            {
                "target.md": "quantum entanglement physics",
                "close.md": "quantum entanglement physics",
                "far.md": "sourdough bread baking recipe",
            },
            "target",
        )
        self.assertEqual([r["name"] for r in results], ["close", "far"])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def setup_pair(self):
        """A target and one candidate, with the vectors of both under the test's control."""
        _, notes, name_index, cached = self.prepare({"target.md": "alpha beta", "other.md": "gamma delta"})
        by_name = {n["name"]: n for n in notes}
        target, other = by_name["target"], by_name["other"]
        keys = ((target["path"], target["hash"]), (other["path"], other["hash"]))

        def score():
            return ariadne_similar.find_similar(
                target, notes, cached, name_index, 10, False
            )[0]["score"]

        return notes, cached, keys, score

    def test_the_target_may_match_on_any_one_of_its_sections(self):
        """One section lining up is a real hit, even if the rest of the note does not."""
        _, cached, (target_key, other_key), score = self.setup_pair()
        other_vec = ariadne_embed_cache.note_vector(cached[other_key])
        unrelated = fake_embedder()(["nothing at all in common"])[0]

        cached[target_key] = ariadne_embed_cache.note_entry([unrelated, other_vec])
        self.assertEqual(score(), 1.0)
        # The same content averaged into one chunk loses the match.
        cached[target_key] = ariadne_embed_cache.note_entry(
            [ariadne_embed_cache.centroid([unrelated, other_vec])]
        )
        self.assertLess(score(), 1.0)

    def test_a_candidate_is_scored_as_a_whole_note_not_by_its_best_section(self):
        """Taking the max on both sides makes a note with many chunks a magnet."""
        _, cached, (target_key, other_key), score = self.setup_pair()
        target_vec = ariadne_embed_cache.note_vector(cached[target_key])
        unrelated = fake_embedder()(["nothing at all in common"])[0]
        chunks = [target_vec, unrelated]

        cached[other_key] = ariadne_embed_cache.note_entry(chunks)
        self.assertLess(score(), 1.0)
        self.assertAlmostEqual(
            score(),
            round(math.sumprod(target_vec, ariadne_embed_cache.centroid(chunks)), 4),
            places=4,
        )

    def test_forward_linked_notes_are_excluded_by_default(self):
        files = {"a.md": "shared words here [[b]]", "b.md": "shared words here", "c.md": "shared words here"}
        self.assertEqual([r["name"] for r in self.similar(files, "a")], ["c"])

    def test_backlinked_notes_are_excluded_by_default(self):
        files = {"a.md": "shared words here", "b.md": "shared words here [[a]]", "c.md": "shared words here"}
        self.assertEqual([r["name"] for r in self.similar(files, "a")], ["c"])

    def test_all_includes_linked_notes_and_labels_them(self):
        files = {"a.md": "shared words here [[b]]", "b.md": "shared words here", "c.md": "shared words here"}
        results = self.similar(files, "a", include_linked=True)
        by_name = {r["name"]: r for r in results}
        self.assertEqual(sorted(by_name), ["b", "c"])
        self.assertTrue(by_name["b"]["linked"])
        self.assertFalse(by_name["c"]["linked"])

    def test_limit_caps_the_result_count(self):
        files = {f"n{i}.md": "shared words here" for i in range(6)}
        files["target.md"] = "shared words here"
        self.assertEqual(len(self.similar(files, "target", limit=2)), 2)

    def test_missing_target_embedding_is_unavailable(self):
        _, notes, name_index, _ = self.prepare({"a.md": "a", "b.md": "b"})
        target = ariadne_similar.resolve_target("a", notes, name_index)
        with self.assertRaises(ariadne_embed_cache.EmbedUnavailable):
            ariadne_similar.find_similar(target, notes, {}, name_index, 10, False)


class FormatTextTests(unittest.TestCase):
    def test_control_characters_in_note_data_are_stripped(self):
        target = {"name": "tar\x1b[31mget"}
        results = [
            {
                "name": "ev\x07il",
                "path": "/v/ev.md",
                "score": 0.5,
                "linked": False,
                "crosses": False,
                "cluster": 0,
                "preview": "p\x1bq",
            }
        ]
        out = ariadne_similar_report.format_text(target, results, 2, False, "/v")
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, out)

    def test_empty_results_still_name_the_target(self):
        out = ariadne_similar_report.format_text({"name": "solo"}, [], 7, False, "/v")
        self.assertIn("solo", out)
        self.assertIn("7", out)


class FormatJsonTests(unittest.TestCase):
    def test_control_characters_are_stripped_from_names_and_previews(self):
        target = {"name": "tar\x1bget", "path": "/v/t.md"}
        results = [{"name": "ev\x07il", "path": "/v/e.md", "score": 0.5, "linked": False, "preview": "p\x1bq"}]
        payload = json.loads(ariadne_similar_report.format_json(target, results, False, "/v", "m"))
        self.assertNotIn("\x1b", payload["target"]["name"])
        self.assertNotIn("\x07", payload["similar"][0]["name"])
        self.assertNotIn("\x1b", payload["similar"][0]["preview"])


class ResolveTargetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = tmp.name
        write_vault(self.vault, {"Alpha Note.md": "a", "sub/Beta.md": "b"})
        self.notes = ariadne_similar.scan_vault(self.vault, [])
        self.name_index = ariadne_common.build_name_index([n["path"] for n in self.notes])

    def resolve(self, spec):
        return ariadne_similar.resolve_target(spec, self.notes, self.name_index)

    def test_resolves_by_absolute_path(self):
        self.assertEqual(self.resolve(os.path.join(self.vault, "Alpha Note.md"))["name"], "Alpha Note")

    def test_resolves_by_name(self):
        self.assertEqual(self.resolve("Alpha Note")["name"], "Alpha Note")

    def test_resolves_by_name_case_insensitively(self):
        self.assertEqual(self.resolve("alpha note")["name"], "Alpha Note")

    def test_resolves_nested_note_by_name(self):
        self.assertEqual(self.resolve("Beta")["name"], "Beta")

    def test_unknown_target_is_none(self):
        self.assertIsNone(self.resolve("no such note"))

    def test_a_path_outside_the_vault_cannot_be_selected(self):
        self.assertIsNone(self.resolve("/etc/passwd"))


if __name__ == "__main__":
    unittest.main()
