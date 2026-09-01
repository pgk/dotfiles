#!/usr/bin/env python3

"""Tests for ariadne-similar's cluster-aware ranking and its report layer.

Split out of ariadne-similar_test.py, which was over the 400-line limit. Run against
synthetic notes only (never ~/notes); no test may require a live embedding server.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_common
import ariadne_embed_cache
import ariadne_similar_report
from ariadne_similar_testkit import fake_embedder, ariadne_similar, write_vault


# Cluster A is the target's own neighbourhood; a3 belongs to it but is unlinked to
# the target, so it survives the unlinked filter. Cluster B is a separate component
# sharing less of the target's vocabulary, so pure similarity ranks a3 above b1 and
# only bridge ranking can invert that.
CLUSTER_VAULT = {
    "t.md": "alpha beta gamma delta [[a1]] [[a2]]",
    "a1.md": "wholly different vocabulary [[a2]] [[a3]]",
    "a2.md": "wholly different vocabulary [[a3]]",
    "a3.md": "alpha beta gamma delta",
    "b1.md": "alpha beta yankee zulu [[b2]] [[b3]]",
    "b2.md": "unrelated words entirely [[b3]]",
    "b3.md": "unrelated words entirely",
}


class ClusterRankingTests(unittest.TestCase):
    def prepare(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_vault(tmp.name, files)
        notes = ariadne_similar.scan_vault(tmp.name, [])
        name_index = ariadne_common.build_name_index([n["path"] for n in notes])
        cached = {}
        ariadne_embed_cache.refresh(notes, cached, 0, fake_embedder())
        return notes, name_index, cached

    def rank(self, files=None, target_name="t", bridge_first=True):
        notes, name_index, cached = self.prepare(files or CLUSTER_VAULT)
        clusters, shape = ariadne_similar.cluster_notes(notes, name_index)
        target = ariadne_similar.resolve_target(target_name, notes, name_index)
        results = ariadne_similar.find_similar(
            target, notes, cached, name_index, 10, False, clusters=clusters, bridge_first=bridge_first
        )
        return results, clusters, shape

    def test_the_fixture_really_does_favour_the_same_cluster_note_on_similarity(self):
        # Without this the bridging assertion below would pass for the wrong reason.
        results, _, _ = self.rank(bridge_first=False)
        by_name = {r["name"]: r for r in results}
        self.assertGreater(by_name["a3"]["score"], by_name["b1"]["score"])
        self.assertEqual(results[0]["name"], "a3")

    def test_cross_cluster_pairs_rank_above_same_cluster_ones(self):
        results, _, _ = self.rank()
        names = [r["name"] for r in results]
        self.assertLess(names.index("b1"), names.index("a3"))
        # a3 is the most similar note of all, so it losing the top slot is the point.
        self.assertTrue(results[0]["crosses"])
        self.assertEqual(names[-1], "a3")

    def test_no_bridge_restores_pure_similarity_order(self):
        bridged = [r["name"] for r in self.rank()[0]]
        plain = [r["name"] for r in self.rank(bridge_first=False)[0]]
        self.assertNotEqual(bridged, plain)
        self.assertEqual(sorted(bridged), sorted(plain))

    def test_every_result_is_labelled_with_its_cluster(self):
        results, clusters, _ = self.rank()
        by_name = {r["name"]: r for r in results}
        self.assertFalse(by_name["a3"]["crosses"])
        self.assertTrue(by_name["b1"]["crosses"])
        self.assertEqual(len({by_name["a3"]["cluster"], by_name["b1"]["cluster"]}), 2)
        self.assertEqual(len(clusters), len(CLUSTER_VAULT))

    def test_the_limit_applies_to_each_group_separately(self):
        # The cross-cluster pool is far larger in any real vault, so a shared
        # limit would leave no within-cluster hits to compare against.
        notes, name_index, cached = self.prepare(CLUSTER_VAULT)
        clusters, _ = ariadne_similar.cluster_notes(notes, name_index)
        target = ariadne_similar.resolve_target("t", notes, name_index)
        results = ariadne_similar.find_similar(
            target, notes, cached, name_index, 1, False, clusters=clusters, bridge_first=True
        )
        self.assertEqual([r["crosses"] for r in results], [True, False])
        self.assertEqual(results[1]["name"], "a3")

    def test_the_best_same_cluster_hit_survives_the_limit(self):
        results, _, _ = self.rank()
        self.assertIn("a3", [r["name"] for r in results])

    def test_no_bridge_applies_one_shared_limit(self):
        notes, name_index, cached = self.prepare(CLUSTER_VAULT)
        clusters, _ = ariadne_similar.cluster_notes(notes, name_index)
        target = ariadne_similar.resolve_target("t", notes, name_index)
        results = ariadne_similar.find_similar(
            target, notes, cached, name_index, 1, False, clusters=clusters, bridge_first=False
        )
        self.assertEqual([r["name"] for r in results], ["a3"])

    def test_within_a_partition_similarity_still_decides(self):
        results, _, _ = self.rank()
        crossing = [r["score"] for r in results if r["crosses"]]
        self.assertEqual(crossing, sorted(crossing, reverse=True))

    def test_a_vault_with_no_links_ranks_exactly_as_similarity_alone(self):
        # Every note is its own cluster, so every pair crosses and the within-cluster
        # group is empty -- the degenerate case a fragmented vault would produce.
        unlinked = {name: text.split(" [[")[0] for name, text in CLUSTER_VAULT.items()}
        results = self.rank(unlinked)[0]
        # Without this, the assertion below would also pass if `crosses` were stuck
        # at False, which is the opposite failure.
        self.assertTrue(all(r["crosses"] for r in results))
        plain = [r["name"] for r in self.rank(unlinked, bridge_first=False)[0]]
        self.assertEqual([r["name"] for r in results], plain)

    def test_omitting_cluster_data_falls_back_to_similarity_order(self):
        notes, name_index, cached = self.prepare(CLUSTER_VAULT)
        target = ariadne_similar.resolve_target("t", notes, name_index)
        results = ariadne_similar.find_similar(target, notes, cached, name_index, 10, False)
        self.assertEqual(results[0]["name"], "a3")
        self.assertFalse(any(r["crosses"] for r in results))

    def test_shape_describes_the_graph_the_clustering_ran_on(self):
        _, _, shape = self.rank()
        self.assertEqual(shape["notes"], len(CLUSTER_VAULT))
        self.assertEqual(shape["components"], 2)
        self.assertEqual(shape["isolated"], 0)
        self.assertGreaterEqual(shape["clusters"], 2)
        self.assertGreater(shape["modularity"], 0.0)

    def test_clustering_is_stable_across_runs(self):
        notes, name_index, _ = self.prepare(CLUSTER_VAULT)
        first, _ = ariadne_similar.cluster_notes(notes, name_index)
        for _ in range(3):
            self.assertEqual(ariadne_similar.cluster_notes(notes, name_index)[0], first)


class ClusterOutputTests(unittest.TestCase):
    def result(self, **overrides):
        row = {
            "name": "other",
            "path": "/v/other.md",
            "score": 0.5,
            "linked": False,
            "crosses": True,
            "cluster": 3,
            "preview": "",
        }
        row.update(overrides)
        return row

    SHAPE = {
        "notes": 9, "edges": 4, "components": 3, "largest_component": 5,
        "isolated": 1, "clusters": 4, "largest_cluster": 5, "modularity": 0.12,
    }

    def test_text_report_marks_a_bridging_hit_with_its_cluster(self):
        out = ariadne_similar_report.format_text({"name": "t"}, [self.result()], 2, False, "/v")
        self.assertIn("[cluster 3]", out)

    def test_text_report_leaves_same_cluster_hits_unmarked(self):
        out = ariadne_similar_report.format_text(
            {"name": "t"}, [self.result(crosses=False)], 2, False, "/v"
        )
        self.assertNotIn("cluster", out)

    def test_the_two_groups_get_their_own_headings(self):
        rows = [self.result(), self.result(name="near", crosses=False, cluster=1)]
        out = ariadne_similar_report.format_text(
            {"name": "t"}, rows, 9, False, "/v", self.SHAPE, grouped=True
        )
        self.assertIn("Bridging other clusters (1)", out)
        self.assertIn("Within cluster 1 (1)", out)
        self.assertLess(out.index("Bridging"), out.index("Within cluster"))

    def test_an_empty_group_gets_no_heading(self):
        out = ariadne_similar_report.format_text(
            {"name": "t"}, [self.result()], 9, False, "/v", self.SHAPE, grouped=True
        )
        self.assertIn("Bridging other clusters", out)
        self.assertNotIn("Within cluster", out)

    def test_ungrouped_rendering_keeps_pure_similarity_order(self):
        # What --no-bridge renders. Grouping must follow the flag, not the mere
        # presence of a shape summary, or the flag only half works.
        rows = [
            self.result(name="near", score=0.90, crosses=False, cluster=1),
            self.result(name="far", score=0.50),
        ]
        out = ariadne_similar_report.format_text(
            {"name": "t"}, rows, 9, False, "/v", self.SHAPE, grouped=False
        )
        self.assertNotIn("Bridging", out)
        self.assertNotIn("Within cluster", out)
        self.assertLess(out.index("near"), out.index("far"))

    def test_no_headings_when_no_clustering_ran(self):
        rows = [self.result(crosses=False, cluster=None)]
        out = ariadne_similar_report.format_text({"name": "t"}, rows, 9, False, "/v")
        self.assertNotIn("Bridging", out)
        self.assertNotIn("Within", out)

    def test_text_report_carries_the_graph_shape_as_its_own_caveat(self):
        out = ariadne_similar_report.format_text(
            {"name": "t"}, [self.result()], 9, False, "/v", self.SHAPE
        )
        self.assertIn("9 notes", out)
        self.assertIn("3 components", out)
        self.assertIn("0.120", out)

    def test_json_carries_shape_and_per_result_cluster_fields(self):
        shape = {"notes": 2, "edges": 1, "components": 1, "largest_component": 2,
                 "isolated": 0, "clusters": 1, "largest_cluster": 2, "modularity": 0.0}
        payload = json.loads(
            ariadne_similar_report.format_json(
                {"name": "t", "path": "/v/t.md"}, [self.result()], False, "/v", "m", shape=shape
            )
        )
        self.assertEqual(payload["shape"], shape)
        self.assertTrue(payload["similar"][0]["crosses"])
        self.assertEqual(payload["similar"][0]["cluster"], 3)

    def test_json_shape_is_null_when_embeddings_were_unavailable(self):
        payload = json.loads(
            ariadne_similar_report.format_json(None, [], False, "/v", "m", error="down")
        )
        self.assertIsNone(payload["shape"])

if __name__ == "__main__":
    unittest.main()
