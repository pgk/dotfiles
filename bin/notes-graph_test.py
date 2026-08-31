#!/usr/bin/env python3

"""Tests for bin/notes-graph, run against synthetic notes only (never ~/notes)."""

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


class GraphBuildingTests(unittest.TestCase):
    def build(self, files, min_links=3, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(notes_common.iter_markdown_files(tmp, excludes or []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            orphans, sparse = notes_graph.classify(graph, min_links)
            return graph, orphans, sparse

    def test_hub_note_has_correct_degree(self):
        graph, orphans, sparse = self.build(
            {
                "hub.md": "links to [[a]], [[b]], and [[c]]",
                "a.md": "back to [[hub]]",
                "b.md": "back to [[hub]]",
                "c.md": "back to [[hub]]",
            },
            min_links=3,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 3)
        names = {e["name"] for e in orphans + sparse}
        self.assertNotIn("hub", names)

    def test_note_with_no_links_is_orphan(self):
        _, orphans, _ = self.build(
            {
                "lonely.md": "no links here at all",
                "hub.md": "[[lonely2]]",
                "lonely2.md": "[[hub]]",
            },
            min_links=3,
        )
        orphan_names = {e["name"] for e in orphans}
        self.assertIn("lonely", orphan_names)
        self.assertNotIn("lonely2", orphan_names)

    def test_single_connection_is_sparse_under_default_threshold(self):
        _, _, sparse = self.build(
            {
                "hub.md": "[[a]] [[b]] [[c]]",
                "a.md": "[[hub]]",
                "b.md": "[[hub]]",
                "c.md": "[[hub]]",
            },
            min_links=3,
        )
        sparse_names = {e["name"]: e["degree"] for e in sparse}
        self.assertEqual(sparse_names.get("a"), 1)
        self.assertEqual(sparse_names.get("b"), 1)
        self.assertEqual(sparse_names.get("c"), 1)

    def test_broken_link_reported_and_not_counted(self):
        _, orphans, _ = self.build(
            {
                "a.md": "see [[ghost]]",
            },
            min_links=1,
        )
        entry = orphans[0]
        self.assertEqual(entry["name"], "a")
        self.assertEqual(entry["degree"], 0)
        self.assertEqual(entry["broken_links"], ["ghost"])

    def test_min_links_shifts_sparse_boundary(self):
        files = {
            "hub.md": "[[a]] [[b]]",
            "a.md": "[[hub]]",
            "b.md": "[[hub]]",
        }
        _, _, sparse_default = self.build(files, min_links=2)
        _, _, sparse_low = self.build(files, min_links=1)
        self.assertTrue(any(e["name"] == "a" for e in sparse_default))
        self.assertFalse(any(e["name"] == "a" for e in sparse_low))

    def test_self_link_is_not_a_connection(self):
        graph, orphans, _ = self.build(
            {
                "a.md": "see [[a]] again",
            },
            min_links=1,
        )
        a_path = next(p for p in graph)
        self.assertEqual(len(graph[a_path]["neighbors"]), 0)
        self.assertEqual([e["name"] for e in orphans], ["a"])


def ring_beside_a_clique(ring_n=6, clique_n=4):
    """A ring, plus a dense cluster it hangs off by one link.

    The clique is not decoration. A ring on its own is not cohesive enough for
    Louvain to keep whole -- it splits into arcs, each small enough to have an
    entry point. It survives as one community only when there is a denser
    neighbour for the arcs to lose against, which is also the only situation in
    which a hubless cluster is a real finding.
    """
    ring = [f"r{i:02}" for i in range(ring_n)]
    clique = [f"c{i:02}" for i in range(clique_n)]
    files = {f"{nm}.md": f"[[{ring[(i + 1) % ring_n]}]]" for i, nm in enumerate(ring)}
    files[f"{ring[0]}.md"] += f" [[{clique[0]}]]"
    for nm in clique:
        files[f"{nm}.md"] = " ".join(f"[[{other}]]" for other in clique if other != nm)
    return files


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
        self.assertTrue(all(e["name"].startswith("r") for e in hubless))

    def test_a_map_of_content_cluster_is_not_reported(self):
        files = {"moc.md": " ".join(f"[[n{i}]]" for i in range(6))}
        files.update({f"n{i}.md": "[[moc]]" for i in range(6)})
        self.assertEqual(self.build(files), [])

    def test_small_clusters_are_never_reported(self):
        # A three-note cluster needs no map of content, and coverage says so
        # without a separate size threshold to pick.
        self.assertEqual(self.build({"a.md": "[[b]]", "b.md": "[[c]]", "c.md": "[[a]]"}), [])

    def test_an_orphan_is_not_reported_as_a_hubless_cluster(self):
        self.assertEqual(self.build({"lonely.md": "no links"}), [])

    def test_raising_hub_reach_reports_more_clusters(self):
        files = {"a.md": "[[b]] [[c]]", "b.md": "[[c]]", "c.md": ""}
        self.assertEqual(self.build(files, hub_reach=0.5), [])
        self.assertEqual(len(self.build(files, hub_reach=1.01)), 1)

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
        shape = {"notes": 8, "edges": 8, "components": 1, "largest_component": 8,
                 "isolated": 0, "clusters": 1, "largest_cluster": 8, "modularity": 0.4}
        out = notes_graph.format_text([], [], 3, 8, "/v", [self.ENTRY], shape)
        self.assertIn("8 notes", out)
        self.assertIn("Clusters without a hub (1)", out)

    def test_all_clear_message_mentions_hubs_too(self):
        out = notes_graph.format_text([], [], 3, 5, "/v")
        self.assertIn("every cluster has a hub", out)

    def test_hubless_clusters_alone_still_produce_a_report(self):
        out = notes_graph.format_text([], [], 3, 8, "/v", [self.ENTRY])
        self.assertIn("Clusters without a hub", out)
        self.assertNotIn("Orphans", out)


class FormatTextTests(unittest.TestCase):
    def test_report_includes_broken_links_and_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"sub/a.md": "see [[ghost]]"})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            orphans, sparse = notes_graph.classify(graph, 3)
            text = notes_graph.format_text(orphans, sparse, 3, len(paths), tmp)

        self.assertIn("Orphans (1)", text)
        self.assertIn("sub/a.md", text)
        self.assertIn("(broken: [[ghost]])", text)
        self.assertNotIn("Sparse", text)

    def test_report_omits_empty_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "no links back"})
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            orphans, sparse = notes_graph.classify(graph, 2)
            text = notes_graph.format_text(orphans, sparse, 2, len(paths), tmp)

        self.assertNotIn("Orphans", text)
        self.assertIn("Sparse", text)


class JsonOutputTests(unittest.TestCase):
    def test_json_shape_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "hub.md": "[[a]] [[b]] [[c]]",
                    "a.md": "[[hub]]",
                    "b.md": "[[hub]]",
                    "c.md": "[[hub]]",
                    "lonely.md": "no links",
                },
            )
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            graph = notes_cluster.build_graph(paths, index)
            orphans, sparse = notes_graph.classify(graph, 3)
            payload = json.loads(notes_graph.format_json(orphans, sparse, 3, len(paths), tmp))

        self.assertEqual(payload["vault"], tmp)
        self.assertEqual(payload["min_links"], 3)
        self.assertEqual(payload["total_notes"], 5)
        self.assertEqual({e["name"] for e in payload["orphans"]}, {"lonely"})
        self.assertEqual({e["name"] for e in payload["sparse"]}, {"a", "b", "c"})
        for entry in payload["orphans"] + payload["sparse"]:
            self.assertEqual(set(entry), {"name", "path", "degree", "broken_links"})


class CliSubprocessTests(unittest.TestCase):
    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "hub.md": "content",
                    "lonely.md": "no links",
                },
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--json", "-m", "1"],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["total_notes"], 2)
            self.assertEqual({e["name"] for e in payload["orphans"]}, {"hub", "lonely"})

    def test_cli_text_output_all_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "a.md": "[[b]]",
                    "b.md": "[[a]]",
                },
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "-m", "1"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(f"All 2 notes in {os.path.abspath(tmp)} have at least 1 connection", result.stdout)

    def test_cli_repeatable_exclude_does_not_swallow_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "hub.md": "[[templates/skip-me]]",
                    "templates/skip-me.md": "content",
                },
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--exclude", "templates/*", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["total_notes"], 1)

    def test_cli_json_carries_shape_and_hubless_clusters(self):
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

    def test_cli_rejects_a_hub_reach_outside_zero_to_one(self):
        for bad in ("0", "-0.5", "1.5"):
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "/tmp", "--hub-reach", bad],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, bad)
            self.assertIn("--hub-reach", result.stderr)

    def test_cli_rejects_nonexistent_vault(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "/no/such/vault/path"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a directory", result.stderr)

    def test_cli_repeatable_exclude_leaves_vault_positional_intact(self):
        # Regression guard: --exclude must not be able to swallow the vault
        # positional, leaving the tool to run against some other vault.
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--exclude", "templates/*", "/no/such/vault", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/no/such/vault", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_exclude_alone_is_refused_rather_than_falling_back(self):
        # `--exclude PATH` with nothing else is genuinely ambiguous at the
        # argparse layer: PATH can be read as the glob, leaving no vault. That
        # is unfixable in argparse, so the fix was to delete the ~/notes
        # default instead — the ambiguity now costs an error message rather
        # than a scan of the real vault. $HOME is faked as a second net: if
        # this ever regresses, the canary is what gets read, not ~/notes.
        with tempfile.TemporaryDirectory() as fake_home:
            write_vault(fake_home, {"notes/canary.md": "canary"})
            env = {**os.environ, "HOME": fake_home}
            env.pop("NOTES_VAULT", None)

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--exclude", os.path.join(fake_home, "notes"), "--json"],
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VAULT path is required", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("canary", result.stdout + result.stderr)

    def test_bare_invocation_names_no_vault(self):
        env = {**os.environ}
        env.pop("NOTES_VAULT", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VAULT path is required", result.stderr)

    def test_vault_can_come_from_notes_vault_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "[[a]]"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--json"],
                capture_output=True,
                text=True,
                env={**os.environ, "NOTES_VAULT": tmp},
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["vault"], tmp)
            self.assertEqual(payload["total_notes"], 2)


if __name__ == "__main__":
    unittest.main()
