"""Tests for the bounded HTTP helper. Stdlib only: `python3 -m unittest`.

Run from the scripts/ directory:
    python3 -m unittest common.test_http_fetch -v

The interesting cases are all about time, so they use a local TLS server for
the success paths and a blackholed RFC1918 address (10.255.255.1, which drops
SYN rather than refusing it) for the "dead route" paths. Nothing here touches a
real provider.
"""

from __future__ import annotations

import http.server
import json
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from common import http_fetch
from common.http_fetch import FetchError, fetch_bytes, fetch_json

# Drops SYN instead of sending RST, so a connect attempt burns its full budget.
BLACKHOLE = "10.255.255.1"


def _self_signed(directory: Path) -> tuple[Path, Path]:
    """Generate a throwaway cert for localhost via the system openssl."""
    key = directory / "key.pem"
    cert = directory / "cert.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return key, cert


class _Handler(http.server.BaseHTTPRequestHandler):
    """Serves whatever the test class put in `script`. Silent logging."""

    routes: dict = {}

    def log_message(self, *_args):  # noqa: D102 - quiet test output
        pass

    def do_GET(self):  # noqa: N802 - stdlib naming
        status, headers, body, delay = self.routes.get(
            self.path, (404, {}, b"{}", 0.0)
        )
        if delay:
            time.sleep(delay)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TLSServerCase(unittest.TestCase):
    """Base class that boots a local HTTPS server the helper can really talk to."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        key, cert = _self_signed(Path(cls._tmp.name))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(cert, key)
        cls.server.socket = ctx.wrap_socket(cls.server.socket, server_side=True)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        # Trust the throwaway cert for the duration of the test run. Patching
        # the module's context factory keeps the change scoped to these tests.
        client_ctx = ssl.create_default_context(cafile=str(cert))
        cls._real_ctx = ssl.create_default_context
        ssl.create_default_context = lambda *a, **k: client_ctx

    @classmethod
    def tearDownClass(cls):
        ssl.create_default_context = cls._real_ctx
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def setUp(self):
        _Handler.routes = {}

    def url(self, path: str) -> str:
        return f"https://localhost:{self.port}{path}"

    def route(self, path, *, status=200, body=b"{}", headers=None, delay=0.0):
        _Handler.routes[path] = (status, headers or {"Content-Type": "application/json"}, body, delay)


class TestSuccessPaths(TLSServerCase):
    def test_fetch_json_returns_decoded_payload(self):
        self.route("/ok", body=json.dumps({"events": [{"idEvent": "1"}]}).encode())

        payload = fetch_json(self.url("/ok"), timeout=10)

        self.assertEqual(payload["events"][0]["idEvent"], "1")

    def test_oversize_response_is_rejected_not_truncated(self):
        # Silently truncating would hand the caller a half payload that fails
        # JSON parsing with a misleading "malformed" error.
        self.route("/big", body=b"x" * 5000)

        with self.assertRaises(FetchError) as caught:
            fetch_bytes(self.url("/big"), timeout=10, max_bytes=1000)
        self.assertEqual(caught.exception.kind, "too_large")

    def test_non_200_is_an_http_error_carrying_the_status(self):
        self.route("/nope", status=503, body=b"{}")

        with self.assertRaises(FetchError) as caught:
            fetch_bytes(self.url("/nope"), timeout=10)
        self.assertEqual(caught.exception.kind, "http")
        self.assertEqual(caught.exception.status, 503)

    def test_malformed_json_is_reported_as_malformed(self):
        self.route("/bad", body=b"not json")

        with self.assertRaises(FetchError) as caught:
            fetch_json(self.url("/bad"), timeout=10)
        self.assertEqual(caught.exception.kind, "malformed")

    def test_same_host_redirect_is_followed(self):
        self.route("/from", status=302, headers={"Location": "/to"})
        self.route("/to", body=json.dumps({"ok": True}).encode())

        self.assertEqual(fetch_json(self.url("/from"), timeout=10), {"ok": True})

    def test_cross_host_redirect_is_refused(self):
        # A provider-side change must not be able to steer a reviewed request
        # at an unreviewed host.
        self.route("/away", status=302, headers={"Location": "https://example.com/x"})

        with self.assertRaises(FetchError) as caught:
            fetch_bytes(self.url("/away"), timeout=10)
        self.assertEqual(caught.exception.kind, "http")
        self.assertIn("cross-host", caught.exception.detail)

    def test_redirect_loop_terminates(self):
        self.route("/loop", status=302, headers={"Location": "/loop"})

        with self.assertRaises(FetchError) as caught:
            fetch_bytes(self.url("/loop"), timeout=10)
        self.assertEqual(caught.exception.kind, "http")

    def test_slow_response_body_hits_the_deadline_not_the_default(self):
        self.route("/slow", body=b"{}", delay=3.0)

        started = time.monotonic()
        with self.assertRaises(FetchError) as caught:
            fetch_bytes(self.url("/slow"), timeout=1.5)
        elapsed = time.monotonic() - started

        self.assertEqual(caught.exception.kind, "timeout")
        self.assertLess(elapsed, 3.0, f"waited {elapsed:.2f}s past its 1.5s budget")

    def test_plain_http_is_refused(self):
        with self.assertRaises(FetchError) as caught:
            fetch_bytes("http://localhost/x", timeout=5)
        self.assertEqual(caught.exception.kind, "connect")

    def test_response_headers_are_returned_lowercased(self):
        # odds_data.py reads quota out of these; providers are free to change
        # header casing, so the lookup must not depend on it.
        self.route(
            "/quota",
            body=json.dumps([]).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Requests-Remaining": "412",
            },
        )

        payload, received = http_fetch.fetch_json_with_headers(
            self.url("/quota"), timeout=10
        )

        self.assertEqual(payload, [])
        self.assertEqual(received["x-requests-remaining"], "412")


class TestDeadRouteHandling(TLSServerCase):
    """The bug this module exists for: multi-address hosts with a dead route.

    urlopen hands its timeout to every address in turn, so N dead addresses
    cost N x timeout. These tests pin the two properties that fixes it: the
    caller's timeout is the real ceiling, and a live address behind dead ones
    still gets reached quickly.
    """

    def _resolve_to(self, *addresses):
        """Force _addresses to return the given (ip, port) list, in order."""
        pairs = [(socket.AF_INET, addr) for addr in addresses]
        original = http_fetch._addresses
        http_fetch._addresses = lambda host, port, deadline: list(pairs)
        self.addCleanup(lambda: setattr(http_fetch, "_addresses", original))

    def test_live_address_behind_two_dead_ones_is_reached_quickly(self):
        self.route("/ok", body=json.dumps({"ok": True}).encode())
        self._resolve_to(
            (BLACKHOLE, 443), (BLACKHOLE, 443), ("127.0.0.1", self.port)
        )

        started = time.monotonic()
        payload = fetch_json(self.url("/ok"), timeout=30)
        elapsed = time.monotonic() - started

        self.assertEqual(payload, {"ok": True})
        # Two dead addresses at the fast per-address budget, then success.
        # urlopen would have spent 30s on each dead address instead.
        self.assertLess(
            elapsed,
            2 * http_fetch.FAST_CONNECT_TIMEOUT + 5,
            f"dead routes cost {elapsed:.2f}s; per-address budget is not being applied",
        )

    def test_all_addresses_dead_respects_the_total_budget(self):
        self._resolve_to((BLACKHOLE, 443), (BLACKHOLE, 443), (BLACKHOLE, 443))

        started = time.monotonic()
        with self.assertRaises(FetchError) as caught:
            fetch_bytes("https://unreachable.invalid/x", timeout=6)
        elapsed = time.monotonic() - started

        self.assertIn(caught.exception.kind, ("timeout", "connect"))
        # The whole point: the stated timeout is the ceiling for the entire
        # call, retries included — not per address and not per attempt.
        self.assertLess(elapsed, 9.0, f"took {elapsed:.2f}s against a 6s budget")

    def test_first_address_dead_does_not_consume_the_whole_budget(self):
        self.route("/ok", body=b"{}")
        self._resolve_to((BLACKHOLE, 443), ("127.0.0.1", self.port))

        started = time.monotonic()
        fetch_bytes(self.url("/ok"), timeout=30)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, http_fetch.FAST_CONNECT_TIMEOUT + 5)


if __name__ == "__main__":
    unittest.main()
