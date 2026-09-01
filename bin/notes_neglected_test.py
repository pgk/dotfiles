#!/usr/bin/env python3

"""Tests for notes-graph --neglected, the resurface-by-neglect report.

Run against synthetic notes only (never ~/notes). Modification times are set with
os.utime so nothing depends on how long the test took to run.
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
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
import notes_neglected

DAY = 86400


def write_vault(root, files, ages=None):
    """`ages` maps a relative path to how many days ago it was last modified."""
    now = time.time()
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        age = (ages or {}).get(relpath, 0)
        os.utime(path, (now - age * DAY, now - age * DAY))


def select(root, cutoff_days, min_links=3, limit=None):
    """The selection notes-graph performs, against the vault at `root`."""
    now = time.time()
    files = list(notes_common.iter_markdown_files(root, []))
    graph = notes_cluster.build_graph(files, notes_common.build_name_index(files))
    stale = notes_neglected.untouched_before(files, now - cutoff_days * DAY)
    return notes_neglected.select(graph, stale, min_links, limit, root, now)


def links_to(*names):
    return "Body text. " + " ".join(f"[[{n}]]" for n in names)


class SelectionTest(unittest.TestCase):
    def test_a_well_connected_old_note_is_selected(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(
                root,
                {
                    "gem.md": links_to("a", "b", "c"),
                    "a.md": links_to("gem"),
                    "b.md": links_to("gem"),
                    "c.md": links_to("gem"),
                },
                ages={"gem.md": 400},
            )
            entries, considered = select(root, 180)
            self.assertEqual([e["name"] for e in entries], ["gem"])
            self.assertEqual(considered, 1)
            self.assertEqual(entries[0]["degree"], 3)

    def test_a_sparse_old_note_is_not_selected(self):
        """Degree below --min-links is the whole point of the filter: an abandoned
        stub is neglected too, and resurfacing it is exactly what this must not do."""
        with tempfile.TemporaryDirectory() as root:
            write_vault(
                root,
                {"stub.md": links_to("a"), "a.md": "No links here."},
                ages={"stub.md": 400, "a.md": 400},
            )
            entries, considered = select(root, 180)
            self.assertEqual(entries, [])
            self.assertEqual(considered, 0)

    def test_an_orphan_is_not_selected(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"orphan.md": "Alone."}, ages={"orphan.md": 900})
            entries, _ = select(root, 180)
            self.assertEqual(entries, [])

    def test_a_recently_touched_note_is_not_selected(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(
                root,
                {
                    "fresh.md": links_to("a", "b", "c"),
                    "a.md": links_to("fresh"),
                    "b.md": links_to("fresh"),
                    "c.md": links_to("fresh"),
                },
                ages={"fresh.md": 3},
            )
            entries, _ = select(root, 180)
            self.assertNotIn("fresh", [e["name"] for e in entries])

    def test_the_cutoff_boundary_is_inclusive(self):
        """The cutoff is fed the file's own mtime, so equality is forced. Deriving
        it from time.time() twice put the mtime strictly below the cutoff and left
        the boundary untested."""
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"edge.md": "Body."}, ages={"edge.md": 180})
            path = str(Path(root) / "edge.md")
            exact = os.path.getmtime(path)
            self.assertIn(path, notes_neglected.untouched_before([path], exact))
            self.assertNotIn(path, notes_neglected.untouched_before([path], exact - 1))


class RankingTest(unittest.TestCase):
    def test_more_connected_notes_rank_first(self):
        """Degree leads, not age: the filter already established that every
        candidate is neglected."""
        with tempfile.TemporaryDirectory() as root:
            write_vault(
                root,
                {
                    "big.md": links_to("a", "b", "c", "d"),
                    "small.md": links_to("a", "b", "c"),
                    "a.md": links_to("big", "small"),
                    "b.md": links_to("big", "small"),
                    "c.md": links_to("big", "small"),
                    "d.md": links_to("big"),
                },
                ages={"big.md": 200, "small.md": 900},
            )
            entries, _ = select(root, 180)
            self.assertEqual([e["name"] for e in entries][:2], ["big", "small"])

    def test_equal_degree_puts_the_oldest_first(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(
                root,
                {
                    "newer.md": links_to("a", "b", "c"),
                    "older.md": links_to("a", "b", "c"),
                    "a.md": links_to("newer", "older"),
                    "b.md": links_to("newer", "older"),
                    "c.md": links_to("newer", "older"),
                },
                ages={"newer.md": 200, "older.md": 900},
            )
            entries, _ = select(root, 180)
            names = [e["name"] for e in entries]
            self.assertLess(names.index("older"), names.index("newer"))

    def test_limit_truncates_but_considered_still_counts_everything(self):
        """A ranking limit hides what the sort demoted, so the candidate count is
        reported separately from the rows that survived it."""
        with tempfile.TemporaryDirectory() as root:
            files = {"hub.md": links_to(*[f"n{i}" for i in range(6)])}
            for i in range(6):
                files[f"n{i}.md"] = links_to("hub", *[f"n{j}" for j in range(6) if j != i])
            write_vault(root, files, ages={name: 400 for name in files})
            entries, considered = select(root, 180, limit=2)
            self.assertEqual(len(entries), 2)
            self.assertEqual(considered, 7)


class AgeDescriptionTest(unittest.TestCase):
    def test_spans_read_in_the_largest_useful_unit(self):
        describe = notes_neglected.describe_span
        self.assertEqual(describe(10 * DAY), "10 days")
        self.assertEqual(describe(1 * DAY), "1 day")
        self.assertEqual(describe(90 * DAY), "3 months")
        self.assertEqual(describe(30 * DAY), "1 month")
        self.assertEqual(describe(800 * DAY), "2 years")
        self.assertEqual(describe(365 * DAY), "1 year")

    def test_spans_below_a_day_are_not_reported_as_zero_days(self):
        """--neglected advertises hours in its help, so the formatter has to reach
        below days or a 1h window prints "untouched 0 days"."""
        describe = notes_neglected.describe_span
        self.assertEqual(describe(90 * 60), "1 hour")
        self.assertEqual(describe(5 * 3600), "5 hours")
        self.assertEqual(describe(60), "1 minute")
        self.assertEqual(describe(300), "5 minutes")


class CliTest(unittest.TestCase):
    def run_cli(self, root, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(root), *args],
            capture_output=True, text=True,
        )

    def build(self, root):
        write_vault(
            root,
            {
                "gem.md": links_to("a", "b", "c"),
                "a.md": links_to("gem"),
                "b.md": links_to("gem"),
                "c.md": links_to("gem"),
            },
            ages={"gem.md": 400},
        )

    def test_json_reports_the_candidates_and_the_window(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            result = self.run_cli(root, "--neglected", "180d", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["window"], "180d")
            self.assertEqual(payload["considered"], 1)
            self.assertEqual([n["name"] for n in payload["neglected"]], ["gem"])
            self.assertEqual(payload["neglected"][0]["degree"], 3)

    def test_json_omits_cluster_shape_because_no_clusters_were_computed(self):
        """This view ranks on degree and mtime alone. Every cluster-derived view
        prints the graph shape as its own caveat; there is nothing here to caveat,
        and running Louvain would cost seconds for an unused number."""
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            payload = json.loads(self.run_cli(root, "--neglected", "180d", "--json").stdout)
            self.assertNotIn("shape", payload)

    def test_the_text_report_states_the_mtime_assumption(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            result = self.run_cli(root, "--neglected", "180d")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("gem", result.stdout)
            self.assertIn("mtime", result.stdout.lower())

    def test_an_empty_result_says_so(self):
        with tempfile.TemporaryDirectory() as root:
            write_vault(root, {"fresh.md": links_to("a"), "a.md": links_to("fresh")})
            result = self.run_cli(root, "--neglected", "180d")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Nothing", result.stdout)

    def build_many(self, root):
        """Seven mutually-linked notes, all stale: six of degree 6, the hub of 6."""
        files = {"hub.md": links_to(*[f"n{i}" for i in range(6)])}
        for i in range(6):
            files[f"n{i}.md"] = links_to("hub", *[f"n{j}" for j in range(6) if j != i])
        write_vault(root, files, ages={name: 400 for name in files})

    def test_limit_reaches_the_report(self):
        with tempfile.TemporaryDirectory() as root:
            self.build_many(root)
            payload = json.loads(
                self.run_cli(root, "--neglected", "180d", "--limit", "2", "--json").stdout
            )
            self.assertEqual(len(payload["neglected"]), 2)
            self.assertEqual(payload["considered"], 7)

    def test_limit_zero_means_every_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            self.build_many(root)
            payload = json.loads(
                self.run_cli(root, "--neglected", "180d", "--limit", "0", "--json").stdout
            )
            self.assertEqual(len(payload["neglected"]), 7)

    def test_min_links_reaches_the_filter(self):
        with tempfile.TemporaryDirectory() as root:
            self.build_many(root)
            payload = json.loads(
                self.run_cli(root, "--neglected", "180d", "--min-links", "7", "--json").stdout
            )
            self.assertEqual(payload["considered"], 0)

    def test_a_negative_limit_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            result = self.run_cli(root, "--neglected", "180d", "--limit", "-3")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--limit", result.stderr)

    def test_an_empty_duration_does_not_fall_through_to_the_health_report(self):
        """Truthiness testing let --neglected "" skip parse_duration entirely and
        print the orphan/sparse report, answering a question nobody asked."""
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            result = self.run_cli(root, "--neglected", "")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--neglected", result.stderr)
            self.assertNotIn("Orphans", result.stdout)

    def test_since_and_neglected_together_are_refused(self):
        """Opposite reports over the same field; letting one silently win would
        answer a question the caller did not ask."""
        with tempfile.TemporaryDirectory() as root:
            self.build(root)
            result = self.run_cli(root, "--neglected", "180d", "--since", "7d")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--neglected", result.stderr)

    def test_a_bad_duration_fails_before_the_vault_is_read(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "/no/such/vault", "--neglected", "180"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--neglected", result.stderr)
        self.assertNotIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
