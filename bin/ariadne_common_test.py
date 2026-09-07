#!/usr/bin/env python3

"""Tests for bin/ariadne_common.py, run against synthetic notes only (never ~/notes)."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


BLOCK = (
    "<!-- ariadne:backlinks -->\n"
    "## Backlinks\n"
    "\n"
    "- [[hub]]\n"
    "- [[bridge]] — why this one matters\n"
    "<!-- /ariadne:backlinks -->\n"
)


FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "base/nvim/nvim/lua/plugins/ariadne/backlinks-block.fixture"
)


class SharedFixtureTests(unittest.TestCase):
    """The one artefact both strippers are pinned against.

    Each side used to be pinned by its own hand-written copy of a block, so
    neither pinned the other: they disagreed about unspaced markers and CRLF and
    both suites stayed green. `backlinks_spec.lua` asserts the editor *renders*
    exactly this file; here it must be what Python strips.
    """

    def test_strips_the_block_the_editor_renders(self):
        block = FIXTURE.read_text()
        self.assertEqual(ariadne_common.strip_backlinks_block("Body.\n\n" + block), "Body.\n\n")
        self.assertEqual(
            ariadne_common.extract_links("Body links [[real]].\n\n" + block), ["real"]
        )


class StripBacklinksBlockTests(unittest.TestCase):
    def test_an_unpaired_marker_above_a_block_does_not_swallow_the_prose(self):
        # The editor-side blocker, in its read-only form: a `.*?` reaching from
        # the stray marker to the real block's closer deleted the note's real
        # outbound edges from the graph and its prose from the embedding.
        raw = (
            "Intro [[a]].\n"
            "<!-- ariadne:backlinks -->\n"
            "An essay linking [[b]] and [[c]].\n" + BLOCK
        )
        stripped = ariadne_common.strip_backlinks_block(raw)
        self.assertIn("An essay linking [[b]] and [[c]].", stripped)
        self.assertEqual(ariadne_common.extract_links(raw), ["a", "b", "c"])

    def test_removes_every_block_not_only_the_first(self):
        self.assertEqual(
            ariadne_common.strip_backlinks_block(BLOCK + "middle\n" + BLOCK), "middle\n"
        )

    def test_crlf_line_endings_are_still_a_block(self):
        # A regex anchored on "\n" left a CRLF note's block links in the graph.
        raw = ("Body.\n\n" + BLOCK).replace("\n", "\r\n")
        self.assertEqual(ariadne_common.extract_links(raw), [])

    def test_only_ascii_whitespace_may_surround_a_marker(self):
        # `vim.trim` is byte-wise ASCII; a bare .strip() is the full Unicode
        # class, a strict superset. A marker behind a NBSP was a block here and
        # not in the editor, so the graph ignored it while the editor read its
        # rows back as authored links and wrote the mirror. `backlinks_spec.lua`
        # asserts the editor agrees on this exact input.
        raw = "\u00a0<!-- ariadne:backlinks -->\n- [[hub]]\n<!-- /ariadne:backlinks -->\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), raw)
        self.assertEqual(ariadne_common.extract_links(raw), ["hub"])

    def test_ascii_whitespace_around_a_marker_is_still_allowed(self):
        raw = " \t<!-- ariadne:backlinks -->\n- [[hub]]\n\t <!-- /ariadne:backlinks -->\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), "")

    def test_a_fenced_example_of_a_block_is_not_a_block(self):
        # A note documenting this feature quotes the markers. `backlinks_spec.lua`
        # asserts the editor leaves the same example alone rather than rewriting
        # it with live rows.
        raw = "```\n" + BLOCK + "```\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), raw)
        self.assertEqual(ariadne_common.extract_links(raw), ["hub", "bridge"])

    def test_an_unterminated_fence_is_not_a_fence(self):
        # Otherwise a stray ``` hides every marker below it.
        self.assertEqual(ariadne_common.extract_links("```\nBody [[a]].\n" + BLOCK), ["a"])

    def test_a_marker_is_the_exact_text_alone_on_its_line(self):
        # Deliberately strict, and matched line for line by `backlinks.spans`:
        # the two sides disagreeing about what a marker is means a mirror on one
        # side and not the other.
        for marker in ("<!--ariadne:backlinks-->", "<!-- ariadne:backlinks --> and more"):
            raw = marker + "\n- [[hub]]\n<!-- /ariadne:backlinks -->\n"
            self.assertEqual(ariadne_common.strip_backlinks_block(raw), raw)

    def test_removes_the_whole_block_including_its_heading(self):
        raw = "Body.\n\n" + BLOCK
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), "Body.\n\n")

    def test_note_without_a_block_is_untouched(self):
        raw = "Body with [[a link]].\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), raw)

    def test_unterminated_opening_marker_is_left_alone(self):
        raw = "Body.\n\n<!-- ariadne:backlinks -->\n- [[hub]]\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), raw)

    def test_text_after_the_block_survives(self):
        raw = BLOCK + "A footer line.\n"
        self.assertEqual(ariadne_common.strip_backlinks_block(raw), "A footer line.\n")


class ExtractLinksTests(unittest.TestCase):
    def test_block_links_are_not_authored_links(self):
        # The whole point of the strip: without it A links to B, so B's block
        # names A, so A's block names B, and every link mirrors itself.
        links = ariadne_common.extract_links("Body links [[real]].\n\n" + BLOCK)
        self.assertEqual(links, ["real"])

    def test_a_link_outside_the_block_is_still_found(self):
        self.assertEqual(ariadne_common.extract_links(BLOCK + "\nsee [[after]]"), ["after"])

    def test_extracts_link_target_not_alias_display_text(self):
        links = ariadne_common.extract_links("see [[hub|the hub note]]")
        self.assertEqual(links, ["hub"])

    def test_strips_heading_fragment(self):
        links = ariadne_common.extract_links("[[hub#Some Heading]]")
        self.assertEqual(links, ["hub"])

    def test_strips_folder_prefix(self):
        links = ariadne_common.extract_links("[[sub/hub]]")
        self.assertEqual(links, ["hub"])

    def test_transclusion_is_extracted_like_a_link(self):
        links = ariadne_common.extract_links("![[hub]]")
        self.assertEqual(links, ["hub"])


class WikilinkDisplayTests(unittest.TestCase):
    def display(self, text):
        return ariadne_common.wikilink_display(text)

    def test_a_plain_link_becomes_its_words(self):
        self.assertEqual(self.display("See [[Working Memory]] here."), "See Working Memory here.")

    def test_an_alias_wins_over_the_target(self):
        self.assertEqual(self.display("[[bounded-rationality|satisficing]]"), "satisficing")

    def test_a_blank_alias_falls_back_to_the_target(self):
        self.assertEqual(self.display("[[a-note|   ]]"), "a-note")

    def test_a_heading_anchor_is_dropped_for_the_title(self):
        self.assertEqual(self.display("[[a-note#Some Heading]]"), "a-note")

    def test_a_bare_heading_link_keeps_the_heading(self):
        """`[[#heading]]` points inside this note, so the heading is all the reader sees."""
        self.assertEqual(self.display("[[#Some Heading]]"), "Some Heading")

    def test_a_directory_prefix_is_dropped(self):
        self.assertEqual(self.display("[[dir/sub/a-note]]"), "a-note")

    def test_an_embed_loses_its_bang(self):
        self.assertEqual(self.display("![[a-note]]"), "a-note")

    def test_text_without_links_is_untouched(self):
        self.assertEqual(self.display("Plain prose, [brackets] and all."), "Plain prose, [brackets] and all.")

    def test_every_link_on_a_line_is_rewritten(self):
        self.assertEqual(self.display("[[a]] then [[b|B]] then [[c]]"), "a then B then c")

    def test_an_empty_link_leaves_nothing_behind(self):
        self.assertEqual(self.display("before [[]] after"), "before  after")

    def test_an_unclosed_link_is_left_alone(self):
        self.assertEqual(self.display("dangling [[a-note"), "dangling [[a-note")


class ResolveLinkTests(unittest.TestCase):
    def test_case_insensitive_resolution(self):
        index = ariadne_common.build_name_index(["/vault/hub.md"])
        self.assertEqual(ariadne_common.resolve_link("HUB", index), "/vault/hub.md")

    def test_strips_md_extension(self):
        index = ariadne_common.build_name_index(["/vault/hub.md"])
        self.assertEqual(ariadne_common.resolve_link("hub.md", index), "/vault/hub.md")

    def test_dotted_note_name_resolves(self):
        index = ariadne_common.build_name_index(["/vault/node.js.md"])
        self.assertEqual(ariadne_common.resolve_link("node.js", index), "/vault/node.js.md")

    def test_unresolved_link_returns_none(self):
        index = ariadne_common.build_name_index(["/vault/hub.md"])
        self.assertIsNone(ariadne_common.resolve_link("ghost", index))


class PrintableTests(unittest.TestCase):
    def test_control_characters_become_spaces(self):
        self.assertEqual(ariadne_common.printable("a\x1b[31mb\x07c"), "a [31mb c")

    def test_ordinary_text_including_unicode_is_untouched(self):
        self.assertEqual(ariadne_common.printable("Σημείωση — note"), "Σημείωση — note")

    def test_newlines_and_tabs_are_flattened(self):
        self.assertEqual(ariadne_common.printable("a\nb\tc"), "a b c")

    def test_non_string_input_is_coerced(self):
        self.assertEqual(ariadne_common.printable(OSError("boom")), "boom")


class BuildNameIndexTests(unittest.TestCase):
    def test_duplicate_stem_keeps_first_and_warns(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            index = ariadne_common.build_name_index(["/vault/a/dup.md", "/vault/b/dup.md"])
        self.assertEqual(index["dup"], "/vault/a/dup.md")
        self.assertIn("duplicate note name 'dup'", captured.getvalue())


class DuplicateWarningTests(unittest.TestCase):
    def test_a_control_character_in_a_duplicate_name_cannot_drive_the_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"dup\x1b[31mname.md": "a", "sub/dup\x1b[31mNAME.md": "b"})
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                ariadne_common.build_name_index(paths)
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
            paths = list(ariadne_common.iter_markdown_files(tmp, ["templates/*"]))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"hub.md"})

    def test_symlinked_file_outside_vault_is_skipped(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as vault:
            secret = Path(outside) / "secret.md"
            secret.write_text("outside content")
            (Path(vault) / "innocent.md").symlink_to(secret)
            paths = list(ariadne_common.iter_markdown_files(vault, []))
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
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"note.md"})

    def test_duplicate_stem_traversal_order_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a/dup.md": "first", "b/dup.md": "second"})
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            self.assertEqual([Path(p).parent.name for p in paths], ["a", "b"])


class ExcludeMatchingTests(unittest.TestCase):
    """--exclude is the only thing keeping a subtree out of ariadne-similar's upload."""

    def kept(self, patterns, files=None):
        files = files or {
            "top.md": "", "journal/a.md": "", "journal/deep/b.md": "",
            "Personal/d.md": "", "templates/t.md": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            with contextlib.redirect_stderr(io.StringIO()):
                paths = list(ariadne_common.iter_markdown_files(tmp, patterns))
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
                list(ariadne_common.iter_markdown_files(tmp, ["drafts", "a.md"]))
        self.assertIn("--exclude drafts matched nothing", stderr.getvalue())
        self.assertNotIn("a.md matched nothing", stderr.getvalue())

    def test_the_warning_strips_control_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": ""})
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                list(ariadne_common.iter_markdown_files(tmp, ["ev\x1b[31mil"]))
        self.assertNotIn("\x1b", stderr.getvalue())

    def test_an_excluded_directory_is_not_walked_at_all(self):
        """Pruning, not filtering. Asserted on the walk itself: the yielded file list
        looks identical either way, so it cannot tell pruning from a per-file filter."""
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"keep.md": "", "skip/deep/x.md": ""})
            visited = []
            real_walk = os.walk

            def spy(top, *args, **kwargs):
                for root, dirs, files in real_walk(top, *args, **kwargs):
                    visited.append(root)
                    yield root, dirs, files

            with mock.patch.object(ariadne_common.os, "walk", spy):
                kept = list(ariadne_common.iter_markdown_files(tmp, ["skip"]))
        self.assertEqual([os.path.relpath(p, tmp) for p in kept], ["keep.md"])
        self.assertEqual([os.path.relpath(r, tmp) for r in visited], ["."])

    def test_a_file_pattern_still_matches_only_that_file(self):
        self.assertEqual(
            self.kept(["*/d.md"]),
            ["journal/a.md", "journal/deep/b.md", "templates/t.md", "top.md"],
        )

    def test_matched_excludes_reports_which_pattern_hit(self):
        self.assertEqual(ariadne_common.matched_excludes("journal/a.md", ["journal", "x"]), {"journal"})
        self.assertEqual(ariadne_common.matched_excludes("top.md", ["journal"]), set())


class StripFrontmatterTests(unittest.TestCase):
    def test_strips_leading_frontmatter_block(self):
        text = ariadne_common.strip_frontmatter("---\ntitle: X\ntags:\n  - a\n---\nThe body.\n")
        self.assertEqual(text, "The body.\n")

    def test_note_without_frontmatter_is_unchanged(self):
        self.assertEqual(ariadne_common.strip_frontmatter("Just text.\n"), "Just text.\n")

    def test_frontmatter_only_note_yields_empty_string(self):
        self.assertEqual(ariadne_common.strip_frontmatter("---\ntitle: X\n---\n"), "")

    def test_unterminated_frontmatter_is_left_alone(self):
        text = ariadne_common.strip_frontmatter("---\ntitle: X\n")
        self.assertEqual(text, "---\ntitle: X\n")


class RequireVaultTests(unittest.TestCase):
    """The guard that keeps every ariadne-* tool from inventing a ~/notes default."""

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
            self.assertEqual(ariadne_common.require_vault("/some/vault"), "/some/vault")

    def test_explicit_path_wins_over_the_environment(self):
        with self.env("/from/env"):
            self.assertEqual(ariadne_common.require_vault("/explicit"), "/explicit")

    def test_falls_back_to_notes_vault_env(self):
        with self.env("/from/env"):
            self.assertEqual(ariadne_common.require_vault(None), "/from/env")

    def test_raises_when_nothing_names_a_vault(self):
        with self.env(None):
            with self.assertRaises(ValueError) as ctx:
                ariadne_common.require_vault(None)
        self.assertIn("VAULT path is required", str(ctx.exception))

    def test_blank_argument_and_blank_env_do_not_count_as_a_vault(self):
        # A quoted-but-empty shell variable is the shape of the accident this
        # guard exists to stop; it must not read as "the user named a vault".
        with self.env("   "):
            with self.assertRaises(ValueError):
                ariadne_common.require_vault("  ")


if __name__ == "__main__":
    unittest.main()
