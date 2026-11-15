import tempfile
import time
import unittest
from pathlib import Path

from solarbridge.receiver import (
    MASTER_BUS_ERROR,
    MASTER_OFFLINE,
    MasterState,
)
from solarbridge.storage import Storage


class MasterStateTests(unittest.TestCase):
    def _state(self, directory: Path, offline_after_s: int = 180):
        storage = Storage(Path(directory) / "s.sqlite3", master_id="rx")
        return MasterState(storage, offline_after_s=offline_after_s), storage

    def test_first_heartbeat_marks_alive_and_event(self):
        with tempfile.TemporaryDirectory() as directory:
            state, storage = self._state(Path(directory))
            events = state.on_heartbeat({
                "master_id": "m1", "app_version": "0.1.0", "bus": {"inverter": {"ok": True}}
            })
            self.assertEqual([event["event"] for event in events], ["master_alive"])
            snap = state.snapshot()
            self.assertEqual(snap["master_state"], "alive")
            self.assertEqual(snap["status"], "online")
            self.assertEqual(snap["master_id"], "m1")

    def test_bus_error_from_heartbeat(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self._state(Path(directory))
            state.on_heartbeat({"master_id": "m1", "bus": {"inverter": {"ok": False, "last_error": "timeout"}}})
            snap = state.snapshot()
            # Master alive (heartbeat fresh) but the bus is broken: stale.
            self.assertEqual(snap["status"], "stale")
            self.assertEqual(snap["master_state"], MASTER_BUS_ERROR)
            health = state.health()
            self.assertEqual(health["last_error"], "timeout")

    def test_offline_transition_on_tick(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self._state(Path(directory))
            state.on_heartbeat({"master_id": "m1", "bus": {"inverter": {"ok": True}}})
            state._last_heartbeat_ts = time.time() - 100  # far beyond the 45 s threshold
            events = state.tick()
            self.assertEqual([event["event"] for event in events], ["master_offline"])
            self.assertEqual(state.snapshot()["master_state"], MASTER_OFFLINE)
            # repeated tick does not duplicate the event
            self.assertEqual(state.tick(), [])

    def test_bus_error_when_frames_stale_then_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self._state(Path(directory), offline_after_s=180)
            state.on_heartbeat({"master_id": "m1", "bus": {"inverter": {"ok": True}}})
            state._last_frame_ts = int(time.time()) - 300
            events = state.tick()
            self.assertEqual([event["event"] for event in events], ["bus_error"])
            self.assertEqual(state.snapshot()["master_state"], MASTER_BUS_ERROR)
            events = state.on_frames("m1", int(time.time()), "2026-09-02T10:00:00Z")
            self.assertEqual([event["event"] for event in events], ["bus_ok"])
            self.assertEqual(state.snapshot()["master_state"], "alive")

    def test_heartbeat_stores_host_subset(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self._state(Path(directory))
            state.on_heartbeat({
                "master_id": "m1", "app_version": "1.0.0", "bus": {"inverter": {"ok": True}},
                "host": {"cpu_temp_c": 49.8, "load_1m": 0.4, "throttled": False},
            })
            snap = state.snapshot()
            self.assertEqual(snap["host"]["cpu_temp_c"], 49.8)
            self.assertEqual(state.health()["master_app_version"], "1.0.0")

    def test_version_change_is_recorded_as_event(self):
        with tempfile.TemporaryDirectory() as directory:
            state, _ = self._state(Path(directory))
            state.on_heartbeat({"master_id": "m1", "app_version": "1.0.0", "bus": {"inverter": {"ok": True}}})
            events = state.on_heartbeat({"master_id": "m1", "app_version": "1.1.0", "bus": {"inverter": {"ok": True}}})
            # the http handler stores these events; the state only reports them
            self.assertIn("master_version", [event["event"] for event in events])
            self.assertEqual(events[-1]["detail"], "app=1.1.0 (was 1.0.0)")


if __name__ == "__main__":
    unittest.main()
