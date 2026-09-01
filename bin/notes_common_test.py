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


class PrintableTests(unittest.TestCase):
    def test_control_characters_become_spaces(self):
        self.assertEqual(notes_common.printable("a\x1b[31mb\x07c"), "a [31mb c")

    def test_ordinary_text_including_unicode_is_untouched(self):
        self.assertEqual(notes_common.printable("Σημείωση — note"), "Σημείωση — note")

    def test_newlines_and_tabs_are_flattened(self):
        self.assertEqual(notes_common.printable("a\nb\tc"), "a b c")

    def test_non_string_input_is_coerced(self):
        self.assertEqual(notes_common.printable(OSError("boom")), "boom")


class BuildNameIndexTests(unittest.TestCase):
    def test_duplicate_stem_keeps_first_and_warns(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            index = notes_common.build_name_index(["/vault/a/dup.md", "/vault/b/dup.md"])
        self.assertEqual(index["dup"], "/vault/a/dup.md")
        self.assertIn("duplicate note name 'dup'", captured.getvalue())


class DuplicateWarningTests(unittest.TestCase):
    def test_a_control_character_in_a_duplicate_name_cannot_drive_the_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"dup\x1b[31mname.md": "a", "sub/dup\x1b[31mNAME.md": "b"})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                notes_common.build_name_index(paths)
        captured = stderr.getvalue()
        self.assertIn("duplicate note name", captured)
        self.assertNotIn("\x1b", captured)


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


class ExcludeMatchingTests(unittest.TestCase):
    """--exclude is the only thing keeping a subtree out of notes-similar's upload."""

    def kept(self, patterns, files=None):
        files = files or {
            "top.md": "", "journal/a.md": "", "journal/deep/b.md": "",
            "Personal/d.md": "", "templates/t.md": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            with contextlib.redirect_stderr(io.StringIO()):
                paths = list(notes_common.iter_markdown_files(tmp, patterns))
            return sorted(str(Path(p).relative_to(tmp)) for p in paths)

    def test_a_bare_directory_name_excludes_its_whole_tree(self):
        self.assertEqual(self.kept(["journal"]), ["Personal/d.md", "templates/t.md", "top.md"])

    def test_a_trailing_slash_is_accepted(self):
        self.assertEqual(self.kept(["journal/"]), self.kept(["journal"]))

    def test_the_existing_glob_form_still_works(self):
        self.assertEqual(self.kept(["journal/*"]), self.kept(["journal"]))

    def test_matching_is_case_insensitive(self):
        # The vault normally lives on a case-insensitive filesystem, where
        # `Journal` and `journal` name the same directory.
        self.assertEqual(self.kept(["JOURNAL"]), self.kept(["journal"]))
        self.assertNotIn("Personal/d.md", self.kept(["personal"]))

    def test_nested_directories_below_an_excluded_one_go_too(self):
        self.assertNotIn("journal/deep/b.md", self.kept(["journal"]))

    def test_a_pattern_matching_nothing_warns_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": ""})
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                list(notes_common.iter_markdown_files(tmp, ["drafts", "a.md"]))
        self.assertIn("--exclude drafts matched nothing", stderr.getvalue())
        self.assertNotIn("a.md matched nothing", stderr.getvalue())

    def test_the_warning_strips_control_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": ""})
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                list(notes_common.iter_markdown_files(tmp, ["ev\x1b[31mil"]))
        self.assertNotIn("\x1b", stderr.getvalue())

    def test_an_excluded_directory_is_not_walked_at_all(self):
        # Pruning, not filtering: the point of --exclude is that the subtree is
        # never read, so an unreadable note inside it must not even be opened.
        self.assertEqual(
            self.kept(["skip"], {"keep.md": "", "skip/deep/x.md": ""}), ["keep.md"]
        )

    def test_a_file_pattern_still_matches_only_that_file(self):
        self.assertEqual(
            self.kept(["*/d.md"]),
            ["journal/a.md", "journal/deep/b.md", "templates/t.md", "top.md"],
        )

    def test_matched_excludes_reports_which_pattern_hit(self):
        self.assertEqual(notes_common.matched_excludes("journal/a.md", ["journal", "x"]), {"journal"})
        self.assertEqual(notes_common.matched_excludes("top.md", ["journal"]), set())


class StripFrontmatterTests(unittest.TestCase):
    def test_strips_leading_frontmatter_block(self):
        text = notes_common.strip_frontmatter("---\ntitle: X\ntags:\n  - a\n---\nThe body.\n")
        self.assertEqual(text, "The body.\n")

    def test_note_without_frontmatter_is_unchanged(self):
        self.assertEqual(notes_common.strip_frontmatter("Just text.\n"), "Just text.\n")

    def test_frontmatter_only_note_yields_empty_string(self):
        self.assertEqual(notes_common.strip_frontmatter("---\ntitle: X\n---\n"), "")

    def test_unterminated_frontmatter_is_left_alone(self):
        text = notes_common.strip_frontmatter("---\ntitle: X\n")
        self.assertEqual(text, "---\ntitle: X\n")


class RequireVaultTests(unittest.TestCase):
    """The guard that keeps every notes-* tool from inventing a ~/notes default."""

    @contextlib.contextmanager
    def env(self, value):
        previous = os.environ.get("NOTES_VAULT")
        if value is None:
            os.environ.pop("NOTES_VAULT", None)
        else:
            os.environ["NOTES_VAULT"] = value
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("NOTES_VAULT", None)
            else:
                os.environ["NOTES_VAULT"] = previous

    def test_returns_an_explicit_path_unchanged(self):
        with self.env(None):
            self.assertEqual(notes_common.require_vault("/some/vault"), "/some/vault")

    def test_explicit_path_wins_over_the_environment(self):
        with self.env("/from/env"):
            self.assertEqual(notes_common.require_vault("/explicit"), "/explicit")

    def test_falls_back_to_notes_vault_env(self):
        with self.env("/from/env"):
            self.assertEqual(notes_common.require_vault(None), "/from/env")

    def test_raises_when_nothing_names_a_vault(self):
        with self.env(None):
            with self.assertRaises(ValueError) as ctx:
                notes_common.require_vault(None)
        self.assertIn("VAULT path is required", str(ctx.exception))

    def test_blank_argument_and_blank_env_do_not_count_as_a_vault(self):
        # A quoted-but-empty shell variable is the shape of the accident this
        # guard exists to stop; it must not read as "the user named a vault".
        with self.env("   "):
            with self.assertRaises(ValueError):
                notes_common.require_vault("  ")


if __name__ == "__main__":
    unittest.main()
