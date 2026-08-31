#!/usr/bin/env python3

"""Tests for bin/notes_embed_client.

These run the real HTTP path against a loopback stub server rather than a fake
embedder, so the request shape and every response-parsing branch are actually
executed. No vault is touched and nothing leaves the machine.
"""

import contextlib
import json
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes_embed_cache
import notes_embed_client


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        self.server.requests.append({"path": self.path, "body": parsed, "headers": dict(self.headers)})

        status, payload = self.server.reply
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def stub_server(status=200, payload=None):
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.reply = (status, payload if payload is not None else {"data": []})
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def embeddings(*vectors):
    return {"data": [{"index": i, "embedding": list(v)} for i, v in enumerate(vectors)]}


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RequestShapeTests(unittest.TestCase):
    def test_posts_model_and_a_list_of_inputs_to_v1_embeddings(self):
        with stub_server(200, embeddings([3.0, 4.0], [1.0, 0.0])) as (url, server):
            notes_embed_client.embed_batch(["one", "two"], url, "some-model")
        request = server.requests[0]
        self.assertEqual(request["path"], "/v1/embeddings")
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        self.assertEqual(request["body"]["model"], "some-model")
        # A list, not a bare string: servers differ here and a regression would be invisible.
        self.assertEqual(request["body"]["input"], ["one", "two"])

    def test_trailing_slash_on_the_endpoint_does_not_double_up(self):
        with stub_server(200, embeddings([1.0])) as (url, server):
            notes_embed_client.embed_batch(["one"], url + "/", "m")
        self.assertEqual(server.requests[0]["path"], "/v1/embeddings")

    def test_vectors_are_returned_normalised(self):
        with stub_server(200, embeddings([3.0, 4.0])) as (url, _):
            vectors = notes_embed_client.embed_batch(["one"], url, "m")
        self.assertEqual(len(vectors), 1)
        self.assertAlmostEqual(list(vectors[0])[0], 0.6, places=5)
        self.assertAlmostEqual(list(vectors[0])[1], 0.8, places=5)

    def test_out_of_order_responses_are_realigned_to_the_input_order(self):
        payload = {"data": [
            {"index": 1, "embedding": [0.0, 1.0]},
            {"index": 0, "embedding": [1.0, 0.0]},
        ]}
        with stub_server(200, payload) as (url, _):
            vectors = notes_embed_client.embed_batch(["first", "second"], url, "m")
        self.assertEqual(list(vectors[0]), [1.0, 0.0])
        self.assertEqual(list(vectors[1]), [0.0, 1.0])


class ResponseFailureTests(unittest.TestCase):
    def assert_unavailable(self, status, payload, texts=("one",)):
        with stub_server(status, payload) as (url, _):
            with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
                notes_embed_client.embed_batch(list(texts), url, "m")
        return str(caught.exception)

    def test_http_error_status_is_reported(self):
        message = self.assert_unavailable(404, {"error": "model not found"})
        self.assertIn("HTTP 404", message)

    def test_duplicate_indices_are_rejected(self):
        payload = {"data": [
            {"index": 0, "embedding": [1.0]},
            {"index": 0, "embedding": [1.0]},
        ]}
        self.assertIn("indices", self.assert_unavailable(200, payload, ["a", "b"]))

    def test_wrong_number_of_embeddings_is_rejected(self):
        self.assertIn("expected 2", self.assert_unavailable(200, embeddings([1.0]), ["a", "b"]))

    def test_missing_data_key_is_rejected(self):
        self.assert_unavailable(200, {"nope": []})

    def test_empty_embedding_is_rejected(self):
        self.assert_unavailable(200, {"data": [{"index": 0, "embedding": []}]})

    def test_non_numeric_embedding_is_rejected(self):
        self.assert_unavailable(200, {"data": [{"index": 0, "embedding": ["not a number"]}]})

    def test_oversized_embedding_is_rejected(self):
        huge = [1.0] * (notes_embed_cache.MAX_DIMS + 1)
        self.assert_unavailable(200, {"data": [{"index": 0, "embedding": huge}]})

    def test_non_json_body_is_rejected(self):
        self.assert_unavailable(200, b"<html>not json</html>")

    def test_connection_refused_is_reported_not_raised_raw(self):
        url = f"http://127.0.0.1:{closed_port()}/v1"
        with self.assertRaises(notes_embed_cache.EmbedUnavailable):
            notes_embed_client.embed_batch(["one"], url, "m")


class RedirectTests(unittest.TestCase):
    """A 3xx would send the next request somewhere validate_endpoint never approved."""

    def test_a_redirect_is_refused_rather_than_followed(self):
        class Redirector(_Handler):
            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:9/exfil/embeddings")
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = HTTPServer(("127.0.0.1", 0), Redirector)
        server.reply = (302, {})
        server.requests = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1"
            with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
                notes_embed_client.embed_batch(["secret note text"], url, "m")
            self.assertIn("302", str(caught.exception))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class ErrorBodyBoundTests(unittest.TestCase):
    def test_a_large_error_body_is_not_read_whole_into_the_message(self):
        payload = json.dumps({"error": "x" * 200_000}).encode("utf-8")
        with stub_server(500, payload) as (url, _):
            with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
                notes_embed_client.embed_batch(["one"], url, "m")
        self.assertLess(len(str(caught.exception)), 400)


class EndpointValidationTests(unittest.TestCase):
    def test_loopback_names_and_addresses_are_allowed(self):
        for endpoint in ("http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://[::1]:1234/v1"):
            notes_embed_client.validate_endpoint(endpoint, allow_remote=False)

    def test_remote_host_is_refused_without_the_opt_in(self):
        with self.assertRaises(ValueError) as caught:
            notes_embed_client.validate_endpoint("https://embeddings.example.com/v1", allow_remote=False)
        self.assertIn("--allow-remote-endpoint", str(caught.exception))

    def test_remote_host_is_permitted_with_the_opt_in(self):
        notes_embed_client.validate_endpoint("https://embeddings.example.com/v1", allow_remote=True)

    def test_non_http_scheme_is_refused(self):
        for endpoint in ("file:///etc/passwd", "ftp://host/v1", "gopher://host"):
            with self.assertRaises(ValueError):
                notes_embed_client.validate_endpoint(endpoint, allow_remote=True)

    def test_endpoint_without_a_host_is_refused(self):
        with self.assertRaises(ValueError):
            notes_embed_client.validate_endpoint("http:///v1", allow_remote=True)


class SafeUrlTests(unittest.TestCase):
    def test_credentials_are_stripped(self):
        safe = notes_embed_client.safe_url("https://user:secret@host.example/v1/embeddings")
        self.assertNotIn("secret", safe)
        self.assertNotIn("user", safe)
        self.assertIn("host.example", safe)

    def test_query_and_fragment_are_stripped(self):
        safe = notes_embed_client.safe_url("https://host/v1?api_key=SECRET#frag")
        self.assertNotIn("SECRET", safe)
        self.assertNotIn("frag", safe)

    def test_port_is_kept(self):
        self.assertIn(":11434", notes_embed_client.safe_url("http://localhost:11434/v1"))

    def test_control_characters_are_stripped(self):
        self.assertNotIn("\x1b", notes_embed_client.safe_url("http://host/v1\x1b[31m"))


class ErrorTextTests(unittest.TestCase):
    def test_server_error_body_cannot_drive_the_terminal(self):
        with stub_server(400, b'{"error": "\\u001b[31mred\\u0007"}') as (url, _):
            with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
                notes_embed_client.embed_batch(["one"], url, "m")
        message = str(caught.exception)
        self.assertNotIn("\x1b", message)
        self.assertNotIn("\x07", message)

    def test_endpoint_credentials_do_not_leak_into_errors(self):
        url = f"http://user:hunter2@127.0.0.1:{closed_port()}/v1"
        with self.assertRaises(notes_embed_cache.EmbedUnavailable) as caught:
            notes_embed_client.embed_batch(["one"], url, "m")
        self.assertNotIn("hunter2", str(caught.exception))


class JsonConstantTests(unittest.TestCase):
    """Python's json accepts the non-standard NaN/Infinity literals by default."""

    def test_nan_literal_is_refused(self):
        with self.assertRaises(notes_embed_client.EmbedUnavailable):
            json.loads('{"embedding": [NaN]}', parse_constant=notes_embed_client._reject_constant)

    def test_infinity_literals_are_refused(self):
        for literal in ("Infinity", "-Infinity"):
            with self.assertRaises(notes_embed_client.EmbedUnavailable):
                json.loads(
                    '{"embedding": [%s]}' % literal,
                    parse_constant=notes_embed_client._reject_constant,
                )

    def test_ordinary_json_still_parses(self):
        parsed = json.loads(
            '{"embedding": [1.0, -2.5]}', parse_constant=notes_embed_client._reject_constant
        )
        self.assertEqual(parsed["embedding"], [1.0, -2.5])


if __name__ == "__main__":
    unittest.main()
