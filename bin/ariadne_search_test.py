#!/usr/bin/env python3

"""Tests for semantic search and `ariadne-similar --search`.

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
import ariadne_common
import ariadne_search
import ariadne_similar_report
from ariadne_similar_testkit import ariadne_similar, fake_embedder, notes_and_cache, write_vault

DATABASES = "Write-ahead logging keeps the database consistent after a crash.\n"
GARDENING = "Mulch in autumn holds moisture through the dry season.\n"


def vec_for(text, dims=64):
    return fake_embedder(dims=dims)([text])[0]


class RankByClusterTests(unittest.TestCase):
    def rank(self, files, query, clusters, per_cluster=3, limit=10):
        notes, cached = notes_and_cache(files)
        by_name = {n["name"]: n["path"] for n in notes}
        cluster_by_path = {by_name[name]: cluster for name, cluster in clusters.items()}
        query_vec = vec_for(query)
        return ariadne_search.rank_by_cluster(
            query_vec, notes, cached, cluster_by_path, per_cluster=per_cluster, limit=limit
        )

    def test_per_cluster_cap_keeps_the_best_scoring_hits(self):
        files = {
            "db-a.md": DATABASES,
            "db-b.md": DATABASES + "Also covers checkpointing.\n",
            "db-c.md": DATABASES + "Also covers checkpointing and replay.\n",
        }
        clusters = {"db-a": 0, "db-b": 0, "db-c": 0}
        groups = self.rank(files, DATABASES, clusters, per_cluster=2)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["cluster_total"], 3)
        self.assertEqual(len(groups[0]["hits"]), 2)
        # db-a is the exact query text, so it must survive the cap.
        self.assertIn("db-a", {h["name"] for h in groups[0]["hits"]})

    def test_clusters_are_ordered_by_their_own_best_hit(self):
        files = {
            "db-a.md": DATABASES,
            "garden-a.md": GARDENING,
        }
        clusters = {"db-a": 0, "garden-a": 1}
        groups = self.rank(files, DATABASES, clusters)
        self.assertEqual([g["cluster"] for g in groups], [0, 1])

    def test_cluster_cap_drops_the_weakest_clusters(self):
        files = {"db-a.md": DATABASES, "garden-a.md": GARDENING}
        clusters = {"db-a": 0, "garden-a": 1}
        groups = self.rank(files, DATABASES, clusters, limit=1)
        self.assertEqual([g["cluster"] for g in groups], [0])

    def test_a_note_with_no_cached_embedding_is_skipped(self):
        notes, cached = notes_and_cache({"a.md": DATABASES, "b.md": DATABASES})
        cached.pop((notes[0]["path"], notes[0]["hash"]))
        query_vec = vec_for(DATABASES)
        groups = ariadne_search.rank_by_cluster(
            query_vec, notes, cached, {}, per_cluster=3, limit=10
        )
        hit_names = {h["name"] for g in groups for h in g["hits"]}
        self.assertEqual(hit_names, {notes[1]["name"]})


class ReportTests(unittest.TestCase):
    HIT = {"name": "write-ahead-logging", "path": "/v/write-ahead-logging.md", "score": 0.8421, "cluster": 2}

    def group(self, hits, cluster=2, cluster_total=None):
        return {"cluster": cluster, "cluster_total": cluster_total or len(hits), "hits": hits}

    def test_an_empty_result_is_one_line(self):
        out = ariadne_similar_report.format_search_text("crash recovery", [], 9, "/v")
        self.assertNotIn("\n", out)
        self.assertIn("crash recovery", out)

    def test_a_hit_shows_its_score_name_and_path(self):
        out = ariadne_similar_report.format_search_text("crash recovery", [self.group([self.HIT])], 9, "/v")
        self.assertIn("0.8421", out)
        self.assertIn("write-ahead-logging", out)
        self.assertIn("write-ahead-logging.md", out)

    def test_each_cluster_gets_its_own_heading(self):
        out = ariadne_similar_report.format_search_text(
            "q", [self.group([self.HIT], cluster=2), self.group([dict(self.HIT, name="mulching")], cluster=5)], 9, "/v"
        )
        self.assertIn("cluster 2", out)
        self.assertIn("cluster 5", out)

    def test_a_truncated_cluster_says_how_much_it_is_hiding(self):
        out = ariadne_similar_report.format_search_text(
            "q", [self.group([self.HIT], cluster_total=7)], 9, "/v"
        )
        self.assertIn("1 of 7", out)

    def test_control_characters_in_the_query_are_stripped(self):
        out = ariadne_similar_report.format_search_text("ev\x1b[31mil", [], 9, "/v")
        self.assertNotIn("\x1b", out)

    def test_json_carries_the_query_and_groups(self):
        import json

        out = ariadne_similar_report.format_search_json("crash recovery", [self.group([self.HIT])], 9, "/v", "m")
        payload = json.loads(out)
        self.assertEqual(payload["query"], "crash recovery")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["total_notes"], 9)
        self.assertEqual(len(payload["groups"]), 1)
        self.assertEqual(payload["groups"][0]["hits"][0]["name"], "write-ahead-logging")


class ArgumentTests(unittest.TestCase):
    def check(self, argv):
        args = ariadne_similar.parse_args(argv)
        ariadne_similar.split_positional(args)
        ariadne_similar.check_args(args)

    def test_search_takes_the_vault_as_its_only_positional(self):
        args = ariadne_similar.parse_args(["--search", "crash recovery", "/v"])
        self.assertEqual(ariadne_similar.split_positional(args), (None, "/v"))

    def test_search_rejects_a_target_note(self):
        args = ariadne_similar.parse_args(["--search", "q", "a-note", "/v"])
        with self.assertRaises(ValueError):
            ariadne_similar.split_positional(args)

    def test_search_and_index_are_separate_modes(self):
        with self.assertRaises(ValueError):
            self.check(["--search", "q", "--index", "/v"])

    def test_search_and_duplicates_are_separate_modes(self):
        with self.assertRaises(ValueError):
            self.check(["--search", "q", "--duplicates", "/v"])

    def test_all_and_no_bridge_are_refused_under_search(self):
        for flag in ("--all", "--no-bridge"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.check(["--search", "q", flag, "/v"])

    def test_blank_search_phrase_is_refused(self):
        for phrase in ("", "   "):
            with self.subTest(phrase=repr(phrase)), self.assertRaises(ValueError):
                self.check(["--search", phrase, "/v"])

    def test_per_cluster_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            self.check(["--search", "q", "--per-cluster", "0", "/v"])

    def test_per_cluster_is_accepted_at_its_default(self):
        self.check(["--search", "q", "/v"])


class CliTests(unittest.TestCase):
    def run_cli(self, argv, files):
        # load_or_refresh writes an embedding cache under $XDG_CACHE_HOME, so it
        # has to be redirected or the suite litters the user's real ~/.cache.
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            write_vault(root, files)
            args = ariadne_similar.parse_args([*argv, root])
            notes = ariadne_similar.scan_vault(root, [])
            name_index = ariadne_common.build_name_index([n["path"] for n in notes])
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache}):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    embedder = fake_embedder()
                    cached = ariadne_similar.load_or_refresh(args, root, notes, embedder)
                    clusters, shape = ariadne_similar.cluster_notes(notes, name_index)
                    query_vec = embedder([args.search])[0]
                    code = ariadne_search.run(args, root, notes, cached, clusters, shape, query_vec)
            return code, out.getvalue()

    def test_the_text_mode_finds_the_matching_note(self):
        code, out = self.run_cli(["--search", "database crash recovery"], {"db.md": DATABASES, "garden.md": GARDENING})
        self.assertEqual(code, 0)
        self.assertIn("db", out)

    def test_the_json_mode_carries_the_query(self):
        import json

        code, out = self.run_cli(["--search", "database crash recovery", "--json"], {"db.md": DATABASES})
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["query"], "database crash recovery")
        self.assertEqual(payload["total_notes"], 1)


if __name__ == "__main__":
    unittest.main()
