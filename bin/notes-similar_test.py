#!/usr/bin/env python3

"""Tests for bin/notes-similar, run against synthetic notes only (never ~/notes).

No test may require a live embedding server: `fake_embedder` supplies deterministic
vectors and the CLI cases point at a closed loopback port. Cache and HTTP behaviour
live in notes_embed_cache_test.py and notes_embed_client_test.py.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).with_name("notes-similar")

loader = importlib.machinery.SourceFileLoader("notes_similar", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("notes_similar", loader)
notes_similar = importlib.util.module_from_spec(spec)
loader.exec_module(notes_similar)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_common
import notes_embed_cache
import notes_similar_report


def write_vault(root, files):
    for relpath, content in files.items():
        path = Path(root) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def fake_embedder(dims=16, calls=None):
    """Deterministic 'embeddings': a bag-of-words hash, so shared words raise cosine.

    crc32 rather than hash(), which is PYTHONHASHSEED-randomised and would make the
    ranking assertions depend on the run.
    """

    def embed(texts):
        if calls is not None:
            calls.extend(texts)
        vectors = []
        for text in texts:
            values = [0.0] * dims
            for word in text.lower().split():
                values[zlib.crc32(word.encode("utf-8")) % dims] += 1.0
            if not any(values):
                values[0] = 1.0
            vectors.append(notes_embed_cache.normalize(values))
        return vectors

    return embed


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class NoteTextTests(unittest.TestCase):
    def test_frontmatter_is_stripped_and_name_prepended(self):
        text = notes_similar.note_text("my-note", "---\ntitle: X\ntags:\n  - a\n---\nThe body.\n")
        self.assertEqual(text, "my-note\n\nThe body.")

    def test_note_without_frontmatter_keeps_its_body(self):
        self.assertEqual(notes_similar.note_text("n", "Just text.\n"), "n\n\nJust text.")

    def test_frontmatter_only_note_yields_just_the_name(self):
        self.assertEqual(notes_similar.note_text("n", "---\ntitle: X\n---\n"), "n")

    def test_unterminated_frontmatter_is_left_alone(self):
        self.assertEqual(notes_similar.note_text("n", "---\ntitle: X\n"), "n\n\n---\ntitle: X")

    def test_long_note_is_truncated(self):
        text = notes_similar.note_text("n", "x" * (notes_similar.MAX_CHARS * 2))
        self.assertEqual(len(text), notes_similar.MAX_CHARS)

    def test_hash_ignores_frontmatter_only_edits(self):
        a = notes_similar.note_text("n", "---\ntags: [one]\n---\nBody.\n")
        b = notes_similar.note_text("n", "---\ntags: [two]\n---\nBody.\n")
        self.assertEqual(notes_similar.content_hash(a), notes_similar.content_hash(b))

    def test_hash_changes_when_body_changes(self):
        a = notes_similar.note_text("n", "Body one.")
        b = notes_similar.note_text("n", "Body two.")
        self.assertNotEqual(notes_similar.content_hash(a), notes_similar.content_hash(b))

    def test_preview_skips_headings_and_blank_lines(self):
        text = notes_similar.note_text("n", "# Heading\n\n\nReal first line.\n")
        self.assertEqual(notes_similar.preview_of(text), "Real first line.")


class ScanVaultTests(unittest.TestCase):
    def scan(self, files, excludes=None):
        with tempfile.TemporaryDirectory() as tmp:
            write_vault(tmp, files)
            return notes_similar.scan_vault(tmp, excludes or [])

    def test_collects_name_hash_and_links_in_one_pass(self):
        notes = self.scan({"a.md": "Links to [[b]] and [[c]].", "b.md": "Body b."})
        by_name = {n["name"]: n for n in notes}
        self.assertEqual(sorted(by_name), ["a", "b"])
        self.assertEqual(by_name["a"]["links"], ["b", "c"])
        self.assertEqual(
            by_name["a"]["hash"],
            notes_similar.content_hash(notes_similar.note_text("a", "Links to [[b]] and [[c]].")),
        )
        self.assertNotEqual(by_name["a"]["hash"], by_name["b"]["hash"])

    def test_excludes_are_honoured(self):
        notes = self.scan({"a.md": "a", "skip/b.md": "b"}, excludes=["skip/*"])
        self.assertEqual([n["name"] for n in notes], ["a"])


class FindSimilarTests(unittest.TestCase):
    def prepare(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_vault(tmp.name, files)
        notes = notes_similar.scan_vault(tmp.name, [])
        name_index = notes_common.build_name_index([n["path"] for n in notes])
        cached = {}
        notes_embed_cache.refresh(notes, cached, 0, fake_embedder())
        return tmp.name, notes, name_index, cached

    def similar(self, files, target_name, limit=10, include_linked=False):
        _, notes, name_index, cached = self.prepare(files)
        target = notes_similar.resolve_target(target_name, notes, name_index)
        return notes_similar.find_similar(target, notes, cached, name_index, limit, include_linked)

    def test_self_is_excluded(self):
        results = self.similar({"a.md": "alpha beta", "b.md": "alpha beta"}, "a")
        self.assertNotIn("a", [r["name"] for r in results])

    def test_results_are_sorted_by_descending_score(self):
        results = self.similar(
            {
                "target.md": "quantum entanglement physics",
                "close.md": "quantum entanglement physics",
                "far.md": "sourdough bread baking recipe",
            },
            "target",
        )
        self.assertEqual([r["name"] for r in results], ["close", "far"])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_forward_linked_notes_are_excluded_by_default(self):
        files = {"a.md": "shared words here [[b]]", "b.md": "shared words here", "c.md": "shared words here"}
        self.assertEqual([r["name"] for r in self.similar(files, "a")], ["c"])

    def test_backlinked_notes_are_excluded_by_default(self):
        files = {"a.md": "shared words here", "b.md": "shared words here [[a]]", "c.md": "shared words here"}
        self.assertEqual([r["name"] for r in self.similar(files, "a")], ["c"])

    def test_all_includes_linked_notes_and_labels_them(self):
        files = {"a.md": "shared words here [[b]]", "b.md": "shared words here", "c.md": "shared words here"}
        results = self.similar(files, "a", include_linked=True)
        by_name = {r["name"]: r for r in results}
        self.assertEqual(sorted(by_name), ["b", "c"])
        self.assertTrue(by_name["b"]["linked"])
        self.assertFalse(by_name["c"]["linked"])

    def test_limit_caps_the_result_count(self):
        files = {f"n{i}.md": "shared words here" for i in range(6)}
        files["target.md"] = "shared words here"
        self.assertEqual(len(self.similar(files, "target", limit=2)), 2)

    def test_missing_target_embedding_is_unavailable(self):
        _, notes, name_index, _ = self.prepare({"a.md": "a", "b.md": "b"})
        target = notes_similar.resolve_target("a", notes, name_index)
        with self.assertRaises(notes_embed_cache.EmbedUnavailable):
            notes_similar.find_similar(target, notes, {}, name_index, 10, False)


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
        notes = notes_similar.scan_vault(tmp.name, [])
        name_index = notes_common.build_name_index([n["path"] for n in notes])
        cached = {}
        notes_embed_cache.refresh(notes, cached, 0, fake_embedder())
        return notes, name_index, cached

    def rank(self, files=None, target_name="t", bridge_first=True):
        notes, name_index, cached = self.prepare(files or CLUSTER_VAULT)
        clusters, shape = notes_similar.cluster_notes(notes, name_index)
        target = notes_similar.resolve_target(target_name, notes, name_index)
        results = notes_similar.find_similar(
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
        clusters, _ = notes_similar.cluster_notes(notes, name_index)
        target = notes_similar.resolve_target("t", notes, name_index)
        results = notes_similar.find_similar(
            target, notes, cached, name_index, 1, False, clusters=clusters, bridge_first=True
        )
        self.assertEqual([r["crosses"] for r in results], [True, False])
        self.assertEqual(results[1]["name"], "a3")

    def test_the_best_same_cluster_hit_survives_the_limit(self):
        results, _, _ = self.rank()
        self.assertIn("a3", [r["name"] for r in results])

    def test_no_bridge_applies_one_shared_limit(self):
        notes, name_index, cached = self.prepare(CLUSTER_VAULT)
        clusters, _ = notes_similar.cluster_notes(notes, name_index)
        target = notes_similar.resolve_target("t", notes, name_index)
        results = notes_similar.find_similar(
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
        target = notes_similar.resolve_target("t", notes, name_index)
        results = notes_similar.find_similar(target, notes, cached, name_index, 10, False)
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
        first, _ = notes_similar.cluster_notes(notes, name_index)
        for _ in range(3):
            self.assertEqual(notes_similar.cluster_notes(notes, name_index)[0], first)


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
        out = notes_similar_report.format_text({"name": "t"}, [self.result()], 2, False, "/v")
        self.assertIn("[cluster 3]", out)

    def test_text_report_leaves_same_cluster_hits_unmarked(self):
        out = notes_similar_report.format_text(
            {"name": "t"}, [self.result(crosses=False)], 2, False, "/v"
        )
        self.assertNotIn("cluster", out)

    def test_the_two_groups_get_their_own_headings(self):
        rows = [self.result(), self.result(name="near", crosses=False, cluster=1)]
        out = notes_similar_report.format_text(
            {"name": "t"}, rows, 9, False, "/v", self.SHAPE, grouped=True
        )
        self.assertIn("Bridging other clusters (1)", out)
        self.assertIn("Within cluster 1 (1)", out)
        self.assertLess(out.index("Bridging"), out.index("Within cluster"))

    def test_an_empty_group_gets_no_heading(self):
        out = notes_similar_report.format_text(
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
        out = notes_similar_report.format_text(
            {"name": "t"}, rows, 9, False, "/v", self.SHAPE, grouped=False
        )
        self.assertNotIn("Bridging", out)
        self.assertNotIn("Within cluster", out)
        self.assertLess(out.index("near"), out.index("far"))

    def test_no_headings_when_no_clustering_ran(self):
        rows = [self.result(crosses=False, cluster=None)]
        out = notes_similar_report.format_text({"name": "t"}, rows, 9, False, "/v")
        self.assertNotIn("Bridging", out)
        self.assertNotIn("Within", out)

    def test_text_report_carries_the_graph_shape_as_its_own_caveat(self):
        out = notes_similar_report.format_text(
            {"name": "t"}, [self.result()], 9, False, "/v", self.SHAPE
        )
        self.assertIn("9 notes", out)
        self.assertIn("3 components", out)
        self.assertIn("0.120", out)

    def test_json_carries_shape_and_per_result_cluster_fields(self):
        shape = {"notes": 2, "edges": 1, "components": 1, "largest_component": 2,
                 "isolated": 0, "clusters": 1, "largest_cluster": 2, "modularity": 0.0}
        payload = json.loads(
            notes_similar_report.format_json(
                {"name": "t", "path": "/v/t.md"}, [self.result()], False, "/v", "m", shape=shape
            )
        )
        self.assertEqual(payload["shape"], shape)
        self.assertTrue(payload["similar"][0]["crosses"])
        self.assertEqual(payload["similar"][0]["cluster"], 3)

    def test_json_shape_is_null_when_embeddings_were_unavailable(self):
        payload = json.loads(
            notes_similar_report.format_json(None, [], False, "/v", "m", error="down")
        )
        self.assertIsNone(payload["shape"])


class FormatTextTests(unittest.TestCase):
    def test_control_characters_in_note_data_are_stripped(self):
        target = {"name": "tar\x1b[31mget"}
        results = [
            {
                "name": "ev\x07il",
                "path": "/v/ev.md",
                "score": 0.5,
                "linked": False,
                "crosses": False,
                "cluster": 0,
                "preview": "p\x1bq",
            }
        ]
        out = notes_similar_report.format_text(target, results, 2, False, "/v")
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, out)

    def test_empty_results_still_name_the_target(self):
        out = notes_similar_report.format_text({"name": "solo"}, [], 7, False, "/v")
        self.assertIn("solo", out)
        self.assertIn("7", out)


class FormatJsonTests(unittest.TestCase):
    def test_control_characters_are_stripped_from_names_and_previews(self):
        target = {"name": "tar\x1bget", "path": "/v/t.md"}
        results = [{"name": "ev\x07il", "path": "/v/e.md", "score": 0.5, "linked": False, "preview": "p\x1bq"}]
        payload = json.loads(notes_similar_report.format_json(target, results, False, "/v", "m"))
        self.assertNotIn("\x1b", payload["target"]["name"])
        self.assertNotIn("\x07", payload["similar"][0]["name"])
        self.assertNotIn("\x1b", payload["similar"][0]["preview"])


class ResolveTargetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.vault = tmp.name
        write_vault(self.vault, {"Alpha Note.md": "a", "sub/Beta.md": "b"})
        self.notes = notes_similar.scan_vault(self.vault, [])
        self.name_index = notes_common.build_name_index([n["path"] for n in self.notes])

    def resolve(self, spec):
        return notes_similar.resolve_target(spec, self.notes, self.name_index)

    def test_resolves_by_absolute_path(self):
        self.assertEqual(self.resolve(os.path.join(self.vault, "Alpha Note.md"))["name"], "Alpha Note")

    def test_resolves_by_name(self):
        self.assertEqual(self.resolve("Alpha Note")["name"], "Alpha Note")

    def test_resolves_by_name_case_insensitively(self):
        self.assertEqual(self.resolve("alpha note")["name"], "Alpha Note")

    def test_resolves_nested_note_by_name(self):
        self.assertEqual(self.resolve("Beta")["name"], "Beta")

    def test_unknown_target_is_none(self):
        self.assertIsNone(self.resolve("no such note"))

    def test_a_path_outside_the_vault_cannot_be_selected(self):
        self.assertIsNone(self.resolve("/etc/passwd"))


class ArgumentTests(unittest.TestCase):
    """The vault must never resolve to ~/notes without being named."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("NOTES_VAULT", None)

    def split(self, argv):
        return notes_similar.split_positional(notes_similar.parse_args(argv))

    def test_index_requires_an_explicit_vault(self):
        with self.assertRaises(ValueError) as caught:
            self.split(["--index"])
        self.assertIn("VAULT path is required", str(caught.exception))

    def test_index_with_an_option_swallowing_the_positional_is_refused(self):
        # The historical leak shape: --exclude eats the vault, leaving no positional.
        for argv in (
            ["--index", "--exclude", "drafts/*"],
            ["--index", "--model", "some-model"],
            ["--index", "--endpoint", "http://localhost:1/v1"],
        ):
            with self.assertRaises(ValueError, msg=argv):
                self.split(argv)

    def test_index_accepts_an_explicit_vault(self):
        self.assertEqual(self.split(["--index", "./vault"]), (None, "./vault"))

    def test_an_empty_vault_string_is_not_a_vault(self):
        with self.assertRaises(ValueError):
            self.split(["--index", ""])

    def test_query_requires_a_target(self):
        with self.assertRaises(ValueError):
            self.split([])

    def test_a_query_without_a_vault_is_refused_rather_than_defaulting(self):
        # The shape that accidentally scanned the real vault: one stray token lands
        # as the target, and the vault used to fall back to ~/notes.
        with self.assertRaises(ValueError) as caught:
            self.split(["--index --exclude drafts/*"])
        self.assertIn("VAULT path is required", str(caught.exception))

    def test_query_vault_can_be_given(self):
        self.assertEqual(self.split(["note", "./vault"]), ("note", "./vault"))

    def test_notes_vault_env_var_supplies_the_vault(self):
        os.environ["NOTES_VAULT"] = "/from/env"
        self.assertEqual(self.split(["note"]), ("note", "/from/env"))
        self.assertEqual(self.split(["--index"]), (None, "/from/env"))

    def test_a_blank_notes_vault_is_not_a_vault(self):
        os.environ["NOTES_VAULT"] = "   "
        with self.assertRaises(ValueError):
            self.split(["note"])

    def test_extra_positionals_are_refused(self):
        with self.assertRaises(ValueError):
            self.split(["a", "b", "c"])

    def check(self, argv):
        notes_similar.check_args(notes_similar.parse_args(argv))

    def test_limit_must_be_positive(self):
        for argv in (["n", "-n", "0"], ["n", "-n", "-3"]):
            with self.assertRaises(ValueError, msg=argv):
                self.check(argv)

    def test_negative_max_refresh_is_refused(self):
        with self.assertRaises(ValueError):
            self.check(["n", "--max-refresh", "-1"])

    def test_rebuild_without_index_is_refused(self):
        with self.assertRaises(ValueError):
            self.check(["n", "--rebuild"])

    def test_remote_endpoint_is_refused_without_the_opt_in(self):
        with self.assertRaises(ValueError):
            self.check(["n", "--endpoint", "https://example.com/v1"])

    def test_remote_endpoint_is_allowed_with_the_opt_in(self):
        self.check(["n", "--endpoint", "https://example.com/v1", "--allow-remote-endpoint"])


class CliTests(unittest.TestCase):
    """End-to-end runs. The endpoint always points at a closed port — no server exists."""

    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        vault = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        self.addCleanup(vault.cleanup)
        self.cache = cache.name
        self.vault = vault.name
        self.port = closed_port()
        write_vault(self.vault, {"a.md": "alpha", "b.md": "beta"})

    def run_cli(self, args):
        # HOME points at the temp vault so the ~/notes default is physically unable
        # to reach the real vault from a subprocess, whatever a future test passes.
        env = dict(
            os.environ,
            HOME=self.vault,
            XDG_CACHE_HOME=self.cache,
        )
        for leaked in ("NOTES_EMBED_URL", "NOTES_EMBED_MODEL", "NOTES_VAULT"):
            env.pop(leaked, None)
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args, "--endpoint", f"http://127.0.0.1:{self.port}/v1"],
            capture_output=True,
            text=True,
            env=env,
            cwd=self.vault,
        )

    def test_query_without_a_server_exits_zero_with_valid_empty_json(self):
        result = self.run_cli(["a", self.vault, "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["available"])
        self.assertEqual(payload["similar"], [])
        self.assertTrue(payload["error"])

    def test_query_without_a_server_warns_on_stderr(self):
        result = self.run_cli(["a", self.vault])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("embeddings unavailable", result.stderr.lower())

    def test_the_egress_destination_is_announced_before_any_upload(self):
        result = self.run_cli(["a", self.vault, "--json"])
        self.assertIn("sending", result.stderr)
        self.assertIn(f"127.0.0.1:{self.port}", result.stderr)
        self.assertIn(self.vault, result.stderr)

    def test_index_without_a_server_exits_nonzero(self):
        result = self.run_cli(["--index", self.vault])
        self.assertEqual(result.returncode, 1)
        self.assertIn("embeddings unavailable", result.stderr.lower())

    def test_index_without_a_vault_refuses_rather_than_defaulting(self):
        result = self.run_cli(["--index"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("VAULT path is required", result.stderr)
        self.assertNotIn("sending", result.stderr)

    def test_a_query_without_a_vault_refuses_before_reading_anything(self):
        unreadable = Path(self.vault) / "locked.md"
        unreadable.write_text("x")
        unreadable.chmod(0o000)
        self.addCleanup(unreadable.chmod, 0o600)

        result = self.run_cli(["some-stray-token"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("VAULT path is required", result.stderr)
        # No vault was walked, so scan_vault never reported the unreadable note.
        self.assertNotIn("skipping unreadable note", result.stderr)
        self.assertNotIn("sending", result.stderr)

    def test_remote_endpoint_is_refused_before_any_note_is_read(self):
        # An unreadable note makes scan_vault announce itself on stderr; if that
        # warning appears, validation ran too late to have prevented the read.
        unreadable = Path(self.vault) / "locked.md"
        unreadable.write_text("x")
        unreadable.chmod(0o000)
        self.addCleanup(unreadable.chmod, 0o600)

        env = dict(os.environ, HOME=self.vault, XDG_CACHE_HOME=self.cache)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "a", self.vault, "--endpoint", "https://example.com/v1"],
            capture_output=True,
            text=True,
            env=env,
            cwd=self.vault,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not loopback", result.stderr)
        self.assertNotIn("skipping unreadable note", result.stderr)

    def test_stale_index_over_max_refresh_refuses_instead_of_embedding(self):
        result = self.run_cli(["a", self.vault, "--json", "--max-refresh", "1"])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["available"])
        self.assertIn("--index", payload["error"])
        self.assertNotIn("sending", result.stderr)

    def test_unknown_target_exits_nonzero_with_valid_json(self):
        result = self.run_cli(["no-such-note", self.vault, "--json"])
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertIsNone(payload["target"])
        self.assertEqual(payload["similar"], [])

    def test_missing_target_without_index_is_rejected(self):
        result = self.run_cli([])
        self.assertEqual(result.returncode, 1)
        self.assertIn("target note is required", result.stderr)

    def test_index_with_an_empty_vault_string_is_refused(self):
        result = self.run_cli(["--index", ""])
        self.assertEqual(result.returncode, 1)
        self.assertIn("VAULT path is required", result.stderr)

    def test_a_control_character_in_a_note_name_cannot_drive_the_terminal(self):
        # An unreadable note whose name carries an OSC sequence: the warning path
        # prints the filename, so it must be sanitized like every other note text.
        evil = Path(self.vault) / "unread\x1b]0;pwned\x07able.md"
        evil.write_text("x")
        evil.chmod(0o000)
        self.addCleanup(evil.chmod, 0o600)
        result = self.run_cli(["a", self.vault, "--json"])
        self.assertIn("skipping unreadable note", result.stderr)
        for bad in ("\x1b", "\x07"):
            self.assertNotIn(bad, result.stderr)

    def test_nonexistent_vault_is_rejected(self):
        result = self.run_cli(["a", os.path.join(self.vault, "nope")])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a directory", result.stderr)


class FullQueryTests(unittest.TestCase):
    """The happy path end to end, still with no server: run_index then run_query."""

    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        vault = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        self.addCleanup(vault.cleanup)
        self.cache = cache.name
        self.vault = vault.name
        patcher = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.cache})
        patcher.start()
        self.addCleanup(patcher.stop)

        write_vault(
            self.vault,
            {
                "target.md": "gardening compost soil [[linked]]",
                "linked.md": "gardening compost soil",
                "unlinked.md": "gardening compost soil",
                "unrelated.md": "assembly language registers",
            },
        )
        self.notes = notes_similar.scan_vault(self.vault, [])
        self.name_index = notes_common.build_name_index([n["path"] for n in self.notes])

    def test_index_then_query_returns_ranked_unlinked_notes(self):
        args = notes_similar.parse_args(["target", self.vault, "--json"])
        calls = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(notes_similar.run_index(args, self.vault, self.notes, fake_embedder()), 0)
            # Second pass must reuse the cache rather than re-embed.
            query = notes_similar.run_query(
                args, self.vault, "target", self.notes, self.name_index, fake_embedder(calls=calls)
            )
        self.assertEqual((query, calls), (0, []))

        cdir = notes_embed_cache.cache_dir(self.vault)
        cached, dims = notes_embed_cache.load_cache(cdir, args.model)
        self.assertEqual(dims, 16)
        target = notes_similar.resolve_target("target", self.notes, self.name_index)
        names = [r["name"] for r in notes_similar.find_similar(target, self.notes, cached, self.name_index, 10, False)]
        self.assertNotIn("linked", names)
        self.assertEqual(names[0], "unlinked")

    def test_the_cache_lands_outside_the_vault_and_inside_the_cache_dir(self):
        args = notes_similar.parse_args(["target", self.vault, "--json"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            notes_similar.run_index(args, self.vault, self.notes, fake_embedder())

        cdir = notes_embed_cache.cache_dir(self.vault)
        self.assertTrue(cdir.startswith(self.cache), cdir)
        self.assertTrue(os.path.exists(os.path.join(cdir, "index.json")))
        self.assertTrue(list(Path(cdir).glob("vectors-*.f32")))
        self.assertEqual(list(Path(self.vault).rglob("index.json")), [])
        self.assertEqual(list(Path(self.vault).rglob("*.f32")), [])

    def test_editing_a_note_re_embeds_only_that_note(self):
        args = notes_similar.parse_args(["target", self.vault, "--json"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            notes_similar.run_index(args, self.vault, self.notes, fake_embedder())

        (Path(self.vault) / "unrelated.md").write_text("now about raft consensus instead")
        notes = notes_similar.scan_vault(self.vault, [])
        name_index = notes_common.build_name_index([n["path"] for n in notes])
        calls = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            notes_similar.run_query(args, self.vault, "target", notes, name_index, fake_embedder(calls=calls))
        self.assertEqual(len(calls), 1)
        self.assertIn("raft", calls[0])

    def test_a_failure_partway_through_a_first_index_keeps_what_was_embedded(self):
        # Needs more notes than BATCH_SIZE, so there is a second batch to fail on.
        big = tempfile.TemporaryDirectory()
        self.addCleanup(big.cleanup)
        write_vault(big.name, {f"n{i}.md": f"note number {i}" for i in range(notes_embed_cache.BATCH_SIZE + 8)})
        notes = notes_similar.scan_vault(big.name, [])
        args = notes_similar.parse_args(["--index", big.name])

        embedded = []

        def flaky(texts):
            if embedded:
                raise notes_embed_cache.EmbedUnavailable("server went away")
            embedded.extend(texts)
            return fake_embedder()(texts)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(notes_embed_cache.EmbedUnavailable):
                notes_similar.run_index(args, big.name, notes, flaky)

        # dims is still 0 when the first index fails, so this is exactly the case
        # where the partial save used to be silently skipped.
        cached, dims = notes_embed_cache.load_cache(notes_embed_cache.cache_dir(big.name), args.model)
        self.assertEqual(len(embedded), notes_embed_cache.BATCH_SIZE)
        self.assertEqual(len(cached), notes_embed_cache.BATCH_SIZE)
        self.assertEqual(dims, 16)

    def test_rebuild_re_embeds_everything(self):
        index_args = notes_similar.parse_args(["--index", self.vault])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            notes_similar.run_index(index_args, self.vault, self.notes, fake_embedder())

        rebuild_args = notes_similar.parse_args(["--index", "--rebuild", self.vault])
        calls = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            notes_similar.run_index(rebuild_args, self.vault, self.notes, fake_embedder(calls=calls))
        self.assertEqual(len(calls), len(self.notes))


if __name__ == "__main__":
    unittest.main()
