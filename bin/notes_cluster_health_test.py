#!/usr/bin/env python3

"""Tests for cluster-level health: coverage, and the clusters notes-graph reports.

Split out of notes_cluster_test.py and notes-graph_test.py, which the feature
pushed over the 400-line limit. Run against synthetic notes only (never ~/notes).
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("notes-graph")

loader = importlib.machinery.SourceFileLoader("notes_graph", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("notes_graph", loader)
notes_graph = importlib.util.module_from_spec(spec)
loader.exec_module(notes_graph)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_cluster
import notes_common


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def undirected(edges, isolated=()):
    graph = {node: set() for node in isolated}
    for left, right in edges:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    return graph


def ring_beside_a_clique(ring_n=6, clique_n=4):
    """A ring, plus a dense cluster it hangs off by one link.

    The clique is not decoration. A bare ring is not cohesive enough for Louvain
    to keep whole — it splits into arcs, each small enough to have an entry
    point. Beside a denser neighbour the arcs have more to lose by splitting, and
    the ring survives as one community.

    Ring length sets the coverage: 5 scores exactly 0.5 (spared only by the `>=`
    in hubless_clusters), 6 scores 0.4, 8 scores 0.286.
    """
    ring = [f"r{i:02}" for i in range(ring_n)]
    clique = [f"c{i:02}" for i in range(clique_n)]
    files = {f"{nm}.md": f"[[{ring[(i + 1) % ring_n]}]]" for i, nm in enumerate(ring)}
    files[f"{ring[0]}.md"] += f" [[{clique[0]}]]"
    for nm in clique:
        files[f"{nm}.md"] = " ".join(f"[[{other}]]" for other in clique if other != nm)
    return files


class ClusterEntryPointTests(unittest.TestCase):
    """Coverage: the share of a cluster its best-connected note reaches in one hop."""

    def entries(self, graph, labels=None):
        return notes_cluster.cluster_entry_points(graph, labels or notes_cluster.louvain(graph))

    def test_a_map_of_content_covers_its_whole_cluster(self):
        graph = undirected([("moc", n) for n in ("a", "b", "c", "d")])
        entry = self.entries(graph, dict.fromkeys(graph, 0))[0]
        self.assertEqual((entry["entry_point"], entry["reach"], entry["coverage"]), ("moc", 4, 1.0))

    def test_a_ring_has_no_note_that_covers_it(self):
        ring = [(f"n{i}", f"n{(i + 1) % 8}") for i in range(8)]
        entry = self.entries(undirected(ring), dict.fromkeys([f"n{i}" for i in range(8)], 0))[0]
        self.assertEqual(entry["reach"], 2)
        self.assertAlmostEqual(entry["coverage"], 2 / 7, places=3)

    def test_coverage_is_measured_inside_the_cluster_only(self):
        # `outsider` gives `a` a high raw degree, but it is in another cluster and
        # must not count toward covering this one.
        graph = undirected([("a", "b"), ("a", "outsider"), ("b", "c"), ("c", "a")])
        labels = {"a": 0, "b": 0, "c": 0, "outsider": 1}
        entry = next(e for e in self.entries(graph, labels) if e["cluster"] == 0)
        self.assertEqual((entry["reach"], entry["others"], entry["coverage"]), (2, 2, 1.0))

    def test_a_lone_note_is_its_own_entry_point(self):
        graph = undirected([], isolated=["z"])
        entry = self.entries(graph)[0]
        self.assertEqual((entry["size"], entry["coverage"], entry["entry_point"]), (1, 1.0, "z"))

    def test_every_cluster_is_reported_exactly_once(self):
        graph = undirected([("a", "b"), ("c", "d")], isolated=["z"])
        labels = notes_cluster.louvain(graph)
        entries = self.entries(graph, labels)
        self.assertEqual(len(entries), len(set(labels.values())))
        self.assertEqual(sorted(e["cluster"] for e in entries), sorted(set(labels.values())))

    def test_largest_cluster_is_reported_first(self):
        graph = undirected([("a", "b"), ("b", "c"), ("a", "c"), ("y", "z")])
        self.assertEqual([e["size"] for e in self.entries(graph)], [3, 2])

    def test_ties_resolve_to_the_first_note_in_sorted_order(self):
        ring = undirected([("b", "c"), ("c", "d"), ("d", "b")])
        entry = self.entries(ring, dict.fromkeys(ring, 0))[0]
        self.assertEqual(entry["entry_point"], "b")

    def test_empty_vault(self):
        self.assertEqual(notes_cluster.cluster_entry_points({}, {}), [])


class HublessClusterTests(unittest.TestCase):
    def build(self, files, hub_reach=0.5):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            neighbors = notes_cluster.adjacency(graph)
            labels = notes_cluster.louvain(neighbors)
            return notes_graph.hubless_clusters(neighbors, labels, hub_reach, tmp)

    def test_a_ring_has_no_entry_point(self):
        hubless = self.build(ring_beside_a_clique())
        self.assertEqual(len(hubless), 1)
        self.assertEqual((hubless[0]["size"], hubless[0]["reach"], hubless[0]["others"]), (6, 2, 5))

    def test_the_dense_cluster_beside_it_is_not_reported(self):
        hubless = self.build(ring_beside_a_clique())
        self.assertEqual([e["name"][0] for e in hubless], ["r"])

    def test_a_map_of_content_cluster_is_not_reported(self):
        files = {"moc.md": " ".join(f"[[n{i}]]" for i in range(6))}
        files.update({f"n{i}.md": "[[moc]]" for i in range(6)})
        self.assertEqual(self.build(files), [])

    def test_small_clusters_are_never_reported(self):
        # A three-note cluster needs no map of content, and coverage says so
        # without a separate size threshold to pick.
        self.assertEqual(self.build({"a.md": "[[b]]", "b.md": "[[c]]", "c.md": "[[a]]"}), [])

    def test_a_cluster_exactly_on_the_threshold_is_spared(self):
        # A five-note ring scores exactly 0.5. It is spared only because the test
        # is `coverage >= min_coverage`; flipping that to `>` would start
        # reporting every five-note path in the vault.
        entries = self.build(ring_beside_a_clique(ring_n=5))
        self.assertEqual(entries, [])

    def test_an_orphan_is_not_reported_as_a_hubless_cluster(self):
        self.assertEqual(self.build({"lonely.md": "no links"}), [])

    def test_lowering_hub_reach_below_the_coverage_spares_the_cluster(self):
        # The ring scores 0.4, so it is reported at the 0.5 default and not at 0.3.
        self.assertEqual(len(self.build(ring_beside_a_clique(), hub_reach=0.5)), 1)
        self.assertEqual(self.build(ring_beside_a_clique(), hub_reach=0.3), [])

    def test_entries_carry_a_name_and_a_vault_relative_path(self):
        entry = self.build(ring_beside_a_clique())[0]
        self.assertTrue(entry["name"].startswith("r"))
        self.assertEqual(entry["rel"], entry["name"] + ".md")
        self.assertNotIn("/", entry["rel"])


class HublessReportTests(unittest.TestCase):
    ENTRY = {
        "cluster": 2, "size": 8, "entry_point": "/v/r00.md", "reach": 2,
        "others": 7, "coverage": 0.2857, "name": "r00", "rel": "r00.md",
    }
    SHAPE = {
        "notes": 8, "edges": 8, "components": 1, "largest_component": 8,
        "isolated": 0, "clusters": 1, "largest_cluster": 8, "modularity": 0.4,
    }

    def test_report_states_the_cluster_size_and_the_best_reach(self):
        out = "\n".join(notes_graph.format_hubless([self.ENTRY]))
        self.assertIn("cluster 2", out)
        self.assertIn("[8 notes]", out)
        self.assertIn("more than 2 of the other 7", out)
        self.assertIn("r00", out)

    def test_control_characters_in_a_note_name_are_stripped(self):
        out = "\n".join(notes_graph.format_hubless([dict(self.ENTRY, name="ev\x1b[31mil", rel="a\x07.md")]))
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, out)

    def test_text_report_carries_the_graph_shape(self):
        # Asserted against describe_shape's own wording: "8 notes" alone also
        # appears in the "Scanned 8 notes" header, so it would pass with the
        # shape line dropped entirely.
        out = notes_graph.format_text([], [], 3, 8, "/v", [self.ENTRY], self.SHAPE)
        self.assertIn("graph: 8 notes, 8 links, 1 components", out)
        self.assertIn("modularity 0.400", out)

    def test_the_shape_line_is_omitted_when_there_is_no_shape(self):
        out = notes_graph.format_text([], [], 3, 8, "/v", [self.ENTRY])
        self.assertNotIn("graph:", out)

    def test_all_clear_message_mentions_hubs_too(self):
        out = notes_graph.format_text([], [], 3, 5, "/v")
        self.assertIn("every cluster has a hub", out)

    def test_hubless_clusters_alone_still_produce_a_report(self):
        out = notes_graph.format_text([], [], 3, 8, "/v", [self.ENTRY])
        self.assertIn("Clusters without a hub", out)
        self.assertNotIn("Orphans", out)


class HublessCliTests(unittest.TestCase):
    def test_json_carries_shape_and_hubless_clusters(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, ring_beside_a_clique())
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--json"],
                capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
        self.assertEqual(payload["shape"]["notes"], 10)
        self.assertEqual(len(payload["hubless_clusters"]), 1)
        self.assertEqual(payload["hubless_clusters"][0]["size"], 6)
        self.assertEqual(payload["orphans"], [])

    def test_rejects_a_hub_reach_outside_zero_to_one(self):
        # The vault is a real, empty temp dir rather than a path like /tmp: if the
        # --hub-reach check ever stopped running before the vault is walked, this
        # test must not start scanning someone's files.
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("0", "-0.5", "1.5", "nan", "inf"):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), tmp, "--hub-reach", bad],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0, bad)
                self.assertIn("--hub-reach", result.stderr)

    def test_accepts_the_inclusive_upper_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "[[a]]"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--hub-reach", "1", "--json"],
                capture_output=True, text=True, check=True,
            )
        self.assertEqual(json.loads(result.stdout)["hubless_clusters"], [])


if __name__ == "__main__":
    unittest.main()
