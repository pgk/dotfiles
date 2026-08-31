#!/usr/bin/env python3

"""Tests for bin/notes-graph, run against synthetic notes only (never ~/notes)."""

import contextlib
import importlib.machinery
import importlib.util
import io
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


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class GraphBuildingTests(unittest.TestCase):
    def build(self, files, min_links=3, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(notes_graph.iter_markdown_files(tmp, excludes or []))
            index = notes_graph.build_name_index(paths)
            graph = notes_graph.build_graph(paths, index)
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

    def test_alias_resolves_by_link_target_not_display_text(self):
        graph, _, _ = self.build(
            {
                "hub.md": "content",
                "a.md": "see [[hub|the hub note]]",
            },
            min_links=1,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 1)

    def test_case_insensitive_resolution(self):
        graph, _, _ = self.build(
            {
                "hub.md": "content",
                "a.md": "see [[HUB]]",
            },
            min_links=1,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 1)

    def test_transclusion_counts_as_connection(self):
        graph, _, _ = self.build(
            {
                "hub.md": "content",
                "embed.md": "![[hub]]",
            },
            min_links=1,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 1)

    def test_heading_fragment_is_stripped_before_resolving(self):
        graph, _, _ = self.build(
            {
                "hub.md": "# Some Heading\ncontent",
                "a.md": "see [[hub#Some Heading]]",
            },
            min_links=1,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 1)

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

    def test_exclude_removes_matching_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "hub.md": "[[templates/skip-me]]",
                    "templates/skip-me.md": "content",
                },
            )
            paths = list(notes_graph.iter_markdown_files(tmp, ["templates/*"]))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"hub.md"})

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

    def test_dotted_note_name_resolves(self):
        graph, orphans, _ = self.build(
            {
                "node.js.md": "a note about node.js",
                "a.md": "see [[node.js]]",
            },
            min_links=1,
        )
        target_path = next(p for p in graph if p.endswith("node.js.md"))
        self.assertEqual(len(graph[target_path]["neighbors"]), 1)
        self.assertEqual(orphans, [])

    def test_folder_prefixed_link_resolves_by_basename(self):
        graph, _, _ = self.build(
            {
                "sub/hub.md": "content",
                "a.md": "see [[sub/hub]]",
            },
            min_links=1,
        )
        hub_path = next(p for p in graph if p.endswith("hub.md"))
        self.assertEqual(len(graph[hub_path]["neighbors"]), 1)

    def test_duplicate_stem_keeps_first_and_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "a/dup.md": "first",
                    "b/dup.md": "second",
                },
            )
            # iter_markdown_files sorts its own traversal, so "a/dup.md" is
            # deterministically first without the test re-sorting it.
            paths = list(notes_graph.iter_markdown_files(tmp, []))
            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                index = notes_graph.build_name_index(paths)
            self.assertEqual(index["dup"], paths[0])
            self.assertIn("duplicate note name 'dup'", captured.getvalue())

    def test_symlinked_file_outside_vault_is_skipped(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as vault:
            secret = Path(outside) / "secret.md"
            secret.write_text("outside content")
            (Path(vault) / "innocent.md").symlink_to(secret)
            paths = list(notes_graph.iter_markdown_files(vault, []))
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
            paths = list(notes_graph.iter_markdown_files(tmp, []))
            names = {Path(p).name for p in paths}
            self.assertEqual(names, {"note.md"})


class FormatTextTests(unittest.TestCase):
    def test_report_includes_broken_links_and_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"sub/a.md": "see [[ghost]]"})
            paths = list(notes_graph.iter_markdown_files(tmp, []))
            index = notes_graph.build_name_index(paths)
            graph = notes_graph.build_graph(paths, index)
            orphans, sparse = notes_graph.classify(graph, 3)
            text = notes_graph.format_text(orphans, sparse, 3, len(paths), tmp)

        self.assertIn("Orphans (1)", text)
        self.assertIn("sub/a.md", text)
        self.assertIn("(broken: [[ghost]])", text)
        self.assertNotIn("Sparse", text)

    def test_report_omits_empty_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "no links back"})
            paths = list(notes_graph.iter_markdown_files(tmp, []))
            index = notes_graph.build_name_index(paths)
            graph = notes_graph.build_graph(paths, index)
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
            paths = list(notes_graph.iter_markdown_files(tmp, []))
            index = notes_graph.build_name_index(paths)
            graph = notes_graph.build_graph(paths, index)
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
        # positional and silently fall back to the ~/notes default.
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--exclude", "templates/*", "/no/such/vault", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/no/such/vault", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_exclude_alone_falls_back_but_vault_field_reveals_it(self):
        # `--exclude PATH` with nothing else is genuinely ambiguous at the
        # argparse layer (PATH could be the glob, with no vault given) and
        # does fall back to the default vault. This cannot be fixed in
        # argparse, so this test locks in its two safety nets instead:
        # (1) $HOME is faked, so even a real fallback never touches the
        #     user's actual ~/notes, and (2) the "vault" field in the JSON
        #     output makes the fallback detectable rather than silent.
        with tempfile.TemporaryDirectory() as fake_home:
            write_vault(fake_home, {"notes/canary.md": "canary"})
            intended_vault = os.path.join(fake_home, "not-the-notes-dir")
            os.makedirs(intended_vault)
            env = {**os.environ, "HOME": fake_home}

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--exclude", intended_vault, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertNotEqual(payload["vault"], os.path.abspath(intended_vault))
        self.assertEqual(payload["vault"], os.path.join(fake_home, "notes"))


if __name__ == "__main__":
    unittest.main()
