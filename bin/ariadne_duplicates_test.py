#!/usr/bin/env python3

"""Tests for near-duplicate detection and `ariadne-similar --duplicates`.

Synthetic vaults only, never ~/notes. The stand-in embedder is a bag-of-words
hash, so two notes with the same words land on the same vector.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_duplicates
import ariadne_similar_report
from ariadne_similar_testkit import ariadne_similar, fake_embedder, notes_and_cache, write_vault

SAME_IDEA = "Agents satisfice rather than optimise, because search costs time.\n"
OTHER_IDEA = "Silt fills the channel and the dredger clears it every spring.\n"


class TitleSimilarityTests(unittest.TestCase):
    def test_identical_titles_score_one(self):
        self.assertEqual(ariadne_duplicates.title_similarity("a-note", "a-note"), 1.0)

    def test_case_is_ignored(self):
        self.assertEqual(ariadne_duplicates.title_similarity("A-Note", "a-note"), 1.0)

    def test_unrelated_titles_score_low(self):
        pair = ariadne_duplicates.title_similarity("harbour-dredging", "bounded-rationality")
        self.assertLess(pair, ariadne_duplicates.TITLE_MIN)


class FindDuplicatesTests(unittest.TestCase):
    def found(self, files, **kwargs):
        notes, cached = notes_and_cache(files)
        return ariadne_duplicates.find_duplicates(notes, cached, **kwargs)

    def find(self, files, **kwargs):
        """Both lists flattened, duplicates first — the old flat contract."""
        found = self.found(files, **kwargs)
        return found["duplicates"] + found["possible"]

    def test_matching_body_and_matching_title_is_a_duplicate(self):
        pairs = self.find({"satisficing.md": SAME_IDEA, "satisficing-1.md": SAME_IDEA})
        self.assertEqual([p["verdict"] for p in pairs], ["duplicate"])
        self.assertEqual({pairs[0]["a"], pairs[0]["b"]}, {"satisficing", "satisficing-1"})

    def test_matching_body_but_unrelated_title_is_only_possible(self):
        """Pins that the title is consulted at all. The bag-of-words stand-in cannot
        speak to whether 0.80 is the right cosine bar — that calibration is borrowed."""
        pairs = self.find({"satisficing.md": SAME_IDEA, "bounded-rationality.md": SAME_IDEA})
        self.assertEqual([p["verdict"] for p in pairs], ["possible"])
        self.assertGreaterEqual(pairs[0]["score"], ariadne_duplicates.EMBED_MIN)
        self.assertLess(pairs[0]["title"], ariadne_duplicates.TITLE_MIN)

    def test_matching_title_but_unrelated_body_is_not_reported_at_all(self):
        """Title alone is not a signal either — it only breaks a cosine tie."""
        self.assertEqual(self.find({"satisficing.md": SAME_IDEA, "satisficing-1.md": OTHER_IDEA}), [])

    def test_unrelated_notes_are_not_reported(self):
        self.assertEqual(self.find({"a.md": SAME_IDEA, "b.md": OTHER_IDEA}), [])

    def test_each_pair_is_reported_once(self):
        pairs = self.find({"a.md": SAME_IDEA, "b.md": SAME_IDEA, "c.md": SAME_IDEA})
        self.assertEqual(len(pairs), 3)
        self.assertEqual(len({frozenset((p["a"], p["b"])) for p in pairs}), 3)

    def test_a_note_is_never_paired_with_itself(self):
        pairs = self.find({"a.md": SAME_IDEA, "b.md": SAME_IDEA})
        self.assertTrue(all(p["a"] != p["b"] for p in pairs))

    def test_duplicates_sort_ahead_of_higher_scoring_possibles(self):
        """A caller's limit truncates the noisy band, so the band must sort last."""
        pairs = self.find(
            {
                "satisficing.md": SAME_IDEA,
                "satisficing-1.md": SAME_IDEA + "One extra clause.\n",
                "bounded-rationality.md": SAME_IDEA,
            }
        )
        verdicts = [p["verdict"] for p in pairs]
        self.assertEqual(verdicts, sorted(verdicts, key=lambda v: v != "duplicate"))
        best_possible = max(p["score"] for p in pairs if p["verdict"] == "possible")
        first_duplicate = next(p for p in pairs if p["verdict"] == "duplicate")
        self.assertLess(first_duplicate["score"], best_possible)

    def test_a_lower_embedding_bar_admits_more_pairs(self):
        loose = self.find({"a.md": SAME_IDEA, "b.md": OTHER_IDEA}, embed_min=0.0)
        self.assertEqual(len(loose), 1)

    def test_a_lower_title_bar_promotes_a_possible_to_a_duplicate(self):
        files = {"satisficing.md": SAME_IDEA, "bounded-rationality.md": SAME_IDEA}
        self.assertEqual([p["verdict"] for p in self.find(files, title_min=0.0)], ["duplicate"])

    def test_a_note_with_no_cached_embedding_is_skipped(self):
        notes, cached = notes_and_cache({"a.md": SAME_IDEA, "b.md": SAME_IDEA})
        cached.pop((notes[0]["path"], notes[0]["hash"]))
        found = ariadne_duplicates.find_duplicates(notes, cached)
        self.assertEqual((found["duplicate_total"], found["possible_total"]), (0, 0))

    def test_an_empty_vault_reports_nothing(self):
        found = ariadne_duplicates.find_duplicates([], {})
        self.assertEqual(found, {"duplicates": [], "duplicate_total": 0, "possible": [], "possible_total": 0})


class BoundsTests(unittest.TestCase):
    """The lists are capped while scanning, but the totals still count everything."""

    def found(self, files, **kwargs):
        notes, cached = notes_and_cache(files)
        return ariadne_duplicates.find_duplicates(notes, cached, **kwargs)

    def test_the_limit_bounds_the_possible_list_without_hiding_the_total(self):
        names = ("satisficing", "bounded-rationality", "heuristics", "optimising", "search-costs")
        found = self.found({f"{n}.md": SAME_IDEA for n in names}, limit=2)
        self.assertEqual(len(found["possible"]), 2)
        self.assertEqual(found["possible_total"], 10)
        self.assertEqual(found["duplicate_total"], 0)

    def test_the_limit_keeps_the_highest_scoring_candidates(self):
        """Eviction is by score, so truncation must not drop a stronger pair."""
        files = {"satisficing.md": SAME_IDEA, "heuristics.md": SAME_IDEA,
                 "optimising.md": SAME_IDEA + "A wholly different closing clause here.\n"}
        every = self.found(files)["possible"]
        capped = self.found(files, limit=1)["possible"]
        self.assertEqual(len(capped), 1)
        self.assertEqual(capped[0]["score"], max(p["score"] for p in every))

    def test_a_generous_limit_keeps_every_candidate(self):
        names = ("satisficing", "bounded-rationality", "heuristics")
        found = self.found({f"{n}.md": SAME_IDEA for n in names}, limit=100)
        self.assertEqual(len(found["possible"]), found["possible_total"])

    def test_the_duplicate_list_is_capped_too(self):
        """A vault of near-identical stubs makes the duplicate list quadratic as well."""
        files = {f"duplicate-stub-{i}.md": SAME_IDEA for i in range(8)}
        notes, cached = notes_and_cache(files)
        original = ariadne_duplicates.MAX_DUPLICATES
        ariadne_duplicates.MAX_DUPLICATES = 3
        try:
            found = ariadne_duplicates.find_duplicates(notes, cached)
        finally:
            ariadne_duplicates.MAX_DUPLICATES = original
        self.assertEqual(len(found["duplicates"]), 3)
        self.assertEqual(found["duplicate_total"], 28)


class ReportTests(unittest.TestCase):
    PAIR = {
        "a": "satisficing",
        "a_path": "/v/satisficing.md",
        "b": "satisficing-1",
        "b_path": "/v/satisficing-1.md",
        "score": 0.8421,
        "title": 1.0,
        "verdict": "duplicate",
    }

    def text(self, duplicates, possible, duplicate_total=None, possible_total=None):
        found = {
            "duplicates": duplicates,
            "possible": possible,
            "duplicate_total": len(duplicates) if duplicate_total is None else duplicate_total,
            "possible_total": len(possible) if possible_total is None else possible_total,
        }
        return ariadne_similar_report.format_duplicates_text(found, 9, "/v", 0.8, 0.85)

    def test_an_empty_report_is_one_line(self):
        self.assertNotIn("\n", self.text([], []))

    def test_a_duplicate_shows_both_scores_and_both_paths(self):
        out = self.text([self.PAIR], [])
        self.assertIn("0.8421", out)
        self.assertIn("titles 1.00", out)
        self.assertIn("satisficing.md", out)
        self.assertIn("satisficing-1.md", out)

    def test_the_two_verdicts_get_their_own_sections(self):
        out = self.text([self.PAIR], [dict(self.PAIR, verdict="possible")])
        self.assertIn("Duplicates (1)", out)
        self.assertIn("Possibly the same idea (1)", out)

    def test_a_truncated_section_says_how_much_it_is_hiding(self):
        possible = [dict(self.PAIR, verdict="possible", a=f"n{i}") for i in range(2)]
        out = self.text([self.PAIR], possible, possible_total=5)
        self.assertIn("Duplicates (1)", out)
        self.assertIn("Possibly the same idea (2 of 5)", out)

    def test_a_truncated_duplicate_section_says_so_too(self):
        out = self.text([self.PAIR], [], duplicate_total=40)
        self.assertIn("Duplicates (1 of 40)", out)

    def test_control_characters_in_a_name_are_stripped(self):
        out = self.text([dict(self.PAIR, a="ev\x1b[31mil")], [])
        self.assertNotIn("\x1b", out)


class CliTests(unittest.TestCase):
    def run_cli(self, argv, files):
        # `load_or_refresh` writes an embedding cache under $XDG_CACHE_HOME, so it
        # has to be redirected or the suite litters the user's real ~/.cache with a
        # dead directory per run — one per temp vault, never reused.
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            write_vault(root, files)
            args = ariadne_similar.parse_args([*argv, root])
            notes = ariadne_similar.scan_vault(root, [])
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    cached = ariadne_similar.load_or_refresh(args, root, notes, fake_embedder())
                    code = ariadne_duplicates.run(args, root, notes, cached)
            return code, out.getvalue()

    def test_the_text_mode_reports_the_duplicate(self):
        code, out = self.run_cli(["--duplicates"], {"satisficing.md": SAME_IDEA, "satisficing-1.md": SAME_IDEA})
        self.assertEqual(code, 0)
        self.assertIn("Duplicates (1)", out)

    def test_the_json_mode_carries_the_thresholds_it_used(self):
        import json

        code, out = self.run_cli(["--duplicates", "--json"], {"satisficing.md": SAME_IDEA, "satisficing-1.md": SAME_IDEA})
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["embed_min"], ariadne_duplicates.EMBED_MIN)
        self.assertEqual(payload["title_min"], ariadne_duplicates.TITLE_MIN)
        self.assertEqual(payload["scanned"], 2)
        self.assertEqual([p["verdict"] for p in payload["pairs"]], ["duplicate"])

    def test_json_reports_how_many_possibles_the_limit_hid(self):
        import json

        # One idea under five unrelated titles: ten pairs, none of them a duplicate.
        names = ("satisficing", "bounded-rationality", "heuristics", "optimising", "search-costs")
        _, out = self.run_cli(["--duplicates", "--json", "-n", "2"], {f"{n}.md": SAME_IDEA for n in names})
        payload = json.loads(out)
        self.assertEqual(len(payload["pairs"]), 2)
        self.assertEqual(payload["possible_total"], 10)
        self.assertEqual(payload["duplicate_total"], 0)


class ArgumentTests(unittest.TestCase):
    def check(self, argv):
        args = ariadne_similar.parse_args(argv)
        ariadne_similar.split_positional(args)
        ariadne_similar.check_args(args)

    def test_duplicates_takes_the_vault_as_its_only_positional(self):
        args = ariadne_similar.parse_args(["--duplicates", "/v"])
        self.assertEqual(ariadne_similar.split_positional(args), (None, "/v"))

    def test_duplicates_rejects_a_target_note(self):
        args = ariadne_similar.parse_args(["--duplicates", "a-note", "/v"])
        with self.assertRaises(ValueError):
            ariadne_similar.split_positional(args)

    def test_duplicates_and_index_are_separate_modes(self):
        with self.assertRaises(ValueError):
            self.check(["--duplicates", "--index", "/v"])

    def test_a_threshold_outside_zero_to_one_is_refused(self):
        for argv in (["--duplicates", "--dup-min", "1.5", "/v"], ["--duplicates", "--dup-title-min", "-0.1", "/v"]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                self.check(argv)

    def test_the_thresholds_are_accepted_at_their_bounds(self):
        self.check(["--duplicates", "--dup-min", "0", "--dup-title-min", "1", "/v"])


if __name__ == "__main__":
    unittest.main()
