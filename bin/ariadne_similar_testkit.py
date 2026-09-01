"""Shared harness for the ariadne-similar test suites.

`ariadne-similar` is a hyphenated script, so it cannot be imported normally; loading
it, and the deterministic stand-in embedder, live here so the suites that split off
ariadne-similar_test.py do not each carry their own copy.
"""

import importlib.machinery
import importlib.util
import os
import socket
import sys
import zlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ariadne_embed_cache

SCRIPT_PATH = Path(__file__).with_name("ariadne-similar")

_loader = importlib.machinery.SourceFileLoader("ariadne_similar", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader("ariadne_similar", _loader)
ariadne_similar = importlib.util.module_from_spec(_spec)
_loader.exec_module(ariadne_similar)


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
            vectors.append(ariadne_embed_cache.normalize(values))
        return vectors

    return embed


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
