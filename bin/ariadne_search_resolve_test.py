#!/usr/bin/env python3
"""How `--from` resolves a note, and what it refuses.

Split from ariadne_search_from_test.py, which covers the ranking, the prefix and
the report shape -- that file reached the 400-line limit, and resolution is a
self-contained seam: these cases are about which note a spec names, not about
what happens once one is found.

The sharp case is a path inside an `--exclude`d subtree whose basename collides
with a note elsewhere. Falling back to the basename there ran the query against
a note the user never named.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common
from ariadne_similar_testkit import ariadne_similar, fake_embedder, write_vault

DATABASES = "Write-ahead logging keeps the database consistent after a crash.\n"
GARDENING = "Mulch in autumn holds moisture through the dry season.\n"
STORAGE = "A database crash is survived by replaying the write-ahead log.\n"


def run_search(argv, files, calls=None, want_stderr=False):
    """`run_search` over a throwaway vault, with a throwaway embedding cache."""
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
        write_vault(root, files)
        args = ariadne_similar.parse_args([*argv, root])
        # `args.exclude or []` exactly as main() does it -- scanning with a bare
        # [] here would quietly test a vault main() would never have built.
        notes = ariadne_similar.scan_vault(root, args.exclude or [])
        name_index = ariadne_common.build_name_index([n["path"] for n in notes])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
            with redirect_stdout(out), redirect_stderr(err):
                code = ariadne_similar.run_search(
                    args, root, notes, name_index, fake_embedder(calls=calls)
                )
        return (code, err.getvalue()) if want_stderr else (code, out.getvalue())



class FromResolutionTests(unittest.TestCase):
    """What `--from` accepts as a note, and how it refuses the rest."""

    FILES = {"db.md": DATABASES, "drafts/scratch.md": GARDENING}

    def test_a_path_outside_the_vault_is_refused(self):
        code, out = run_search(["--search", "q", "--from", "/etc/passwd", "--json"], self.FILES)
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["available"])

    def test_a_note_excluded_from_the_scan_cannot_be_the_origin(self):
        """--exclude keeps a subtree out of the HTTP upload; a note that never
        got scanned must not become an origin by the back door."""
        code, out = run_search(
            ["--search", "q", "--from", "scratch", "--exclude", "drafts/*", "--json"], self.FILES
        )
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["available"])

    def test_an_excluded_path_does_not_retarget_to_a_namesake(self):
        """The sharp version: --from names a path inside an --exclude'd subtree
        while another note elsewhere shares its basename. Falling back to the
        basename there would run the query against a note the user never named,
        label the results with it, and point ctrl-y's wikilink at it."""
        files = {
            "drafts/scratch.md": "A private draft about compensation review.\n",
            "archive/scratch.md": GARDENING,
            "db.md": DATABASES,
        }
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            write_vault(root, files)
            argv = ["--search", "a private draft about compensation review",
                    "--from", os.path.join(root, "drafts", "scratch.md"),
                    "--exclude", "drafts/*", "--json", root]
            args = ariadne_similar.parse_args(argv)
            notes = ariadne_similar.scan_vault(root, args.exclude or [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            calls, out = [], io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    code = ariadne_similar.run_search(
                        args, root, notes, name_index, fake_embedder(calls=calls)
                    )
            self.assertEqual(code, 1)
            self.assertIsNone(json.loads(out.getvalue())["target"])
            self.assertEqual([c for c in calls if "compensation" in c], [])

    def test_a_symlink_resolved_path_still_resolves(self):
        """What nvim actually sends: it reports a buffer's name with symlinks
        resolved while the vault stays as configured, so without the realpath
        pass every --from from the editor would now be refused."""
        with tempfile.TemporaryDirectory() as real, tempfile.TemporaryDirectory() as holder:
            write_vault(real, {"note.md": DATABASES, "dup/note.md": GARDENING})
            link = os.path.join(holder, "vault-link")
            os.symlink(real, link)
            notes = ariadne_similar.scan_vault(link, [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            spec = os.path.realpath(os.path.join(link, "note.md"))
            self.assertNotIn(spec, [n["path"] for n in notes])  # the cheap match misses
            origin = ariadne_similar.resolve_target(spec, notes, name_index, path_only=True)
            self.assertIsNotNone(origin)
            self.assertEqual(os.path.relpath(origin["path"], link), "note.md")

    def test_a_bare_name_still_falls_back_when_no_path_is_given(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"deep/db.md": DATABASES})
            notes = ariadne_similar.scan_vault(root, [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            got = ariadne_similar.resolve_target("db", notes, name_index, path_only=True)
            self.assertIsNotNone(got)

    def test_a_bare_note_name_resolves(self):
        code, _ = run_search(["--search", "q", "--from", "db", "--json"], self.FILES)
        self.assertEqual(code, 0)

    def test_a_control_character_in_the_from_spec_is_not_echoed_raw(self):
        code, out = run_search(["--search", "q", "--from", "no\x1bpe", "--json"], self.FILES)
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)


class FromArgumentTests(unittest.TestCase):
    def check(self, argv):
        args = ariadne_similar.parse_args(argv)
        ariadne_similar.split_positional(args)
        ariadne_similar.check_args(args)

    def test_from_without_search_is_refused(self):
        # Matched on the message, not just the type: without --search this argv
        # also fails positional splitting, so a bare assertRaises passes whether
        # or not the rule under test exists at all.
        with self.assertRaisesRegex(ValueError, "--from"):
            self.check(["--from", "db", "a-note", "/v"])

    def test_a_blank_from_note_is_refused(self):
        for spec in ("", "   "):
            with self.subTest(spec=repr(spec)), self.assertRaises(ValueError):
                self.check(["--search", "q", "--from", spec, "/v"])

    def test_search_with_from_still_takes_only_the_vault(self):
        args = ariadne_similar.parse_args(["--search", "q", "--from", "db", "/v"])
        self.assertEqual(ariadne_similar.split_positional(args), (None, "/v"))

    def test_all_and_no_bridge_are_allowed_once_from_supplies_a_note(self):
        for flag in ("--all", "--no-bridge"):
            with self.subTest(flag=flag):
                self.check(["--search", "q", "--from", "db", flag, "/v"])

    def test_all_and_no_bridge_are_still_refused_without_from(self):
        for flag in ("--all", "--no-bridge"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.check(["--search", "q", flag, "/v"])


if __name__ == "__main__":
    unittest.main()
