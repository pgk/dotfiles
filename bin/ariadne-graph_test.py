#!/usr/bin/env python3

"""Tests for bin/ariadne-graph, run against synthetic notes only (never ~/notes)."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("ariadne-graph")

loader = importlib.machinery.SourceFileLoader("ariadne_graph", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("ariadne_graph", loader)
ariadne_graph = importlib.util.module_from_spec(spec)
loader.exec_module(ariadne_graph)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_cluster
import ariadne_common


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class GraphBuildingTests(unittest.TestCase):
    def build(self, files, min_links=3, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(ariadne_common.iter_markdown_files(tmp, excludes or []))
            index = ariadne_common.build_name_index(paths)
            graph = ariadne_cluster.build_graph(paths, index)
            orphans, sparse = ariadne_graph.classify(graph, min_links)
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


class FormatTextTests(unittest.TestCase):
    def test_report_includes_broken_links_and_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"sub/a.md": "see [[ghost]]"})
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            index = ariadne_common.build_name_index(paths)
            graph = ariadne_cluster.build_graph(paths, index)
            orphans, sparse = ariadne_graph.classify(graph, 3)
            text = ariadne_graph.format_text(orphans, sparse, 3, len(paths), tmp)

        self.assertIn("Orphans (1)", text)
        self.assertIn("sub/a.md", text)
        self.assertIn("(broken: [[ghost]])", text)
        self.assertNotIn("Sparse", text)

    def test_report_omits_empty_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "no links back"})
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            index = ariadne_common.build_name_index(paths)
            graph = ariadne_cluster.build_graph(paths, index)
            orphans, sparse = ariadne_graph.classify(graph, 2)
            text = ariadne_graph.format_text(orphans, sparse, 2, len(paths), tmp)

        self.assertNotIn("Orphans", text)
        self.assertIn("Sparse", text)

    def test_splittable_section_shows_sections_as_split_points(self):
        entries = [
            {"name": "sprawl", "path": "/v/sprawl.md", "rel": "sprawl.md",
             "words": 1500, "headers": ["Background", "Approach"], "out_degree": 1},
        ]
        text = ariadne_graph.format_text([], [], 3, 1, "/v", splittable=entries)
        self.assertIn("Splittable (1)", text)
        self.assertIn("sprawl", text)
        self.assertIn("1500 words", text)
        self.assertIn("sections: Background / Approach", text)

    def test_all_clear_requires_no_splittable_notes_either(self):
        entries = [
            {"name": "sprawl", "path": "/v/sprawl.md", "rel": "sprawl.md",
             "words": 1500, "headers": [], "out_degree": 0},
        ]
        text = ariadne_graph.format_text([], [], 3, 1, "/v", splittable=entries)
        self.assertNotIn("All 1 notes", text)


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
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            index = ariadne_common.build_name_index(paths)
            graph = ariadne_cluster.build_graph(paths, index)
            orphans, sparse = ariadne_graph.classify(graph, 3)
            payload = json.loads(ariadne_graph.format_json(orphans, sparse, 3, len(paths), tmp))

        self.assertEqual(payload["vault"], tmp)
        self.assertEqual(payload["min_links"], 3)
        self.assertEqual(payload["total_notes"], 5)
        self.assertEqual({e["name"] for e in payload["orphans"]}, {"lonely"})
        self.assertEqual({e["name"] for e in payload["sparse"]}, {"a", "b", "c"})
        for entry in payload["orphans"] + payload["sparse"]:
            self.assertEqual(set(entry), {"name", "path", "degree", "broken_links"})

    def test_json_includes_splittable_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "short"})
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            payload = json.loads(ariadne_graph.format_json([], [], 3, len(paths), tmp, splittable=[]))
        self.assertEqual(payload["splittable"], [])


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

    def test_cli_splittable_thresholds_are_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"sprawl.md": "## A\ntext\n## B\ntext\n## C\ntext\n"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--json", "--min-headers", "3", "--min-words", "9999"],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
        self.assertEqual({e["name"] for e in payload["splittable"]}, {"sprawl"})

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
