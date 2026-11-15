import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from solarbridge.auth import AuthStore
from solarbridge.config import random_master_suffix
from solarbridge.hoststats import DiskGuard
from solarbridge.http import AppContext, DashboardServer
from solarbridge.storage import Storage
from tests.helpers import make_settings, snapshot


class AuthStoreTests(unittest.TestCase):
    def test_verify_reads_user_list_and_is_editable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user_list"
            path.write_text("# comment\nadmin:secret123\n", encoding="utf-8")
            store = AuthStore(path, Path(directory) / "tokens.json")
            self.assertTrue(store.verify("admin", "secret123"))
            self.assertFalse(store.verify("admin", "wrong"))
            self.assertFalse(store.verify("ghost", "secret123"))
            path.write_text("admin:newpass\n", encoding="utf-8")
            self.assertFalse(store.verify("admin", "secret123"))
            self.assertTrue(store.verify("admin", "newpass"))

    def test_tokens_survive_restart_and_expire(self):
        with tempfile.TemporaryDirectory() as directory:
            tokens_path = Path(directory) / "tokens.json"
            store = AuthStore(Path(directory) / "user_list", tokens_path)
            token = store.issue_token("admin")
            self.assertEqual(store.validate_token(token), "admin")
            # A second instance models the service restart.
            store2 = AuthStore(Path(directory) / "user_list", tokens_path)
            self.assertEqual(store2.validate_token(token), "admin")
            self.assertIsNone(store2.validate_token("bogus"))
            # Expired entries are rejected and pruned on the next issue.
            data = json.loads(tokens_path.read_text(encoding="utf-8"))
            data[token]["expires_ts"] = int(time.time()) - 10
            tokens_path.write_text(json.dumps(data), encoding="utf-8")
            store3 = AuthStore(Path(directory) / "user_list", tokens_path)
            self.assertIsNone(store3.validate_token(token))
            store3.issue_token("admin")
            self.assertNotIn(token, json.loads(tokens_path.read_text(encoding="utf-8")))

    def test_random_master_suffix_shape(self):
        suffix = random_master_suffix()
        self.assertEqual(len(suffix), 8)
        self.assertTrue(all(ch in "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ" for ch in suffix))
        self.assertNotEqual(suffix, random_master_suffix())


class DiskGuardTests(unittest.TestCase):
    def test_pauses_below_threshold_and_disables_at_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = DiskGuard(Path(directory), min_free_percent=101.0)  # always above threshold
            self.assertTrue(guard.status()["paused"])
            guard_off = DiskGuard(Path(directory), min_free_percent=0.0)
            self.assertFalse(guard_off.status()["paused"])
            guard_lenient = DiskGuard(Path(directory), min_free_percent=0.1)
            self.assertFalse(guard_lenient.status()["paused"])
            self.assertIsInstance(guard_lenient.status()["free_percent"], float)


class StorageRestoreTests(unittest.TestCase):
    def test_restore_copies_frames_with_master_id_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Storage(Path(directory) / "receiver.sqlite3", master_id="rx-master")
            source.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
            source.insert_sample(snapshot("2026-09-02T11:00:00Z", 200))
            source.insert_battery_frame(
                "2026-09-02T11:00:00Z", 1788356400,
                [{"module_index": 2, "module_serial": "S2", "payload": {"soc": 42}}],
            )
            target = Storage(Path(directory) / "master.sqlite3", master_id="pi-master")
            result = target.restore_from_db(Path(directory) / "receiver.sqlite3")
            self.assertEqual(result["inserted"], 2)
            self.assertEqual(result["skipped"], 0)
            rows = target.frames_after(0, 10, "pi-master")
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["snapshot"]["metrics"]["load_power_w"], 100)
            self.assertEqual(target.battery_row_count(), 1)

    def test_restore_is_idempotent_and_respects_range(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Storage(Path(directory) / "rx.sqlite3", master_id="rx")
            source.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
            source.insert_sample(snapshot("2026-09-02T11:00:00Z", 200))
            source.insert_sample(snapshot("2026-09-02T12:00:00Z", 300))
            target = Storage(Path(directory) / "master.sqlite3", master_id="pi")
            source_path = Path(directory) / "rx.sqlite3"
            first = target.restore_from_db(source_path)
            self.assertEqual(first["inserted"], 3)
            second = target.restore_from_db(source_path)
            self.assertEqual(second["inserted"], 0)
            self.assertEqual(second["skipped"], 3)
            # Only the 11:00Z frame falls inside [10:30Z .. 11:30Z].
            from datetime import datetime, timezone as tz

            def epoch(hour, minutes=0):
                return int(datetime(2026, 9, 2, hour, minutes, tzinfo=tz.utc).timestamp())

            partial = Storage(Path(directory) / "master2.sqlite3", master_id="pi")
            info = partial.restore_from_db(source_path, since_ts=epoch(10, 30), until_ts=epoch(11, 30))
            self.assertEqual(info["inserted"], 1)
            rows = partial.frames_after(0, 10, "pi")
            self.assertEqual(rows[0]["snapshot"]["metrics"]["load_power_w"], 200)

    def test_missing_source_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            with self.assertRaises(FileNotFoundError):
                store.restore_from_db(Path(directory) / "nope.sqlite3")

    def test_battery_frames_carry_metrics_for_receiver_roundtrip(self):
        """Regression: forwarded battery modules must include the metrics dict.

        On the master, battery_frames_after() shapes what /api/ingest/frames
        carries; the receiver stores it via insert_battery_frame, which fills
        the metric columns from module["metrics"]. Without those keys the
        receiver dashboard shows empty cards while "Details" (payload) still
        has data."""
        with tempfile.TemporaryDirectory() as directory:
            master = Storage(Path(directory) / "master.sqlite3", master_id="pi")
            master.insert_battery_frame(
                "2026-11-15T10:00:00Z", 1763200800,
                [{
                    "module_index": 2,
                    "module_serial": "PY4850G-M01",
                    "metrics": {
                        "soc_percent": 63.3, "voltage_v": 52.49, "current_a": -8.7,
                        "temp_min_c": 21.0, "temp_max_c": 29.0,
                        "cell_voltage_min_v": 3.345, "cell_voltage_max_v": 3.353,
                        "cell_delta_v": 0.008, "soh_percent": 98.0, "cycles": 431,
                        "protection_bits": 0, "alarm_bits": 0,
                    },
                    "payload": {"protocol": "PYLON_V3.3", "soc": 633},
                }],
            )
            forwarded = master.battery_frames_after(0, 100, "pi")
            modules = forwarded[1763200800]
            self.assertEqual(modules[0]["metrics"]["soc_percent"], 63.3)
            self.assertEqual(modules[0]["metrics"]["voltage_v"], 52.49)

            # Receiver side: same call the ingest handler makes.
            receiver = Storage(Path(directory) / "receiver.sqlite3", master_id="pi")
            receiver.insert_battery_frame(
                "2026-11-15T10:00:00Z", 1763200800, modules, master_id="pi"
            )
            frame = receiver.latest_battery_frame()
            self.assertIsNotNone(frame)
            metrics = frame["modules"][0]["metrics"]
            self.assertEqual(metrics["soc_percent"], 63.3)
            self.assertEqual(metrics["voltage_v"], 52.49)
            self.assertEqual(metrics["cycles"], 431)
            self.assertEqual(metrics["cell_delta_v"], 0.008)
            self.assertEqual(frame["modules"][0]["payload"]["protocol"], "PYLON_V3.3")

    def test_purge_before_deletes_and_frees(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.insert_sample(snapshot("2026-01-02T10:00:00Z", 100))
            store.insert_sample(snapshot("2026-03-02T10:00:00Z", 200))
            result = store.purge_before(1788340000)  # ~2026-06-02: deletes everything
            self.assertEqual(result["samples"], 2)
            self.assertEqual(store.stats()["sample_count"], 0)


class AuthHttpTests(unittest.TestCase):
    def _server(self, directory: str, user_list: Path):
        settings = make_settings(Path(directory))
        context = AppContext(
            settings=settings,
            storage=Storage(settings.db_path),
            auth_store=AuthStore(user_list, Path(directory) / "data" / "tokens.json"),
        )
        server = DashboardServer(("127.0.0.1", 0), context)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, server.server_address[1]

    def _request(self, port: int, method: str, path: str, body: dict | None = None, token: str | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Auth-Token"] = token
        connection.request(method, path, json.dumps(body or {}), headers)
        response = connection.getresponse()
        raw = response.read()
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {"_raw": raw[:50].decode("utf-8", "replace")}
        status = response.status
        connection.close()
        return status, payload

    def test_login_flow_protects_api(self):
        with tempfile.TemporaryDirectory() as directory:
            user_list = Path(directory) / "user_list"
            user_list.write_text("admin:secret\n", encoding="utf-8")
            server, port = self._server(directory, user_list)
            try:
                # Data endpoints are closed without a token.
                status, _ = self._request(port, "GET", "/api/current")
                self.assertEqual(status, 401)
                status, body = self._request(port, "GET", "/api/auth/status")
                self.assertEqual(status, 200)
                self.assertTrue(body["auth_required"])
                self.assertFalse(body["authenticated"])
                # Bad credentials -> 401; healthz and pages stay open.
                status, _ = self._request(port, "POST", "/api/auth/login",
                                          {"login": "admin", "password": "wrong"})
                self.assertEqual(status, 401)
                status, _ = self._request(port, "GET", "/healthz")
                self.assertEqual(status, 200)
                status, _ = self._request(port, "GET", "/")
                self.assertEqual(status, 200)
                # Correct credentials issue a working token.
                status, body = self._request(port, "POST", "/api/auth/login",
                                             {"login": "admin", "password": "secret"})
                self.assertEqual(status, 200)
                self.assertTrue(body["token"])
                status, _ = self._request(port, "GET", "/api/current", token=body["token"])
                self.assertEqual(status, 200)
                # The status endpoint now reports authenticated for the token.
                status, body = self._request(port, "GET", "/api/auth/status", token=body["token"])
                self.assertTrue(body["authenticated"])
            finally:
                server.shutdown()
                server.server_close()

    def test_auth_disabled_leaves_everything_open(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            server = DashboardServer(("127.0.0.1", 0), AppContext(settings, Storage(settings.db_path)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, body = self._request(server.server_address[1], "GET", "/api/auth/status")
                self.assertEqual(status, 200)
                self.assertFalse(body["auth_required"])
                status, _ = self._request(server.server_address[1], "GET", "/api/current")
                self.assertEqual(status, 200)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
