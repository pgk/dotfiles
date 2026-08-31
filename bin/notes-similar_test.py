#!/usr/bin/env python3

"""Tests for bin/notes-similar, run against synthetic notes only (never ~/notes).

No test may require a live embedding server: `fake_embedder` supplies deterministic
vectors and the CLI cases point at a closed loopback port. Cache and HTTP behaviour
live in notes_embed_cache_test.py and notes_embed_client_test.py.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_common
import notes_embed_cache
import notes_similar_report
from notes_similar_testkit import (
    fake_embedder,
    notes_similar,
    write_vault,
)


class NoteTextTests(unittest.TestCase):
    def test_frontmatter_is_stripped_and_name_prepended(self):
        text = notes_similar.note_text("my-note", "---\ntitle: X\ntags:\n  - a\n---\nThe body.\n")
        self.assertEqual(text, "my-note\n\nThe body.")

    def test_note_without_frontmatter_keeps_its_body(self):
        self.assertEqual(notes_similar.note_text("n", "Just text.\n"), "n\n\nJust text.")

    def test_frontmatter_only_note_yields_just_the_name(self):
        self.assertEqual(notes_similar.note_text("n", "---\ntitle: X\n---\n"), "n")

    def test_unterminated_frontmatter_is_left_alone(self):
        self.assertEqual(notes_similar.note_text("n", "---\ntitle: X\n"), "n\n\n---\ntitle: X")

    def test_long_note_is_truncated(self):
        text = notes_similar.note_text("n", "x" * (notes_similar.MAX_CHARS * 2))
        self.assertEqual(len(text), notes_similar.MAX_CHARS)

    def test_hash_ignores_frontmatter_only_edits(self):
        a = notes_similar.note_text("n", "---\ntags: [one]\n---\nBody.\n")
        b = notes_similar.note_text("n", "---\ntags: [two]\n---\nBody.\n")
        self.assertEqual(notes_similar.content_hash(a), notes_similar.content_hash(b))

    def test_hash_changes_when_body_changes(self):
        a = notes_similar.note_text("n", "Body one.")
        b = notes_similar.note_text("n", "Body two.")
        self.assertNotEqual(notes_similar.content_hash(a), notes_similar.content_hash(b))

    def test_preview_skips_headings_and_blank_lines(self):
        text = notes_similar.note_text("n", "# Heading\n\n\nReal first line.\n")
        self.assertEqual(notes_similar.preview_of(text), "Real first line.")


class ScanVaultTests(unittest.TestCase):
    def scan(self, files, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            return notes_similar.scan_vault(tmp, excludes or [])

    def test_collects_name_hash_and_links_in_one_pass(self):
        notes = self.scan({"a.md": "Links to [[b]] and [[c]].", "b.md": "Body b."})
        by_name = {n["name"]: n for n in notes}
        self.assertEqual(sorted(by_name), ["a", "b"])
        self.assertEqual(by_name["a"]["links"], ["b", "c"])
        self.assertEqual(
            by_name["a"]["hash"],
            notes_similar.content_hash(notes_similar.note_text("a", "Links to [[b]] and [[c]].")),
        )
        self.assertNotEqual(by_name["a"]["hash"], by_name["b"]["hash"])

    def test_excludes_are_honoured(self):
        notes = self.scan({"a.md": "a", "skip/b.md": "b"}, excludes=["skip/*"])
        self.assertEqual([n["name"] for n in notes], ["a"])


class FindSimilarTests(unittest.TestCase):
    def prepare(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_vault(tmp.name, files)
        notes = notes_similar.scan_vault(tmp.name, [])
        name_index = notes_common.build_name_index([n["path"] for n in notes])
        cached = {}
        notes_embed_cache.refresh(notes, cached, 0, fake_embedder())
        return tmp.name, notes, name_index, cached

    def similar(self, files, target_name, limit=10, include_linked=False):
        _, notes, name_index, cached = self.prepare(files)
        target = notes_similar.resolve_target(target_name, notes, name_index)
        return notes_similar.find_similar(target, notes, cached, name_index, limit, include_linked)

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
        target = notes_similar.resolve_target("a", notes, name_index)
        with self.assertRaises(notes_embed_cache.EmbedUnavailable):
            notes_similar.find_similar(target, notes, {}, name_index, 10, False)


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
        out = notes_similar_report.format_text(target, results, 2, False, "/v")
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, out)

    def test_empty_results_still_name_the_target(self):
        out = notes_similar_report.format_text({"name": "solo"}, [], 7, False, "/v")
        self.assertIn("solo", out)
        self.assertIn("7", out)


class FormatJsonTests(unittest.TestCase):
    def test_control_characters_are_stripped_from_names_and_previews(self):
        target = {"name": "tar\x1bget", "path": "/v/t.md"}
        results = [{"name": "ev\x07il", "path": "/v/e.md", "score": 0.5, "linked": False, "preview": "p\x1bq"}]
        payload = json.loads(notes_similar_report.format_json(target, results, False, "/v", "m"))
        self.assertNotIn("\x1b", payload["target"]["name"])
        self.assertNotIn("\x07", payload["similar"][0]["name"])
        self.assertNotIn("\x1b", payload["similar"][0]["preview"])


class ResolveTargetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = tmp.name
        write_vault(self.vault, {"Alpha Note.md": "a", "sub/Beta.md": "b"})
        self.notes = notes_similar.scan_vault(self.vault, [])
        self.name_index = notes_common.build_name_index([n["path"] for n in self.notes])

    def resolve(self, spec):
        return notes_similar.resolve_target(spec, self.notes, self.name_index)

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
