"""OpenAI-compatible embeddings client for notes-similar.

Note text leaves the process only through this module, so endpoint validation and
the "where did it go" formatting live here rather than in the CLI.
"""

import ipaddress
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_common
import notes_embed_cache

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "embeddinggemma"
TIMEOUT = 30
MAX_RESPONSE_BYTES = 64 * 1024 * 1024

EmbedUnavailable = notes_embed_cache.EmbedUnavailable
MAX_ERROR_BYTES = 4096


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx would send the next request somewhere validate_endpoint never approved."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def safe_url(url):
    """URL for display: no userinfo, query, or fragment, so a token in the endpoint isn't logged."""
    parts = urllib.parse.urlsplit(url)
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return notes_common.printable(urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, "", "")))


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_endpoint(endpoint, allow_remote):
    """Note text is POSTed here, so refuse anything that would send it off this machine unasked."""
    parts = urllib.parse.urlsplit(endpoint)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"endpoint must be http or https: {safe_url(endpoint)}")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError(f"endpoint has no host: {safe_url(endpoint)}")
    if not is_loopback(host) and not allow_remote:
        raise ValueError(
            f"endpoint host '{notes_common.printable(host)}' is not loopback — note text would "
            "leave this machine. Pass --allow-remote-endpoint if that is what you want."
        )


def announce(vault, endpoint, model, count):
    """Never embed without saying what is being sent where — this is the tool's only egress."""
    print(
        f"notes-similar: sending {count} note(s) from {vault} to {safe_url(endpoint)} "
        f"({notes_common.printable(model)})",
        file=sys.stderr,
    )


def _ordered(data, count, where):
    """The OpenAI schema does not promise response order, and a bad server may repeat an index."""
    indices = [item.get("index") if isinstance(item, dict) else None for item in data]
    if all(isinstance(i, int) for i in indices):
        if sorted(indices) != list(range(count)):
            raise EmbedUnavailable(f"{where}: embedding indices are not 0..{count - 1}")
        return sorted(data, key=lambda item: item["index"])
    return data


def _reject_constant(name):
    raise EmbedUnavailable(f"embedding server returned a non-numeric value: {name}")


def _fetch(url, where, payload, timeout):
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise EmbedUnavailable(f"{where}: response larger than {MAX_RESPONSE_BYTES} bytes")
        # Python's json accepts the non-standard NaN/Infinity literals by default.
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except urllib.error.HTTPError as exc:
        detail = notes_common.printable(exc.read(MAX_ERROR_BYTES).decode("utf-8", "replace"))[:200].strip()
        raise EmbedUnavailable(f"{where}: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise EmbedUnavailable(f"{where}: {notes_common.printable(exc.reason)}") from exc
    except (OSError, ValueError) as exc:
        raise EmbedUnavailable(f"{where}: {notes_common.printable(exc)}") from exc


def embed_batch(texts, endpoint, model, timeout=TIMEOUT):
    """POST an OpenAI-compatible /v1/embeddings request; return normalised vectors."""
    url = endpoint.rstrip("/") + "/embeddings"
    where = safe_url(url)
    body = _fetch(url, where, json.dumps({"model": model, "input": texts}).encode("utf-8"), timeout)

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or len(data) != len(texts):
        got = len(data) if isinstance(data, list) else "no"
        raise EmbedUnavailable(f"{where}: expected {len(texts)} embeddings, got {got}")

    vectors = []
    for item in _ordered(data, len(texts), where):
        values = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(values, list) or not values or len(values) > notes_embed_cache.MAX_DIMS:
            raise EmbedUnavailable(f"{where}: malformed embedding in response")
        try:
            vectors.append(notes_embed_cache.normalize(values))
        except (TypeError, OverflowError) as exc:
            raise EmbedUnavailable(f"{where}: non-numeric embedding in response") from exc
    return vectors
