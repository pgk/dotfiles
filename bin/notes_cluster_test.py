#!/usr/bin/env python3

"""Tests for bin/notes_cluster.py, run against synthetic notes only (never ~/notes)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_cluster
import notes_common

DEV_VAULT = (
    Path(__file__).resolve().parent.parent
    / "base/nvim/nvim/lua/plugins/obsidian/dev-vault"
)


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def undirected(edges, isolated=()):
    """A {node: set(node)} map from an edge list, for tests that don't need files."""
    graph = {node: set() for node in isolated}
    for left, right in edges:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    return graph


TWO_TRIANGLES = undirected(
    [("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("d", "e"), ("d", "f"), ("e", "f")]
)


HARBOUR_RING = ("one", "two", "three", "four", "five", "six", "seven", "eight")


def grouping(labels):
    """Labels as a set of frozensets, so tests assert on the partition, not on ids."""
    groups = {}
    for node, cluster_id in labels.items():
        groups.setdefault(cluster_id, set()).add(node)
    return {frozenset(members) for members in groups.values()}


class BuildGraphTests(unittest.TestCase):
    def build(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            return {Path(p).stem: entry for p, entry in graph.items()}

    def test_links_are_undirected(self):
        graph = self.build({"a.md": "[[b]]", "b.md": "no links back"})
        names = lambda entry: {Path(p).stem for p in entry["neighbors"]}
        self.assertEqual(names(graph["a"]), {"b"})
        self.assertEqual(names(graph["b"]), {"a"})

    def test_unresolvable_links_are_recorded_not_edges(self):
        graph = self.build({"a.md": "[[ghost]]"})
        self.assertEqual(graph["a"]["neighbors"], set())
        self.assertEqual(graph["a"]["broken_links"], ["ghost"])

    def test_self_links_are_not_edges(self):
        graph = self.build({"a.md": "[[a]] and [[b]]", "b.md": ""})
        self.assertEqual({Path(p).stem for p in graph["a"]["neighbors"]}, {"b"})


class AdjacencyFromLinksTests(unittest.TestCase):
    """The in-memory path, for callers like notes-similar that already read the notes."""

    def test_agrees_with_build_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]] [[ghost]]", "b.md": "[[c]]", "c.md": "", "d.md": ""})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            from_files = {path: entry["neighbors"] for path, entry in graph.items()}
            entries = [
                {"path": p, "links": notes_common.extract_links(Path(p).read_text())}
                for p in paths
            ]
            self.assertEqual(notes_cluster.adjacency_from_links(entries, index), from_files)

    def test_links_outside_the_scanned_set_are_not_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "", "b.md": ""})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
        # `index` still resolves both notes, but only one is handed over as an entry.
        entries = [{"path": paths[0], "links": ["b"]}]
        self.assertEqual(notes_cluster.adjacency_from_links(entries, index), {paths[0]: set()})

    def test_self_links_are_not_edges(self):
        entries = [{"path": "/v/a.md", "links": ["a"]}]
        index = {"a": "/v/a.md"}
        self.assertEqual(notes_cluster.adjacency_from_links(entries, index), {"/v/a.md": set()})


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


class AdjacencyTests(unittest.TestCase):
    def test_drops_everything_but_neighbours(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]] [[ghost]]", "b.md": ""})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            graph = notes_cluster.build_graph(paths, notes_common.build_name_index(paths))
            neighbors = notes_cluster.adjacency(graph)
        self.assertEqual({Path(p).stem for p in neighbors}, {"a", "b"})
        self.assertTrue(all(isinstance(v, set) for v in neighbors.values()))


class ComponentsTests(unittest.TestCase):
    def test_splits_disconnected_groups(self):
        graph = undirected([("a", "b"), ("c", "d"), ("d", "e")])
        self.assertEqual(notes_cluster.components(graph), [["c", "d", "e"], ["a", "b"]])

    def test_isolated_nodes_are_their_own_component(self):
        graph = undirected([("a", "b")], isolated=["z"])
        self.assertEqual(notes_cluster.components(graph), [["a", "b"], ["z"]])

    def test_orders_largest_first_then_alphabetically(self):
        graph = undirected([("b", "c"), ("a", "z")])
        self.assertEqual(notes_cluster.components(graph), [["a", "z"], ["b", "c"]])

    def test_empty_graph_has_no_components(self):
        self.assertEqual(notes_cluster.components({}), [])


class ModularityTests(unittest.TestCase):
    def test_matches_hand_computed_value_for_two_triangles(self):
        # 7 edges, so 2m = 14. Each triangle: in = 6, tot = 7.
        # Q = 2 * (6/14 - (7/14)^2) = 5/14.
        labels = {"a": 0, "b": 0, "c": 0, "d": 1, "e": 1, "f": 1}
        self.assertAlmostEqual(notes_cluster.modularity(TWO_TRIANGLES, labels), 5 / 14)

    def test_one_community_over_a_connected_graph_scores_zero(self):
        labels = dict.fromkeys(TWO_TRIANGLES, 0)
        self.assertAlmostEqual(notes_cluster.modularity(TWO_TRIANGLES, labels), 0.0)

    def test_all_singletons_score_below_zero(self):
        labels = {node: i for i, node in enumerate(sorted(TWO_TRIANGLES))}
        self.assertLess(notes_cluster.modularity(TWO_TRIANGLES, labels), 0.0)

    def test_edgeless_graph_scores_zero(self):
        graph = undirected([], isolated=["a", "b"])
        self.assertEqual(notes_cluster.modularity(graph, {"a": 0, "b": 1}), 0.0)

    def test_empty_graph_scores_zero(self):
        self.assertEqual(notes_cluster.modularity({}, {}), 0.0)


class LouvainTests(unittest.TestCase):
    def test_recovers_two_triangles_joined_by_one_edge(self):
        labels = notes_cluster.louvain(TWO_TRIANGLES)
        self.assertEqual(
            grouping(labels), {frozenset("abc"), frozenset("def")}
        )

    def test_recovers_three_planted_cliques(self):
        edges = []
        for block in ("abcd", "efgh", "ijkl"):
            for i, left in enumerate(block):
                for right in block[i + 1 :]:
                    edges.append((left, right))
        edges += [("d", "e"), ("h", "i")]
        labels = notes_cluster.louvain(undirected(edges))
        self.assertEqual(
            grouping(labels),
            {frozenset("abcd"), frozenset("efgh"), frozenset("ijkl")},
        )

    def test_a_clique_is_one_community(self):
        edges = [(a, b) for a in "abcd" for b in "abcd" if a < b]
        self.assertEqual(len(set(notes_cluster.louvain(undirected(edges)).values())), 1)

    def test_isolated_notes_each_get_their_own_cluster(self):
        graph = undirected([("a", "b")], isolated=["y", "z"])
        labels = notes_cluster.louvain(graph)
        self.assertEqual(grouping(labels), {frozenset("ab"), frozenset("y"), frozenset("z")})

    def test_edgeless_vault_gives_every_note_its_own_cluster(self):
        graph = undirected([], isolated=["a", "b", "c"])
        self.assertEqual(len(set(notes_cluster.louvain(graph).values())), 3)

    def test_empty_vault(self):
        self.assertEqual(notes_cluster.louvain({}), {})

    def test_single_note(self):
        self.assertEqual(notes_cluster.louvain({"a": set()}), {"a": 0})

    def test_dangling_neighbour_outside_the_vault_is_ignored(self):
        # adjacency() can only name scanned notes, but louvain() must not blow up
        # if a caller hands it a neighbour set mentioning something it never saw.
        labels = notes_cluster.louvain({"a": {"b", "gone"}, "b": {"a"}})
        self.assertEqual(set(labels), {"a", "b"})

    def test_a_one_way_neighbour_map_is_treated_as_an_edge(self):
        # louvain() is public and takes a raw map; a caller that forgot to
        # symmetrise must not silently lose the edge.
        self.assertEqual(
            grouping(notes_cluster.louvain({"a": {"b"}, "b": set()})), {frozenset("ab")}
        )
        self.assertEqual(notes_cluster.shape({"a": {"b"}, "b": set()}, {"a": 0, "b": 0})["edges"], 0)

    def test_beats_the_all_in_one_partition_it_starts_from(self):
        labels = notes_cluster.louvain(TWO_TRIANGLES)
        self.assertGreater(notes_cluster.modularity(TWO_TRIANGLES, labels), 0.3)

    def test_cluster_ids_are_dense_and_start_at_zero(self):
        labels = notes_cluster.louvain(TWO_TRIANGLES)
        self.assertEqual(sorted(set(labels.values())), [0, 1])

    def test_lowest_cluster_id_holds_the_alphabetically_first_note(self):
        labels = notes_cluster.louvain(TWO_TRIANGLES)
        self.assertEqual(labels["a"], 0)


class DeterminismTests(unittest.TestCase):
    def test_repeated_runs_agree(self):
        first = notes_cluster.louvain(TWO_TRIANGLES)
        for _ in range(5):
            self.assertEqual(notes_cluster.louvain(TWO_TRIANGLES), first)

    def test_input_insertion_order_does_not_change_the_answer(self):
        forward = notes_cluster.louvain(TWO_TRIANGLES)
        reversed_input = {k: TWO_TRIANGLES[k] for k in reversed(sorted(TWO_TRIANGLES))}
        self.assertEqual(notes_cluster.louvain(reversed_input), forward)

    def test_renaming_nodes_without_reordering_them_preserves_the_partition(self):
        renamed = {
            node.upper(): {other.upper() for other in others}
            for node, others in TWO_TRIANGLES.items()
        }
        labels = notes_cluster.louvain(renamed)
        self.assertEqual(grouping(labels), {frozenset("ABC"), frozenset("DEF")})


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.labels = notes_cluster.louvain(TWO_TRIANGLES)
        self.summary = notes_cluster.shape(TWO_TRIANGLES, self.labels)

    def test_counts_notes_and_links(self):
        self.assertEqual(self.summary["notes"], 6)
        self.assertEqual(self.summary["edges"], 7)

    def test_reports_one_component_when_the_graph_is_connected(self):
        self.assertEqual(self.summary["components"], 1)
        self.assertEqual(self.summary["largest_component"], 6)
        self.assertEqual(self.summary["isolated"], 0)

    def test_reports_cluster_count_and_modularity(self):
        self.assertEqual(self.summary["clusters"], 2)
        self.assertEqual(self.summary["largest_cluster"], 3)
        self.assertAlmostEqual(self.summary["modularity"], round(5 / 14, 4))

    def test_counts_isolated_notes_separately_from_components(self):
        graph = undirected([("a", "b")], isolated=["y", "z"])
        summary = notes_cluster.shape(graph, notes_cluster.louvain(graph))
        self.assertEqual(summary["components"], 3)
        self.assertEqual(summary["isolated"], 2)

    def test_empty_vault_reports_zeroes_rather_than_failing(self):
        summary = notes_cluster.shape({}, {})
        self.assertEqual(summary["notes"], 0)
        self.assertEqual(summary["largest_component"], 0)
        self.assertEqual(summary["largest_cluster"], 0)

    def test_describe_shape_names_every_number_it_was_given(self):
        line = notes_cluster.describe_shape(self.summary)
        self.assertIn("6 notes", line)
        self.assertIn("7 links", line)
        self.assertIn("1 components", line)
        self.assertIn("2 clusters", line)
        self.assertIn("0.357", line)


class DevVaultFixtureTests(unittest.TestCase):
    """The fixture contract: dev-vault must keep exercising what it was grown for."""

    @classmethod
    def setUpClass(cls):
        paths = list(notes_common.iter_markdown_files(str(DEV_VAULT), []))
        entries = [
            {"path": p, "links": notes_common.extract_links(Path(p).read_text())} for p in paths
        ]
        index = notes_common.build_name_index(paths)
        cls.neighbors = notes_cluster.adjacency_from_links(entries, index)
        cls.labels = notes_cluster.louvain(cls.neighbors)
        cls.by_name = {Path(p).stem: p for p in paths}

    def cluster_of(self, name):
        return self.labels[self.by_name[name]]

    def test_has_a_disconnected_three_note_component(self):
        sizes = [len(g) for g in notes_cluster.components(self.neighbors)]
        self.assertIn(3, sizes)

    def test_has_a_single_note_orphan_component(self):
        groups = notes_cluster.components(self.neighbors)
        singles = [g[0] for g in groups if len(g) == 1]
        self.assertEqual([Path(p).stem for p in singles], ["orphan-note"])

    def test_finds_at_least_four_clusters(self):
        # Three link communities, plus the island, plus the orphan.
        self.assertGreaterEqual(len(set(self.labels.values())), 4)

    def test_each_community_is_cohesive_and_separate_from_the_others(self):
        # Cohesion is the half that matters: "three distinct ids" alone would also
        # hold if clustering degenerated to one singleton per note.
        planning = {self.cluster_of(n) for n in ("hub-note", "project-plan", "meeting-notes", "reading-list")}
        gardening = {self.cluster_of(f"cluster-b-{n}") for n in ("hub", "one", "two", "three")}
        harbour = {self.cluster_of(f"hubless-{n}") for n in HARBOUR_RING}
        for community in (planning, gardening, harbour):
            self.assertEqual(len(community), 1)
        self.assertEqual(len({planning.pop(), gardening.pop(), harbour.pop()}), 3)

    def test_the_island_is_its_own_cluster_apart_from_the_rest(self):
        island = {self.cluster_of(n) for n in ("island-one", "island-two", "island-three")}
        self.assertEqual(len(island), 1)
        self.assertNotIn(self.cluster_of("hub-note"), island)

    def test_hubless_ring_members_cluster_together(self):
        self.assertEqual(len({self.cluster_of(f"hubless-{n}") for n in HARBOUR_RING}), 1)

    def test_the_harbour_ring_is_the_only_cluster_with_no_entry_point(self):
        # The fixture's reason for being eight notes: below about six, any cluster
        # cohesive enough for Louvain to keep whole is small enough that some note
        # covers half of it, so there is nothing to report.
        entries = notes_cluster.cluster_entry_points(self.neighbors, self.labels)
        hubless = [e for e in entries if e["coverage"] < 0.5]
        self.assertEqual(len(hubless), 1)
        self.assertEqual(hubless[0]["size"], len(HARBOUR_RING))
        self.assertEqual(Path(hubless[0]["entry_point"]).stem, "hubless-eight")
        self.assertEqual(hubless[0]["reach"], 2)

    def test_every_other_cluster_has_a_full_entry_point(self):
        for entry in notes_cluster.cluster_entry_points(self.neighbors, self.labels):
            if entry["size"] != len(HARBOUR_RING):
                self.assertEqual(entry["coverage"], 1.0, Path(entry["entry_point"]).stem)

    def test_modularity_is_high_enough_to_be_worth_clustering(self):
        self.assertGreater(notes_cluster.modularity(self.neighbors, self.labels), 0.5)


if __name__ == "__main__":
    unittest.main()
