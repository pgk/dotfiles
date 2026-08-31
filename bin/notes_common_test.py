#!/usr/bin/env python3

"""Tests for bin/notes_common.py, run against synthetic notes only (never ~/notes)."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_common


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class ExtractLinksTests(unittest.TestCase):
    def test_extracts_link_target_not_alias_display_text(self):
        links = notes_common.extract_links("see [[hub|the hub note]]")
        self.assertEqual(links, ["hub"])

    def test_strips_heading_fragment(self):
        links = notes_common.extract_links("[[hub#Some Heading]]")
        self.assertEqual(links, ["hub"])

    def test_strips_folder_prefix(self):
        links = notes_common.extract_links("[[sub/hub]]")
        self.assertEqual(links, ["hub"])

    def test_transclusion_is_extracted_like_a_link(self):
        links = notes_common.extract_links("![[hub]]")
        self.assertEqual(links, ["hub"])


class ResolveLinkTests(unittest.TestCase):
    def test_case_insensitive_resolution(self):
        index = notes_common.build_name_index(["/vault/hub.md"])
        self.assertEqual(notes_common.resolve_link("HUB", index), "/vault/hub.md")

    def test_strips_md_extension(self):
        index = notes_common.build_name_index(["/vault/hub.md"])
        self.assertEqual(notes_common.resolve_link("hub.md", index), "/vault/hub.md")

    def test_dotted_note_name_resolves(self):
        index = notes_common.build_name_index(["/vault/node.js.md"])
        self.assertEqual(notes_common.resolve_link("node.js", index), "/vault/node.js.md")

    def test_unresolved_link_returns_none(self):
        index = notes_common.build_name_index(["/vault/hub.md"])
        self.assertIsNone(notes_common.resolve_link("ghost", index))


class BuildNameIndexTests(unittest.TestCase):
    def test_duplicate_stem_keeps_first_and_warns(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            index = notes_common.build_name_index(["/vault/a/dup.md", "/vault/b/dup.md"])
        self.assertEqual(index["dup"], "/vault/a/dup.md")
        self.assertIn("duplicate note name 'dup'", captured.getvalue())


class IterMarkdownFilesTests(unittest.TestCase):
    def test_exclude_removes_matching_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "hub.md": "[[templates/skip-me]]",
                    "templates/skip-me.md": "content",
                },
            )
            paths = list(notes_common.iter_markdown_files(tmp, ["templates/*"]))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"hub.md"})

    def test_symlinked_file_outside_vault_is_skipped(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as vault:
            secret = Path(outside) / "secret.md"
            secret.write_text("outside content")
            (Path(vault) / "innocent.md").symlink_to(secret)
            paths = list(notes_common.iter_markdown_files(vault, []))
            self.assertEqual(paths, [])

    def test_dot_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    ".obsidian/config.md": "ignored",
                    "note.md": "kept",
                },
            )
            paths = list(notes_common.iter_markdown_files(tmp, []))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"note.md"})

    def test_duplicate_stem_traversal_order_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a/dup.md": "first", "b/dup.md": "second"})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            self.assertEqual([Path(p).parent.name for p in paths], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
