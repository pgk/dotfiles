#!/usr/bin/env python3

"""Tests for ariadne-graph --since, the recent-activity report.

Run against synthetic notes only (never ~/notes). Modification times are set with
os.utime so nothing depends on how long the test took to run.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
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


class ParseDurationTests(unittest.TestCase):
    def test_understands_hours_days_and_weeks(self):
        self.assertEqual(ariadne_graph.parse_duration("36h"), 36 * 3600)
        self.assertEqual(ariadne_graph.parse_duration("7d"), 7 * DAY)
        self.assertEqual(ariadne_graph.parse_duration("2w"), 14 * DAY)

    def test_accepts_a_fraction_and_ignores_case_and_spacing(self):
        self.assertEqual(ariadne_graph.parse_duration("  1.5D "), 1.5 * DAY)

    def test_rejects_a_bare_number(self):
        with self.assertRaises(ValueError) as ctx:
            ariadne_graph.parse_duration("7")
        self.assertIn("7d", str(ctx.exception))

    def test_rejects_an_unknown_unit_and_nonsense(self):
        for bad in ("7x", "abc", "", "d"):
            with self.assertRaises(ValueError):
                ariadne_graph.parse_duration(bad)

    def test_rejects_zero_and_negative_windows(self):
        for bad in ("0d", "-3d"):
            with self.assertRaises(ValueError) as ctx:
                ariadne_graph.parse_duration(bad)
            self.assertIn("positive", str(ctx.exception))

    def test_the_error_strips_control_characters(self):
        with self.assertRaises(ValueError) as ctx:
            ariadne_graph.parse_duration("ev\x1b[31mil")
        self.assertNotIn("\x1b", str(ctx.exception))


class DescribeAgeTests(unittest.TestCase):
    def test_scales_from_minutes_to_days(self):
        self.assertEqual(ariadne_graph.describe_age(0), "0m")
        self.assertEqual(ariadne_graph.describe_age(90 * 60), "1h")
        self.assertEqual(ariadne_graph.describe_age(3 * DAY + 3600), "3d")

    def test_a_negative_age_from_a_future_mtime_does_not_go_negative(self):
        self.assertEqual(ariadne_graph.describe_age(-60), "0m")


class TouchedSinceTests(unittest.TestCase):
    def test_keeps_only_notes_modified_after_the_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"new.md": "", "old.md": ""}, ages={"old.md": 30})
            files = list(ariadne_common.iter_markdown_files(tmp, []))
            recent = ariadne_graph.touched_since(files, time.time() - 7 * DAY)
        self.assertEqual({Path(p).name for p in recent}, {"new.md"})

    def test_an_unreadable_note_warns_rather_than_failing_the_run(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            recent = ariadne_graph.touched_since(["/no/such/note.md"], 0)
        self.assertEqual(recent, {})
        self.assertIn("cannot stat", stderr.getvalue())


class ActivityTests(unittest.TestCase):
    def report(self, files, ages, window_days=7):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files, ages)
            paths = list(ariadne_common.iter_markdown_files(tmp, []))
            graph = ariadne_cluster.build_graph(paths, ariadne_common.build_name_index(paths))
            labels = ariadne_cluster.louvain(ariadne_cluster.adjacency(graph))
            now = time.time()
            recent = ariadne_graph.touched_since(paths, now - window_days * DAY)
            return ariadne_graph.activity(graph, labels, recent, tmp, now)

    def test_touched_notes_are_grouped_by_cluster(self):
        files = {"a.md": "[[b]] [[c]]", "b.md": "[[c]]", "c.md": "", "z.md": "[[y]]", "y.md": ""}
        clusters, orphaned = self.report(files, ages={"c.md": 30, "y.md": 30})
        self.assertEqual(orphaned, [])
        self.assertEqual([c["touched"] for c in clusters], [2, 1])
        self.assertEqual({e["name"] for e in clusters[0]["notes"]}, {"a", "b"})

    def test_a_cluster_reports_its_whole_size_not_just_the_touched_part(self):
        files = {"a.md": "[[b]] [[c]]", "b.md": "[[c]]", "c.md": ""}
        clusters, _ = self.report(files, ages={"b.md": 30, "c.md": 30})
        self.assertEqual((clusters[0]["touched"], clusters[0]["size"]), (1, 3))

    def test_clusters_come_from_the_whole_vault_not_the_time_window(self):
        # `hot` is linked only from notes untouched for a month. Scoping the graph
        # to the window would make it look like an orphan; it must not.
        files = {"hot.md": "", **{f"old{i}.md": "[[hot]]" for i in range(4)}}
        clusters, orphaned = self.report(files, ages={f"old{i}.md": 30 for i in range(4)})
        self.assertEqual(orphaned, [])
        self.assertEqual(clusters[0]["notes"][0]["name"], "hot")
        self.assertEqual(clusters[0]["notes"][0]["degree"], 4)

    def test_touched_notes_with_no_links_are_listed_separately(self):
        clusters, orphaned = self.report({"a.md": "[[b]]", "b.md": "", "lone.md": ""}, ages={})
        self.assertEqual([e["name"] for e in orphaned], ["lone"])
        self.assertNotIn("lone", {e["name"] for c in clusters for e in c["notes"]})

    def test_clusters_are_ordered_by_how_much_of_them_you_touched(self):
        files = {
            "a.md": "[[b]] [[c]]", "b.md": "[[c]]", "c.md": "",
            "z.md": "[[y]] [[x]]", "y.md": "[[x]]", "x.md": "",
        }
        clusters, _ = self.report(files, ages={"y.md": 30, "x.md": 30})
        self.assertEqual([c["touched"] for c in clusters], [3, 1])

    def test_notes_within_a_cluster_run_newest_first(self):
        files = {"a.md": "[[b]] [[c]]", "b.md": "[[c]]", "c.md": ""}
        clusters, _ = self.report(files, ages={"a.md": 3, "b.md": 1, "c.md": 5})
        self.assertEqual([e["name"] for e in clusters[0]["notes"]], ["b", "a", "c"])

    def test_an_empty_window_reports_nothing(self):
        clusters, orphaned = self.report({"a.md": "[[b]]", "b.md": ""}, ages={"a.md": 30, "b.md": 30})
        self.assertEqual((clusters, orphaned), ([], []))

    def test_entries_carry_a_vault_relative_path_and_a_readable_age(self):
        clusters, _ = self.report({"a.md": "[[b]]", "b.md": ""}, ages={"a.md": 2})
        entry = next(e for c in clusters for e in c["notes"] if e["name"] == "a")
        self.assertEqual(entry["rel"], "a.md")
        self.assertEqual(entry["age"], "2d")
        self.assertNotIn("/", entry["rel"])


class ActivityReportTests(unittest.TestCase):
    NOTE = {"name": "a", "path": "/v/a.md", "rel": "a.md", "degree": 3,
            "broken_links": [], "age": "2d", "age_seconds": 172800}
    SHAPE = {"notes": 9, "edges": 4, "components": 2, "largest_component": 5,
             "isolated": 1, "clusters": 3, "largest_cluster": 5, "modularity": 0.42}

    def render(self, clusters, orphaned, touched=1):
        return ariadne_graph.format_activity(clusters, orphaned, "7d", touched, 9, "/v", self.SHAPE)

    def test_names_the_window_and_the_counts(self):
        out = self.render([{"cluster": 1, "size": 5, "touched": 1, "notes": [self.NOTE]}], [])
        self.assertIn("Active in the last 7d", out)
        self.assertIn("1 of 9 notes touched", out)
        self.assertIn("cluster 1   1 of 5 notes touched", out)
        self.assertIn("a  [3 links]  2d  a.md", out)

    def test_carries_the_graph_shape(self):
        out = self.render([], [dict(self.NOTE, degree=0)])
        self.assertIn("graph: 9 notes, 4 links, 2 components", out)

    def test_orphans_get_their_own_heading(self):
        out = self.render([], [dict(self.NOTE, degree=0)])
        self.assertIn("Touched and still orphaned (1)", out)
        self.assertIn("[0 links]", out)

    def test_an_empty_window_says_so_plainly(self):
        out = self.render([], [], touched=0)
        self.assertIn("Nothing touched in that window.", out)

    def test_control_characters_in_a_note_name_are_stripped(self):
        out = self.render([], [dict(self.NOTE, degree=0, name="ev\x1b[31mil", rel="a\x07.md")])
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, out)


class ActivityCliTests(unittest.TestCase):
    def test_since_switches_the_report_and_carries_both_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "", "old.md": ""}, ages={"old.md": 30})
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--since", "7d", "--json"],
                capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
        self.assertEqual((payload["window"], payload["touched"], payload["total_notes"]), ("7d", 2, 3))
        self.assertIn("active_clusters", payload)
        self.assertIn("touched_orphans", payload)
        # The health report's keys are gone: --since is a different question.
        self.assertNotIn("orphans", payload)

    def test_a_bad_duration_fails_before_the_vault_is_read(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "/no/such/vault", "--since", "7"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--since", result.stderr)
        self.assertNotIn("not a directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
