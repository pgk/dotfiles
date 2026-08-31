#!/usr/bin/env python3

"""Tests for bin/notes-deadlinks, run against synthetic notes only (never ~/notes)."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("notes-deadlinks")

loader = importlib.machinery.SourceFileLoader("notes_deadlinks", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("notes_deadlinks", loader)
notes_deadlinks = importlib.util.module_from_spec(spec)
loader.exec_module(notes_deadlinks)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_common


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class CollectDeadLinksTests(unittest.TestCase):
    def collect(self, files, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            paths = list(notes_common.iter_markdown_files(tmp, excludes or []))
            index = notes_common.build_name_index(paths)
            dead_by_file = notes_deadlinks.collect_dead_links(paths, index)
            report = notes_deadlinks.build_report(dead_by_file, index)
            return report

    def test_note_with_one_broken_link_appears_with_candidates(self):
        report = self.collect(
            {
                "project-plan.md": "content",
                "a.md": "see [[projct-plan]]",
            }
        )
        self.assertEqual(len(report), 1)
        entry = report[0]
        self.assertEqual(entry["name"], "a")
        self.assertEqual(len(entry["dead_links"]), 1)
        self.assertEqual(entry["dead_links"][0]["link"], "projct-plan")
        self.assertIn("project-plan", entry["dead_links"][0]["candidates"])

    def test_note_with_all_links_resolved_is_absent(self):
        report = self.collect(
            {
                "hub.md": "content",
                "a.md": "see [[hub]]",
            }
        )
        self.assertEqual(report, [])

    def test_multiple_dead_links_in_one_note_are_grouped_and_sorted(self):
        report = self.collect(
            {
                "a.md": "see [[zeta-ghost]] and [[alpha-ghost]]",
            }
        )
        self.assertEqual(len(report), 1)
        links = [dl["link"] for dl in report[0]["dead_links"]]
        self.assertEqual(links, ["alpha-ghost", "zeta-ghost"])

    def test_dead_link_with_no_close_match_has_empty_candidates(self):
        report = self.collect(
            {
                "hub.md": "content",
                "a.md": "see [[zzz-totally-unrelated-xyz]]",
            }
        )
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["dead_links"][0]["candidates"], [])

    def test_exclude_removes_dead_links_in_excluded_file(self):
        report = self.collect(
            {
                "templates/skip-me.md": "see [[ghost]]",
                "a.md": "content",
            },
            excludes=["templates/*"],
        )
        self.assertEqual(report, [])

    def test_candidate_uses_on_disk_display_casing(self):
        report = self.collect(
            {
                "Project-Plan.md": "content",
                "a.md": "see [[projct-plan]]",
            }
        )
        self.assertEqual(report[0]["dead_links"][0]["candidates"], ["Project-Plan"])

    def test_duplicate_dead_link_in_one_note_is_deduped(self):
        report = self.collect(
            {
                "a.md": "see [[ghost]] and again [[ghost]]",
            }
        )
        self.assertEqual(len(report), 1)
        self.assertEqual([dl["link"] for dl in report[0]["dead_links"]], ["ghost"])

    def test_notes_with_dead_links_are_sorted_by_name(self):
        report = self.collect(
            {
                "zeta.md": "see [[ghost1]]",
                "alpha.md": "see [[ghost2]]",
            }
        )
        self.assertEqual([e["name"] for e in report], ["alpha", "zeta"])


class FormatTests(unittest.TestCase):
    def test_text_reports_no_dead_links(self):
        text = notes_deadlinks.format_text([], 3, "/vault")
        self.assertIn("No dead links found among 3 notes", text)

    def test_text_includes_candidates_and_no_matches_label(self):
        report = [
            {
                "name": "a",
                "path": "/vault/a.md",
                "dead_links": [
                    {"link": "projct-plan", "candidates": ["project-plan"]},
                    {"link": "zzz-nothing", "candidates": []},
                ],
            }
        ]
        text = notes_deadlinks.format_text(report, 2, "/vault")
        self.assertIn("[[projct-plan]]  possible: project-plan", text)
        self.assertIn("[[zzz-nothing]]  no matches", text)

    def test_text_strips_control_characters_from_link_and_candidates(self):
        report = [
            {
                "name": "a",
                "path": "/vault/a.md",
                "dead_links": [
                    {"link": "ghost\nnewline", "candidates": ["cand\x1b[31mred"]},
                ],
            }
        ]
        text = notes_deadlinks.format_text(report, 1, "/vault")
        self.assertIn("[[ghost newline]]", text)
        self.assertIn("cand [31mred", text)
        self.assertNotIn("\x1b", text)

    def test_json_shape_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "project-plan.md": "content",
                    "a.md": "see [[projct-plan]]",
                    "b.md": "see [[hub]] and [[hub]]",
                    "hub.md": "content",
                },
            )
            paths = list(notes_common.iter_markdown_files(tmp, []))
            index = notes_common.build_name_index(paths)
            dead_by_file = notes_deadlinks.collect_dead_links(paths, index)
            report = notes_deadlinks.build_report(dead_by_file, index)
            payload = json.loads(notes_deadlinks.format_json(report, len(paths), tmp))

        self.assertEqual(payload["vault"], tmp)
        self.assertEqual(payload["total_notes"], 4)
        self.assertEqual({e["name"] for e in payload["notes_with_dead_links"]}, {"a"})
        for entry in payload["notes_with_dead_links"]:
            self.assertEqual(set(entry), {"name", "path", "dead_links"})
            for dl in entry["dead_links"]:
                self.assertEqual(set(dl), {"link", "candidates"})


class CliSubprocessTests(unittest.TestCase):
    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "project-plan.md": "content",
                    "a.md": "see [[projct-plan]]",
                },
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp, "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["total_notes"], 2)
            self.assertEqual({e["name"] for e in payload["notes_with_dead_links"]}, {"a"})

    def test_cli_text_output_no_dead_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, {"a.md": "[[b]]", "b.md": "[[a]]"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmp],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(f"No dead links found among 2 notes in {os.path.abspath(tmp)}", result.stdout)

    def test_cli_rejects_nonexistent_vault(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "/no/such/vault/path"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a directory", result.stderr)

    def test_cli_repeatable_exclude_does_not_swallow_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(
                tmp,
                {
                    "a.md": "see [[templates/skip-me]]",
                    "templates/skip-me.md": "see [[ghost]]",
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
        self.assertNotIn("canary", result.stdout)

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
