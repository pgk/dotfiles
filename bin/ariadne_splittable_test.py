#!/usr/bin/env python3

"""Tests for ariadne-graph --splittable candidates: long, multi-section notes that
aren't themselves acting as an index. Synthetic notes only, never ~/notes."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common
import ariadne_splittable

DEV_VAULT = (
    Path(__file__).resolve().parent.parent
    / "base/nvim/nvim/lua/plugins/ariadne/dev-vault"
)


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class NoteStatsTests(unittest.TestCase):
    def test_word_count_excludes_frontmatter(self):
        raw = "---\ntitle: X\ntags: [a, b, c]\n---\none two three four five\n"
        stats = ariadne_splittable.note_stats("/v/n.md", raw, {}, set())
        self.assertEqual(stats["words"], 5)

    def test_headers_are_h2_and_deeper_in_document_order(self):
        raw = "# Title\n\nintro\n\n## Background\n\ntext\n\n### Approach A\n\nmore\n\n## Open questions\n"
        stats = ariadne_splittable.note_stats("/v/n.md", raw, {}, set())
        self.assertEqual(stats["headers"], ["Background", "Approach A", "Open questions"])

    def test_out_degree_counts_distinct_resolved_targets(self):
        name_index = {"a": "/v/a.md", "b": "/v/b.md"}
        files = {"/v/n.md", "/v/a.md", "/v/b.md"}
        raw = "links [[a]] and [[b]] and [[a]] again"
        stats = ariadne_splittable.note_stats("/v/n.md", raw, name_index, files)
        self.assertEqual(stats["out_degree"], 2)

    def test_out_degree_excludes_self_link(self):
        name_index = {"n": "/v/n.md"}
        stats = ariadne_splittable.note_stats("/v/n.md", "[[n]]", name_index, {"/v/n.md"})
        self.assertEqual(stats["out_degree"], 0)

    def test_out_degree_excludes_unresolved_links(self):
        stats = ariadne_splittable.note_stats("/v/n.md", "[[nowhere]]", {}, {"/v/n.md"})
        self.assertEqual(stats["out_degree"], 0)

    def test_out_degree_excludes_a_resolved_target_outside_the_scanned_set(self):
        # Resolves via name_index, but isn't in `files` -- e.g. an --exclude'd note.
        name_index = {"elsewhere": "/other-vault/elsewhere.md"}
        stats = ariadne_splittable.note_stats("/v/n.md", "[[elsewhere]]", name_index, {"/v/n.md"})
        self.assertEqual(stats["out_degree"], 0)

    def test_blank_header_line_does_not_capture_the_next_paragraph(self):
        raw = "## \n\nthis is body text, not a header\n\n## Real\n"
        stats = ariadne_splittable.note_stats("/v/n.md", raw, {}, set())
        self.assertEqual(stats["headers"], ["Real"])

    def test_headers_inside_fenced_code_blocks_are_not_counted(self):
        raw = (
            "# Cheatsheet\n\nShort note, one idea.\n\n"
            "```bash\n## build step\nmake build\n## test step\nmake test\n## ship step\nmake ship\n```\n"
        )
        stats = ariadne_splittable.note_stats("/v/n.md", raw, {}, set())
        self.assertEqual(stats["headers"], [])


class SelectTests(unittest.TestCase):
    def run_select(self, root, min_headers=3, min_words=1200, max_out_degree=8):
        files = list(ariadne_common.iter_markdown_files(root, []))
        name_index = ariadne_common.build_name_index(files)
        return ariadne_splittable.select(files, name_index, min_headers, min_words, max_out_degree, root)

    def test_many_headers_alone_is_a_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            body = "\n\n".join(f"## Section {i}\n\ntext" for i in range(4))
            write_vault(root, {"multi.md": body})
            candidates = self.run_select(root)
        self.assertEqual([c["name"] for c in candidates], ["multi"])

    def test_word_count_alone_is_a_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"sprawl.md": "word " * 1500})
            candidates = self.run_select(root)
        self.assertEqual([c["name"] for c in candidates], ["sprawl"])

    def test_word_count_gate_is_inclusive_of_the_minimum(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {
                "at-min.md": "word " * 1200,
                "below-min.md": "word " * 1199,
            })
            candidates = self.run_select(root)
        self.assertEqual([c["name"] for c in candidates], ["at-min"])

    def test_short_and_headerless_is_not_a_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"atomic.md": "a short, single idea."})
            candidates = self.run_select(root)
        self.assertEqual(candidates, [])

    def test_high_out_degree_vetoes_an_otherwise_matching_note(self):
        with tempfile.TemporaryDirectory() as root:
            body = "word " * 1500 + " ".join(f"[[t{i}]]" for i in range(9))
            files = {"moc.md": body}
            files.update({f"t{i}.md": "stub" for i in range(9)})
            write_vault(root, files)
            candidates = self.run_select(root)
        self.assertNotIn("moc", [c["name"] for c in candidates])

    def test_out_degree_veto_is_strictly_less_than_the_max(self):
        # The gate is `< max_out_degree`, not `<=` -- exactly at the max vetoes,
        # one below it doesn't. max_out_degree=1 makes this cheap to pin.
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {
                "at-max.md": "## A\n## B\n## C\n\n[[t1]]",
                "below-max.md": "## A\n## B\n## C\n",
                "t1.md": "stub",
            })
            candidates = self.run_select(root, max_out_degree=1)
        self.assertEqual([c["name"] for c in candidates], ["below-max"])

    def test_candidates_sort_by_words_descending_then_name(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {
                "b-long.md": "word " * 1300,
                "a-longer.md": "word " * 1400,
                "c-tie.md": "word " * 1300,
            })
            candidates = self.run_select(root)
        self.assertEqual([c["name"] for c in candidates], ["a-longer", "b-long", "c-tie"])


class DevVaultFixtureTests(unittest.TestCase):
    """Pins the fixture contract documented in ariadne/CLAUDE.md and PLAN-0006:
    splittable-index's out-degree sits exactly at the default max, proving the
    veto is `< max_out_degree`, not `<=` -- the boundary the fixture exists for."""

    def test_candidate_is_flagged_and_the_index_is_vetoed_at_the_exact_boundary(self):
        files = list(ariadne_common.iter_markdown_files(str(DEV_VAULT), []))
        name_index = ariadne_common.build_name_index(files)
        candidates = ariadne_splittable.select(files, name_index, 3, 1200, 8, str(DEV_VAULT))
        names = {c["name"] for c in candidates}
        self.assertEqual(names, {"splittable-candidate"})
        self.assertNotIn("splittable-index", names)


class UnreadableNoteTests(unittest.TestCase):
    def test_unreadable_note_is_skipped_with_a_warning(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"sprawl.md": "word " * 1500})
            unreadable = Path(root) / "locked.md"
            unreadable.write_text("word " * 1500)
            os.chmod(unreadable, 0)
            stderr = io.StringIO()
            try:
                files = list(ariadne_common.iter_markdown_files(root, []))
                name_index = ariadne_common.build_name_index(files)
                with contextlib.redirect_stderr(stderr):
                    candidates = ariadne_splittable.select(files, name_index, 3, 1200, 8, root)
            finally:
                os.chmod(unreadable, 0o644)
        self.assertEqual([c["name"] for c in candidates], ["sprawl"])
        self.assertIn("locked.md", stderr.getvalue())
        self.assertIn("warning", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
