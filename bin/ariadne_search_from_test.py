#!/usr/bin/env python3
"""Tests for `--search PHRASE --from NOTE`: a passage lifted out of a note.

Split from ariadne_search_test.py, which covers the bare `--search` phrase --
same split as ariadne_similar_cli_test.py / ariadne_similar_clusters_test.py.
How `--from` resolves a note is split again into ariadne_search_resolve_test.py;
all three stay under the 400-line limit.

The behaviour under test: `--from` names where the text came from,
which is what licenses ranking a passage the way a whole note is ranked --
excluding that note, marking what it already links to, and splitting crossing
from within its cluster.
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
import ariadne_note_text
import ariadne_ranking
import ariadne_search
from ariadne_similar_testkit import ariadne_similar, fake_embedder, notes_and_cache, write_vault

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


class RankAgainstTests(unittest.TestCase):
    """The ranking core, on hand-built inputs: no CLI, no cache files."""

    def rank(self, files, origin_name, phrase, *, include_linked=False, clusters=None,
             bridge_first=False, limit=10):
        """`clusters` is keyed by note NAME here: notes_and_cache builds a fresh
        temporary vault per call, so a path-keyed map from one call matches
        nothing in the next."""
        notes, cached = notes_and_cache(files)
        name_index = ariadne_common.build_name_index([n["path"] for n in notes])
        origin = next(n for n in notes if n["name"] == origin_name)
        by_path = {n["name"]: n["path"] for n in notes}
        labels = {by_path[name]: c for name, c in (clusters or {}).items()}
        query = fake_embedder(dims=64)([phrase])
        return notes, ariadne_ranking.rank_against(
            query, origin, notes, cached, name_index, limit, include_linked,
            clusters=labels or None, bridge_first=bridge_first,
        )

    def test_the_origin_note_is_left_out_of_its_own_results(self):
        _, results = self.rank(
            {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE},
            "db", DATABASES,
        )
        self.assertNotIn("db", [r["name"] for r in results])

    def test_every_other_note_is_still_ranked(self):
        """Only the origin is dropped -- the exclusion must not be broader."""
        _, results = self.rank(
            {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE},
            "db", DATABASES,
        )
        self.assertEqual({r["name"] for r in results}, {"garden", "storage"})

    def test_a_note_the_origin_links_to_is_dropped_without_all(self):
        _, results = self.rank(
            {"db.md": DATABASES + "See [[storage]].\n", "storage.md": STORAGE, "garden.md": GARDENING},
            "db", DATABASES,
        )
        self.assertEqual({r["name"] for r in results}, {"garden"})

    def test_a_linked_note_is_kept_and_marked_under_all(self):
        _, results = self.rank(
            {"db.md": DATABASES + "See [[storage]].\n", "storage.md": STORAGE, "garden.md": GARDENING},
            "db", DATABASES, include_linked=True,
        )
        marked = {r["name"]: r["linked"] for r in results}
        self.assertEqual(marked, {"storage": True, "garden": False})

    def test_crossing_is_measured_against_the_origins_cluster(self):
        _, results = self.rank(
            {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE},
            "db", DATABASES, clusters={"db": 0, "storage": 0, "garden": 7},
        )
        crosses = {r["name"]: r["crosses"] for r in results}
        self.assertEqual(crosses, {"storage": False, "garden": True})

    def test_the_query_vectors_are_scored_not_the_origins_stored_ones(self):
        """The whole point: the passage is the query, not the note it came from.

        `garden` is the passage; `db` is the origin. If the origin's own vector
        were being used, the gardening note would not be the top hit.
        """
        _, results = self.rank(
            {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE},
            "db", GARDENING, include_linked=True,
        )
        self.assertEqual(results[0]["name"], "garden")

    def test_bridging_puts_crossing_rows_first(self):
        _, results = self.rank(
            {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE},
            "db", DATABASES, clusters={"db": 0, "storage": 0, "garden": 7},
            bridge_first=True,
        )
        # storage scores higher on this phrase, so only the bridge ordering can
        # put the cross-cluster garden row above it.
        self.assertEqual([r["name"] for r in results], ["garden", "storage"])


class LiftedQueryPrefixTests(unittest.TestCase):
    """Measured: a passage is not a title-shaped query.

    `task: search result | query: ` is worth +1.5% MRR on title-shaped queries
    (PLAN-0008) but costs ~1% on 300-800 character passages lifted out of notes,
    across two seeds on a 314-source public corpus. So the prefix is applied to
    a typed phrase and withheld from a lifted one, and `--from` is the signal.
    """

    def test_a_lifted_passage_is_embedded_raw(self):
        self.assertEqual(ariadne_search.query_texts("a passage", lifted=True), ["a passage"])

    def test_a_typed_phrase_still_gets_the_query_prefix(self):
        self.assertEqual(
            ariadne_search.query_texts("crash recovery", lifted=False),
            ["task: search result | query: crash recovery"],
        )

    def test_run_search_with_from_embeds_the_passage_unprefixed(self):
        calls = []
        run_search(["--search", DATABASES.strip(), "--from", "db"], {"db.md": DATABASES}, calls)
        self.assertIn(f"db\n\n{DATABASES.strip()}", calls)
        self.assertNotIn(ariadne_search.query_text(DATABASES.strip()), calls)

    def test_the_origin_notes_name_reaches_the_embedder(self):
        """Worth +2.7% / +1.8% MRR when the name carries words; see bin/CLAUDE.md."""
        calls = []
        run_search(["--search", "mulch and moisture", "--from", "db"], {"db.md": DATABASES}, calls)
        self.assertIn("db\n\nmulch and moisture", calls)

    def test_a_date_titled_origin_contributes_no_name(self):
        """The daily-note case: a date title costs -2.2% MRR, so it is left off."""
        calls = []
        run_search(
            ["--search", "mulch and moisture", "--from", "2026-09-05"],
            {"2026-09-05.md": DATABASES}, calls,
        )
        self.assertIn("mulch and moisture", calls)
        self.assertNotIn("2026-09-05\n\nmulch and moisture", calls)

    def test_run_search_without_from_keeps_the_prefix(self):
        calls = []
        run_search(["--search", "crash recovery"], {"db.md": DATABASES}, calls)
        self.assertIn(ariadne_search.query_text("crash recovery"), calls)
        self.assertNotIn("crash recovery", calls)


class FromReportTests(unittest.TestCase):
    FILES = {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE}

    def test_json_is_the_whole_note_shape_not_the_grouped_one(self):
        """similar.lua indexes `similar`; search.lua indexes `groups`."""
        code, out = run_search(["--search", "mulch and moisture", "--from", "db", "--json"], self.FILES)
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertIn("similar", payload)
        self.assertNotIn("groups", payload)
        self.assertEqual(payload["target"]["name"], "db")

    def test_the_passage_is_what_gets_ranked_not_the_origin_note(self):
        """run_search must embed the passage and score with that.

        The phrase is about gardening while its origin `db` is about databases,
        so handing the origin's own stored vectors to the ranking instead would
        put `storage` on top rather than `garden`.
        """
        code, out = run_search(
            ["--search", "mulch and moisture", "--from", "db", "--all", "--json"], self.FILES
        )
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["similar"][0]["name"], "garden")

    def test_json_carries_the_passage_that_was_searched(self):
        code, out = run_search(["--search", "mulch and moisture", "--from", "db", "--json"], self.FILES)
        self.assertEqual(json.loads(out)["passage"], "mulch and moisture")

    def test_a_whole_note_query_has_no_passage(self):
        """The field distinguishes the two, so it must stay null for a note query."""
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            write_vault(root, self.FILES)
            args = ariadne_similar.parse_args(["db", root, "--json"])
            notes = ariadne_similar.scan_vault(root, [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    ariadne_similar.run_query(args, root, "db", notes, name_index, fake_embedder())
        self.assertIsNone(json.loads(out.getvalue())["passage"])

    def test_the_egress_notice_says_a_passage_was_sent(self):
        """The "what is leaving this machine" notice has to name the right thing."""
        _, err = run_search(
            ["--search", "mulch", "--from", "db"], self.FILES, want_stderr=True
        )
        self.assertIn("sending your selected passage and its note's name to", err)

    def test_the_egress_notice_drops_the_name_when_the_name_is_not_sent(self):
        """A date-titled note contributes no name, so the notice must not claim one."""
        _, err = run_search(
            ["--search", "mulch", "--from", "2026-09-05"],
            {"2026-09-05.md": DATABASES}, want_stderr=True,
        )
        self.assertIn("sending your selected passage to", err)
        self.assertNotIn("note's name", err)

    def test_the_egress_notice_still_says_phrase_without_from(self):
        _, err = run_search(["--search", "mulch"], self.FILES, want_stderr=True)
        self.assertIn("sending your search phrase to", err)

    def test_the_text_header_says_a_passage_not_the_note(self):
        code, out = run_search(["--search", "mulch and moisture", "--from", "db"], self.FILES)
        self.assertEqual(code, 0)
        self.assertIn("a passage from 'db'", out)

    def test_an_unknown_from_note_fails_in_the_whole_note_json_shape(self):
        code, out = run_search(["--search", "q", "--from", "nope", "--json"], self.FILES)
        payload = json.loads(out)
        self.assertEqual(code, 1)
        self.assertFalse(payload["available"])
        self.assertIn("similar", payload)
        self.assertIsNone(payload["target"])
        # Without this the shared report_missing_note helper can drop `passage`
        # for the --from caller and no suite notices -- a mutation that survived.
        self.assertEqual(payload["passage"], "q")

    def test_an_unknown_target_of_a_whole_note_query_carries_no_passage(self):
        """The same helper serves both modes; only --from supplies a passage."""
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            write_vault(root, self.FILES)
            args = ariadne_similar.parse_args(["nope", root, "--json"])
            notes = ariadne_similar.scan_vault(root, [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    code = ariadne_similar.run_query(
                        args, root, "nope", notes, name_index, fake_embedder()
                    )
        self.assertEqual(code, 1)
        self.assertIsNone(json.loads(out.getvalue())["passage"])


class LongSelectionTests(unittest.TestCase):
    """A selection past the model's context must not lose its tail.

    The defect PLAN-0008 removed for notes: one vector for arbitrarily long
    text. `rank_against` already scores a multi-chunk query on its best chunk,
    so the fix is to hand it more than one chunk.
    """

    FILES = {"db.md": DATABASES, "garden.md": GARDENING, "storage.md": STORAGE}
    # A database-heavy head with a gardening tail, sized so the tail owns a
    # whole window: averaged into one vector it is outvoted two to one, but
    # chunked it gets a vector of its own, which is the behaviour under test.
    MIXED = (DATABASES * 60) + (GARDENING * 30)

    def test_the_tail_owns_a_chunk_of_its_own(self):
        """Guards the fixture, not the code: if the sizes drift so that every
        chunk is database-heavy, the test below would pass for a bad reason."""
        chunks = ariadne_note_text.passage_chunks(self.MIXED)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(any("Write-ahead" not in c for c in chunks))

    def test_a_long_passage_is_embedded_as_exactly_its_chunks(self):
        calls = []
        run_search(["--search", self.MIXED, "--from", "db"], self.FILES, calls)
        expected = ariadne_note_text.passage_chunks(self.MIXED, "db")
        self.assertGreater(len(expected), 1)
        # `db.md` is itself indexed as one chunk that also starts "db\n\n", so an
        # inequality here passes even with chunking switched off entirely.
        self.assertEqual([c for c in calls if c.startswith("db\n\n")][1:], expected)

    def test_the_tail_of_a_long_passage_can_win(self):
        code, out = run_search(
            ["--search", self.MIXED, "--from", "db", "--all", "--json"], self.FILES
        )
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["similar"][0]["name"], "garden")

    def test_a_short_passage_is_still_a_single_query_vector(self):
        calls = []
        run_search(["--search", "mulch and moisture", "--from", "db"], self.FILES, calls)
        self.assertEqual(
            [c for c in calls if c.endswith("mulch and moisture")], ["db\n\nmulch and moisture"]
        )


if __name__ == "__main__":
    unittest.main()
