import gzip
import http.client
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from solarbridge.http import AppContext, DashboardServer, _auto_period, allowlist_allows
from solarbridge.poller import EventHub
from solarbridge.receiver import MasterState
from solarbridge.storage import Storage
from tests.helpers import make_settings, snapshot

TOKEN = "test-ingest-token-123"


class FakePoller:
    def __init__(self):
        self.status = "online"
        self.events = EventHub()

    def latest(self):
        return None

    def health(self):
        return {"status": self.status, "storage": {"sample_count": 0}}


class HttpTests(unittest.TestCase):
    def test_auto_period_uses_fine_resolution_for_short_ranges(self):
        self.assertEqual(_auto_period(3600), "minute")
        self.assertEqual(_auto_period(24 * 3600), "30m")
        self.assertEqual(_auto_period(7 * 86400), "day")

    def test_allowlist_matches_ips_and_cidrs(self):
        self.assertTrue(allowlist_allows((), "1.2.3.4"))
        self.assertTrue(allowlist_allows(("10.0.0.0/8", "1.2.3.4"), "10.9.9.9"))
        self.assertTrue(allowlist_allows(("10.0.0.0/8", "1.2.3.4"), "1.2.3.4"))
        self.assertFalse(allowlist_allows(("10.0.0.0/8",), "192.168.0.1"))
        self.assertFalse(allowlist_allows(("bogus",), "10.0.0.1"))

    def test_healthz_reports_readiness_and_security_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port = self._start_server(directory)
            url = f"http://127.0.0.1:{port}"
            try:
                with urllib.request.urlopen(f"{url}/healthz", timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("Content-Security-Policy", response.headers)
                    # Loopback is a trustworthy origin: COOP must still be sent.
                    self.assertIn("Cross-Origin-Opener-Policy", response.headers)
            finally:
                self._stop(server, thread)

    def test_current_payload_accepts_hoststats_instance(self):
        # Regression: main.py wires HostStats(...).snapshot (a bound method)
        # into AppContext.host_provider; /api/current must not crash on it.
        from solarbridge.hoststats import HostStats

        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            context = AppContext(
                settings=settings,
                storage=Storage(settings.db_path),
                poller=FakePoller(),
                host_provider=HostStats(Path(directory)).snapshot,
            )
            server = DashboardServer(("127.0.0.1", 0), context)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/api/current", timeout=3
                ) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertIn("host", payload)
                    self.assertEqual(payload["host"]["master_id"], settings.master_id)
                    self.assertIn("service_uptime_s", payload["host"])
            finally:
                self._stop(server, thread)

    def test_events_stream_sends_initial_snapshot(self):
        # Regression: the SSE handshake referenced a removed helper; the
        # initial snapshot must arrive as an "event: snapshot" line.
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            poller = FakePoller()
            poller.latest = lambda: snapshot("2026-11-14T20:00:00Z", 750)
            context = AppContext(settings=settings, storage=Storage(settings.db_path), poller=poller)
            server = DashboardServer(("127.0.0.1", 0), context)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                conn.request("GET", "/api/events")
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                first_line = response.readline()
                self.assertIn(b"retry", first_line)
                # Skip the blank line after "retry"; the next event is the initial snapshot.
                while True:
                    line = response.readline()
                    if line.strip() and not line.startswith(b":"):
                        break
                self.assertIn(b"event: snapshot", line)
                data_line = response.readline()
                self.assertIn(b"load_power_w", data_line)
                conn.close()
            finally:
                self._stop(server, thread)

    def test_coop_header_sent_only_for_trustworthy_origins(self):
        # Browsers ignore COOP over plain HTTP from a LAN address and log a
        # console warning; the server must skip the header there, but keep it
        # when the request arrives through an HTTPS-terminating reverse proxy.
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port = self._start_server(directory)
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("GET", "/healthz", headers={"Host": "192.168.1.50:8080"})
                response = conn.getresponse()
                response.read()
                self.assertEqual(response.status, 200)
                self.assertNotIn("Cross-Origin-Opener-Policy", response.headers)
                self.assertIn("Content-Security-Policy", response.headers)
                self.assertIn("X-Content-Type-Options", response.headers)
                conn.close()

                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request(
                    "GET",
                    "/healthz",
                    headers={"Host": "192.168.1.50:8080", "X-Forwarded-Proto": "https"},
                )
                response = conn.getresponse()
                response.read()
                self.assertIn("Cross-Origin-Opener-Policy", response.headers)
                conn.close()
            finally:
                self._stop(server, thread)

    # ------------------------------------------------------------------ ingest

    def _start_receiver(self, directory: str, **overrides):
        settings = make_settings(Path(directory), source_mode="ingest", ingest_token=TOKEN, **overrides)
        storage = Storage(settings.db_path, master_id="testmaster")
        master_state = MasterState(storage, offline_after_s=settings.offline_after_s)
        context = AppContext(settings=settings, storage=storage, master_state=master_state)
        server = DashboardServer(("127.0.0.1", 0), context)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, server.server_address[1], storage, master_state

    @staticmethod
    def _stop(server, thread) -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    def _post_json(self, port: int, path: str, payload: dict, token: str | None = TOKEN,
                   compress: bool = True) -> tuple[int, dict | None]:
        body = json.dumps(payload).encode("utf-8")
        if compress:
            body = gzip.compress(body)
        headers = {"Content-Type": "application/json"}
        if compress:
            headers["Content-Encoding"] = "gzip"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        return response.status, parsed

    def test_ingest_requires_bearer_token(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, _ = self._start_receiver(directory)
            try:
                status, _body = self._post_json(port, "/api/ingest/hello", {"schema_version": 1}, token=None)
                self.assertEqual(status, 401)
                status, _body = self._post_json(port, "/api/ingest/hello", {"schema_version": 1}, token="wrong")
                self.assertEqual(status, 401)
            finally:
                self._stop(server, thread)

    def test_ingest_rejects_disallowed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, _ = self._start_receiver(
                directory, ingest_allowlist=("10.0.0.0/8",)
            )
            try:
                status, _body = self._post_json(port, "/api/ingest/hello", {"schema_version": 1})
                self.assertEqual(status, 403)
            finally:
                self._stop(server, thread)

    def test_rate_limits_repeated_auth_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, _ = self._start_receiver(directory)
            try:
                codes = []
                for _ in range(35):
                    status, _body = self._post_json(
                        port, "/api/ingest/hello", {"schema_version": 1}, token="bad"
                    )
                    codes.append(status)
                self.assertIn(429, codes)
                self.assertEqual(codes[-1], 429)
            finally:
                self._stop(server, thread)

    def test_hello_handshake_and_schema_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, _ = self._start_receiver(directory)
            try:
                storage.insert_sample(snapshot("2026-09-02T10:00:00Z", 100), master_id="m1")
                status, body = self._post_json(
                    port, "/api/ingest/hello",
                    {"master_id": "m1", "app_version": "0.1.0", "schema_version": 1},
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["last_sample_ts"], 1788343200)
                self.assertEqual(body["min_supported"], 1)

                conflict_status, conflict_body = self._post_json(
                    port, "/api/ingest/hello",
                    {"master_id": "m1", "schema_version": 99},
                )
                self.assertEqual(conflict_status, 409)
                self.assertEqual(conflict_body["error"], "schema_too_new")
            finally:
                self._stop(server, thread)

    def test_frames_idempotent_with_battery_and_unknown_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, master_state = self._start_receiver(directory)
            try:
                frame = {
                    "captured_at": "2026-09-02T10:00:00Z",
                    "captured_ts": 1788343200,
                    "inverter": snapshot("2026-09-02T10:00:00Z", 150),
                    "battery": {
                        "modules": [
                            {"module_index": 1, "module_serial": "LPR-1",
                             "metrics": {"soc_percent": 75, "voltage_v": 52.4},
                             "payload": {"cells_v": [3.2, 3.3]}},
                        ]
                    },
                    "future_section": {"anything": True},
                }
                payload = {"master_id": "m1", "app_version": "0.1.0", "schema_version": 1,
                           "frames": [frame]}
                status, body = self._post_json(port, "/api/ingest/frames", payload)
                self.assertEqual(status, 200)
                self.assertEqual(body["accepted"], 1)
                self.assertEqual(body["duplicates"], 0)

                status, body = self._post_json(port, "/api/ingest/frames", payload)
                self.assertEqual(body["accepted"], 0)
                self.assertEqual(body["duplicates"], 1)
                self.assertEqual(body["last_sample_ts"], 1788343200)

                self.assertEqual(storage.stats()["sample_count"], 1)
                self.assertEqual(storage.stats()["battery_row_count"], 1)
                stored = storage.latest_payload()
                self.assertEqual(stored["_extra_sections"]["future_section"]["anything"], True)
                self.assertIsNotNone(master_state.snapshot()["master_id"])
            finally:
                self._stop(server, thread)

    def test_heartbeat_updates_master_state(self):
        with tempfile.TemporaryDirectory() as directory:
            server, thread, port, storage, master_state = self._start_receiver(directory)
            try:
                heartbeat = {
                    "master_id": "m1", "app_version": "0.1.0", "schema_version": 1,
                    "uptime_s": 100, "last_frame_ts": None,
                    "bus": {"inverter": {"ok": True, "last_error": None, "consecutive_errors": 0}},
                }
                status, _body = self._post_json(port, "/api/ingest/heartbeat", heartbeat)
                self.assertEqual(status, 200)
                snap = master_state.snapshot()
                self.assertEqual(snap["master_state"], "alive")
                self.assertEqual(snap["status"], "online")
                self.assertIn("events", json.loads(
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/master", timeout=3).read()
                ))
            finally:
                self._stop(server, thread)

    # ------------------------------------------------------------------ seed

    def test_seed_download_token_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), source_mode="ingest", ingest_token=TOKEN)
            storage = Storage(settings.db_path, master_id="testmaster")
            seed_id, gz_path, passport = self._make_seed(Path(directory))
            storage.add_seed_token("seedtok", seed_id, "vps1", ttl_hours=2, max_downloads=10)
            server = DashboardServer(("127.0.0.1", 0), AppContext(settings=settings, storage=storage))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            try:
                url = f"http://127.0.0.1:{port}/api/seed/download/{seed_id}"
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(url, timeout=3)
                self.assertEqual(raised.exception.code, 403)
                raised.exception.close()

                with urllib.request.urlopen(f"{url}?t=seedtok", timeout=3) as response:
                    payload = response.read()
                self.assertEqual(payload, gz_path.read_bytes())

                passport_url = f"http://127.0.0.1:{port}/api/seed/passport/{seed_id}?t=seedtok"
                with urllib.request.urlopen(passport_url, timeout=3) as response:
                    data = json.loads(response.read())
                self.assertEqual(data["seed_id"], seed_id)
                self.assertEqual(data["sha256"], passport["sha256"])

                with urllib.request.urlopen(f"{url}?t=bogus", timeout=3) as response:
                    response.read()
                self.fail("expected 403 for bogus token")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 403)
                exc.close()
            finally:
                self._stop(server, thread)

    @staticmethod
    def _make_seed(directory: Path):
        from solarbridge.seed import create_seed
        from solarbridge.storage import Storage

        db_path = directory / "master.sqlite3"
        store = Storage(db_path, master_id="m1")
        store.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
        store.insert_sample(snapshot("2026-09-02T10:01:00Z", 200))
        return create_seed(db_path, "m1", directory / "seeds", compact_days=None)

    # ------------------------------------------------------------------ helpers

    def test_current_payload_carries_battery_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            storage = Storage(settings.db_path)
            poller = FakePoller()
            server = DashboardServer(("127.0.0.1", 0), AppContext(settings, storage, poller))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}"
                with urllib.request.urlopen(f"{url}/api/current", timeout=3) as response:
                    payload = json.loads(response.read())
                self.assertNotIn("battery", payload)

                modules = [{
                    "module_index": 2, "module_serial": "LPR-A",
                    "metrics": {"soc_percent": 58.2, "voltage_v": 52.926, "current_a": 1.69},
                    "payload": {"protocol": "paceic-ascii/v25"},
                }]
                storage.insert_battery_frame("2026-11-13T10:00:00Z", 1763028000, modules)
                with urllib.request.urlopen(f"{url}/api/current", timeout=3) as response:
                    payload = json.loads(response.read())
                battery = payload["battery"]
                self.assertEqual(battery["captured_ts"], 1763028000)
                self.assertEqual(battery["modules"][0]["module_index"], 2)
                self.assertEqual(battery["modules"][0]["metrics"]["soc_percent"], 58.2)
            finally:
                self._stop(server, thread)

    def _start_server(self, directory: str):
        settings = make_settings(Path(directory))
        poller = FakePoller()
        server = DashboardServer(("127.0.0.1", 0), AppContext(settings, Storage(settings.db_path), poller))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, server.server_address[1]


if __name__ == "__main__":
    unittest.main()
