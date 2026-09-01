#!/usr/bin/env python3

"""Tests for bin/notes-embed-setup, against a fake `ollama` on $PATH.

No real Ollama server or binary is ever invoked: every test builds its own tiny
`ollama` shell script in a temp dir and points $PATH at it, so pull/list behaviour
is fully controlled and nothing leaves the machine.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("notes-embed-setup")

_loader = importlib.machinery.SourceFileLoader("notes_embed_setup", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader("notes_embed_setup", _loader)
notes_embed_setup = importlib.util.module_from_spec(_spec)
_loader.exec_module(notes_embed_setup)

FAKE_OLLAMA = """#!/bin/sh
if [ "$1" = "list" ]; then
  if [ -n "$FAKE_OLLAMA_LIST_FAIL" ]; then
    echo "connection refused" >&2
    exit 1
  fi
  echo "NAME                    ID              SIZE      MODIFIED"
  cat "$FAKE_OLLAMA_MODELS" 2>/dev/null
  exit 0
elif [ "$1" = "pull" ]; then
  echo "$2" >> "$FAKE_OLLAMA_PULLED"
  exit "${FAKE_OLLAMA_PULL_EXIT:-0}"
fi
exit 1
"""


@contextlib.contextmanager
def fake_path(models=(), pull_exit=0, list_fail=False):
    """A $PATH containing only a fake `ollama`. `models` seeds `ollama list`'s output."""
    with tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as statedir:
        ollama_path = os.path.join(bindir, "ollama")
        with open(ollama_path, "w") as f:
            f.write(FAKE_OLLAMA)
        os.chmod(ollama_path, os.stat(ollama_path).st_mode | stat.S_IEXEC)

        models_file = os.path.join(statedir, "models")
        with open(models_file, "w") as f:
            for name in models:
                f.write(f"{name}    abc123    600 MB    now\n")

        pulled_file = os.path.join(statedir, "pulled")
        Path(pulled_file).touch()

        old_path = os.environ.get("PATH")
        old_models = os.environ.get("FAKE_OLLAMA_MODELS")
        old_pulled = os.environ.get("FAKE_OLLAMA_PULLED")
        old_exit = os.environ.get("FAKE_OLLAMA_PULL_EXIT")
        old_list_fail = os.environ.get("FAKE_OLLAMA_LIST_FAIL")
        # Prepend, don't replace: the fake script's own #!/bin/sh body needs the real
        # `cat` still reachable, and prepending still makes `ollama` resolve to ours first.
        os.environ["PATH"] = bindir + os.pathsep + (old_path or "")
        os.environ["FAKE_OLLAMA_MODELS"] = models_file
        os.environ["FAKE_OLLAMA_PULLED"] = pulled_file
        os.environ["FAKE_OLLAMA_PULL_EXIT"] = str(pull_exit)
        if list_fail:
            os.environ["FAKE_OLLAMA_LIST_FAIL"] = "1"
        else:
            os.environ.pop("FAKE_OLLAMA_LIST_FAIL", None)
        try:
            yield pulled_file
        finally:
            _restore(old_path, "PATH")
            _restore(old_models, "FAKE_OLLAMA_MODELS")
            _restore(old_pulled, "FAKE_OLLAMA_PULLED")
            _restore(old_exit, "FAKE_OLLAMA_PULL_EXIT")
            _restore(old_list_fail, "FAKE_OLLAMA_LIST_FAIL")


def _restore(old, name):
    if old is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = old


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = notes_embed_setup.main(argv)
    return code, out.getvalue(), err.getvalue()


def pulled_models(pulled_file):
    return Path(pulled_file).read_text().split()


class ModelValidationTests(unittest.TestCase):
    def test_option_shaped_model_name_is_rejected_before_touching_ollama(self):
        # `--model=X` form: argparse itself already refuses the space form
        # (`--model --insecure`) as "expected one argument", but happily hands
        # this one through as args.model == "--insecure" without our own check.
        with fake_path(models=[]) as pulled_file:
            code, out, err = run_main(["--model=--insecure"])
            self.assertEqual(pulled_models(pulled_file), [])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())


class OllamaAbsentTests(unittest.TestCase):
    def test_ollama_not_on_path_is_a_clean_failure(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            old_path = os.environ.get("PATH")
            os.environ["PATH"] = empty_dir
            try:
                code, out, err = run_main(["--model", "embeddinggemma"])
            finally:
                _restore(old_path, "PATH")
        self.assertEqual(code, 1)
        self.assertIn("ollama", err.lower())


class ModelPresentTests(unittest.TestCase):
    def test_present_model_exits_zero_without_pulling(self):
        with fake_path(models=["embeddinggemma:latest"]) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma"])
            self.assertEqual(pulled_models(pulled_file), [])
        self.assertEqual(code, 0)
        self.assertIn("embeddinggemma", out)

    def test_a_different_tag_of_the_same_model_is_not_a_match(self):
        # An unqualified --model implies :latest; a differently-tagged pull already
        # present doesn't satisfy that, and notes-similar would fail against :latest
        # if this reported "present" here.
        with fake_path(models=["embeddinggemma:300m"]) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma"])
            self.assertEqual(pulled_models(pulled_file), ["embeddinggemma"])
        self.assertEqual(code, 0)

    def test_an_explicitly_tagged_model_matches_exactly(self):
        with fake_path(models=["embeddinggemma:300m"]) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma:300m"])
            self.assertEqual(pulled_models(pulled_file), [])
        self.assertEqual(code, 0)


class ModelMissingCheckOnlyTests(unittest.TestCase):
    def test_missing_model_with_check_reports_and_does_not_pull(self):
        with fake_path(models=["some-other-model:latest"]) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma", "--check"])
            self.assertEqual(pulled_models(pulled_file), [])
        self.assertEqual(code, 1)
        self.assertIn("embeddinggemma", out)


class ModelMissingPullTests(unittest.TestCase):
    def test_missing_model_is_pulled(self):
        with fake_path(models=[]) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma"])
            self.assertEqual(pulled_models(pulled_file), ["embeddinggemma"])
        self.assertEqual(code, 0)

    def test_failed_pull_propagates_its_exit_code(self):
        with fake_path(models=[], pull_exit=17) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma"])
            self.assertEqual(pulled_models(pulled_file), ["embeddinggemma"])
        self.assertEqual(code, 17)


class OllamaListFailsTests(unittest.TestCase):
    def test_ollama_list_failure_is_a_clean_exit(self):
        with fake_path(models=[], list_fail=True) as pulled_file:
            code, out, err = run_main(["--model", "embeddinggemma"])
            self.assertEqual(pulled_models(pulled_file), [])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())


if __name__ == "__main__":
    unittest.main()
