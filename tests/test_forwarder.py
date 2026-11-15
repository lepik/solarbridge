import tempfile
import threading
import time
import unittest
from pathlib import Path

from solarbridge.forwarder import (
    Forwarder,
    ReceiverWorker,
    build_frame_payload,
    build_heartbeat,
    parse_receivers,
    reload_receivers,
)
from solarbridge.storage import Storage
from tests.helpers import make_settings, snapshot


class ParseReceiversTests(unittest.TestCase):
    def test_parses_valid_lines_with_comments_and_flags(self):
        text = "\n".join([
            "# comment",
            "",
            "vps1 | https://vps1.example.com/ | tok1 | on",
            "vps2 | http://198.51.100.7:8090 | tok2 | off",
        ])
        receivers, errors = parse_receivers(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(receivers), 2)
        self.assertEqual(receivers[0].url, "https://vps1.example.com")  # trailing / stripped
        self.assertTrue(receivers[0].enabled)
        self.assertFalse(receivers[1].enabled)

    def test_malformed_lines_are_collected_not_fatal(self):
        text = "\n".join([
            "broken-line-without-pipes",
            "vps1 | url | tok | maybe",
            " | url | tok | on",
            "dup | url | tok | on",
            "dup | url2 | tok2 | on",
        ])
        receivers, errors = parse_receivers(text)
        self.assertEqual(len(receivers), 1)
        self.assertEqual(len(errors), 4)

    def test_reload_receivers_missing_file(self):
        receivers, errors = reload_receivers("/nonexistent/receivers.list")
        self.assertEqual((receivers, errors), ([], []))


class PayloadBuilderTests(unittest.TestCase):
    def test_build_frame_payload_with_battery(self):
        rows = [
            {"captured_at": "2026-09-02T10:00:00Z", "captured_ts": 100, "snapshot": {"metrics": {}}},
            {"captured_at": "2026-09-02T10:01:00Z", "captured_ts": 160, "snapshot": {"metrics": {}}},
        ]
        battery = {100: [{"module_index": 1, "payload": {}}]}
        payload = build_frame_payload("master", "0.1.0", 1, rows, battery)
        self.assertEqual(payload["master_id"], "master")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["frames"]), 2)
        self.assertIn("battery", payload["frames"][0])
        self.assertNotIn("battery", payload["frames"][1])

    def test_build_heartbeat_bus_blocks(self):
        class FakePoller:
            def health(self):
                return {"status": "offline", "last_error": "boom", "consecutive_failures": 3,
                        "last_success_at": "2026-09-02T10:00:00Z"}

        heartbeat = build_heartbeat("master", "0.1.0", 1, 42.0, FakePoller(),
                                    battery_health={"ok": False, "modules_online": 0})
        self.assertFalse(heartbeat["bus"]["inverter"]["ok"])
        self.assertEqual(heartbeat["bus"]["inverter"]["consecutive_errors"], 3)
        self.assertEqual(heartbeat["bus"]["battery"]["modules_online"], 0)
        self.assertNotIn("host", heartbeat)

    def test_build_heartbeat_carries_host_subset(self):
        class FakePoller:
            def health(self):
                return {"status": "online"}

        heartbeat = build_heartbeat("master", "0.1.0", 1, 42.0, FakePoller(),
                                    host_stats={"cpu_temp_c": 52.4, "load_1m": 0.3,
                                                "throttled": False, "uptime_s": 120.0})
        self.assertEqual(heartbeat["host"]["cpu_temp_c"], 52.4)
        self.assertFalse(heartbeat["host"]["throttled"])
        self.assertEqual(heartbeat["host"]["load_1m"], 0.3)


class WorkerWatermarkTests(unittest.TestCase):
    def _worker(self, directory: Path, batch: int = 3):
        settings = make_settings(
            directory, forward_batch=batch, forward_pause_s=0.0, forward_backfill_days=60,
        )
        storage = Storage(settings.db_path, master_id="testmaster")
        base = int(time.time()) - 3600
        for index in range(5):
            moment = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + index * 60))
            storage.insert_sample(snapshot(moment, 100 + index), master_id="testmaster")
        worker = ReceiverWorker(
            receiver=type("R", (), {"name": "vps1", "url": "http://x", "token": "t", "enabled": True})(),
            settings=settings,
            storage=storage,
            poller=None,
            parallel_semaphore=threading.Semaphore(2),
            started_at=0.0,
        )
        return worker, storage

    def test_hello_then_batched_push_updates_watermark(self):
        with tempfile.TemporaryDirectory() as directory:
            worker, storage = self._worker(Path(directory), batch=3)
            sent: list[tuple[str, dict]] = []

            def fake_post(path, payload, expect_json=False):
                sent.append((path, payload))
                if path.endswith("hello"):
                    return {"ok": True, "last_sample_ts": None}
                frames = payload["frames"]
                newest = frames[-1]["captured_ts"]
                return {"ok": True, "accepted": len(frames), "last_sample_ts": newest}

            worker._post = fake_post
            worker._hello()
            self.assertEqual(sent[-1][0], "/api/ingest/hello")

            worker._push_frames()
            frames_sent = [payload for path, payload in sent if "frames" in path]
            self.assertEqual(len(frames_sent[0]["frames"]), 3)
            state = storage.forward_state("vps1")
            self.assertEqual(state["last_result"], "ok")
            self.assertEqual(state["sent_total"], 3)
            self.assertEqual(state["acked_total"], 3)

            worker._push_frames()
            frames_sent = [payload for path, payload in sent if "frames" in path]
            self.assertEqual(len(frames_sent[1]["frames"]), 2)
            state = storage.forward_state("vps1")
            self.assertEqual(state["sent_total"], 5)

            worker._push_frames()  # nothing new
            frames_sent = [payload for path, payload in sent if "frames" in path]
            self.assertEqual(len(frames_sent), 2)

    def test_window_limit_caps_backfill_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory), forward_backfill_days=1, forward_batch=10)
            storage = Storage(settings.db_path, master_id="testmaster")
            old_ts = int(time.time()) - 30 * 86400  # far beyond the 1-day window
            moment = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old_ts))
            storage.insert_sample(snapshot(moment, 50), master_id="testmaster")
            worker = ReceiverWorker(
                receiver=type("R", (), {"name": "vps1", "url": "http://x", "token": "t", "enabled": True})(),
                settings=settings,
                storage=storage,
                poller=None,
                parallel_semaphore=threading.Semaphore(2),
                started_at=0.0,
            )
            worker._last_acked_ts = old_ts - 100
            sent: list[tuple[str, dict]] = []

            def fake_post(path, payload, expect_json=False):
                sent.append((path, payload))
                return {"ok": True, "accepted": 0, "last_sample_ts": None}

            worker._post = fake_post
            worker._push_frames()
            paths = [path for path, _ in sent if "frames" in path]
            self.assertEqual(paths, [], "frames older than the window must not be sent")

    def test_live_frames_bypass_watermark_and_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            worker, storage = self._worker(Path(directory), batch=3)
            sent: list[tuple[str, dict]] = []

            def fake_post(path, payload, expect_json=False):
                sent.append((path, payload))
                if path.endswith("hello"):
                    return {"ok": True, "last_sample_ts": None}
                return {"ok": True, "accepted": len(payload["frames"]),
                        "last_sample_ts": payload["frames"][-1]["captured_ts"]}

            worker._post = fake_post
            worker._hello()
            # Live frames arrive while storage is paused (disk guard mode).
            live_ts = int(time.time()) + 10
            worker.enqueue_live({
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(live_ts)),
                "captured_ts": live_ts,
                "inverter": snapshot("2026-09-02T10:00:00Z", 700),
                "battery": {"modules": [{"module_index": 1}]},
            })
            worker._flush_live()
            frames_sent = [payload for path, payload in sent if "frames" in path]
            self.assertEqual(len(frames_sent), 1)
            frame = frames_sent[0]["frames"][0]
            self.assertEqual(frame["captured_ts"], live_ts)
            self.assertEqual(frame["battery"]["modules"][0]["module_index"], 1)
            # Watermark untouched: the live frame bypassed the DB and acks.
            self.assertIsNone(worker._last_acked_ts)
            state = storage.forward_state("vps1")
            self.assertEqual(state["last_result"], "ok-live")
            # Empty flush is a no-op.
            worker._flush_live()
            self.assertEqual(len([p for p, _ in sent if "frames" in p]), 1)


class ForwarderStatusTests(unittest.TestCase):
    def test_status_reports_receivers_and_states(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = make_settings(Path(directory))
            storage = Storage(settings.db_path, master_id="testmaster")
            settings.receivers_file.write_text("vps1 | http://x | tok | on\n", encoding="utf-8")
            forwarder = Forwarder(settings, storage, poller=None)
            status = forwarder.status()
            self.assertEqual(status["receivers"][0]["name"], "vps1")
            self.assertTrue(status["receivers"][0]["enabled"])
            self.assertEqual(status["errors"], [])


if __name__ == "__main__":
    unittest.main()
