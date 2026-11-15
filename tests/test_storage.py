import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from solarbridge.storage import FORWARD_RESULT_DEFAULTS, METRIC_COLUMNS, SCHEMA_VERSION, Storage
from tests.helpers import snapshot


class StorageTests(unittest.TestCase):
    def test_insert_latest_stats_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "samples.sqlite3")
            store.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
            store.insert_sample(snapshot("2026-09-02T10:30:00Z", 300))
            self.assertEqual(store.latest_payload()["metrics"]["load_power_w"], 300)
            self.assertEqual(store.stats()["sample_count"], 2)
            history = store.history(1788340000, 1788350000, "hour")
            self.assertEqual(len(history["points"]), 1)
            self.assertEqual(history["points"][0]["load_power_w"], 200)
            self.assertEqual(history["points"][0]["load_power_min_w"], 100)
            self.assertEqual(history["points"][0]["load_power_max_w"], 300)

    def test_insert_is_idempotent_per_master_and_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            first = store.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
            duplicate = store.insert_sample(snapshot("2026-09-02T10:00:00Z", 100))
            self.assertTrue(first)
            self.assertFalse(duplicate)
            self.assertEqual(store.stats()["sample_count"], 1)
            # A different master_id is a different source: both rows are kept.
            store.insert_sample(snapshot("2026-09-02T10:00:00Z", 999), master_id="other")
            self.assertEqual(store.stats()["sample_count"], 2)

    def test_meta_schema_version_and_master_id(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3", master_id="pi-master")
            self.assertEqual(store.schema_version(), SCHEMA_VERSION)
            store.set_master_id("pi-master")
            with closing(sqlite3.connect(Path(directory) / "s.sqlite3")) as connection:
                rows = dict(connection.execute("SELECT key, value FROM meta"))
            self.assertEqual(rows["master_id"], "pi-master")

    def test_frames_after_respects_order_limit_and_master(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            base = 1_700_000_000
            for index in range(5):
                moment = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + index * 60))
                store.insert_sample(snapshot(moment, 100 + index), master_id="m1")
                if index < 2:
                    store.insert_sample(snapshot(moment, 500), master_id="m2")
            rows = store.frames_after(base - 1, 3, master_id="m1")
            self.assertEqual([row["captured_ts"] for row in rows],
                             [base, base + 60, base + 120])
            rows = store.frames_after(base + 180, 10, master_id="m1")
            self.assertEqual(len(rows), 1)

    def test_forward_state_upsert_and_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            state = store.forward_state("vps1")
            self.assertEqual(state, {**FORWARD_RESULT_DEFAULTS})
            store.save_forward_state(
                "vps1", last_acked_ts=12345, last_result="ok", consecutive_failures=0,
                sent_total=10, acked_total=9,
            )
            state = store.forward_state("vps1")
            self.assertEqual(state["last_acked_ts"], 12345)
            self.assertEqual(state["acked_total"], 9)
            self.assertIsNotNone(state["updated_ts"])
            self.assertIn("vps1", store.all_forward_states())

    def test_seed_tokens_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.add_seed_token("tok1", "seed-a", "vps1", ttl_hours=1, max_downloads=2)
            row = store.consume_seed_token("tok1")
            self.assertIsNotNone(row)
            self.assertEqual(row["seed_id"], "seed-a")
            self.assertEqual(store.consume_seed_token("tok1")["downloads_used"], 2)
            self.assertIsNone(store.consume_seed_token("tok1"))  # exhausted
            store.add_seed_token("tok2", "seed-a", "vps1", ttl_hours=1, max_downloads=5)
            listed = store.list_seed_tokens()
            self.assertEqual([item["status"] for item in listed], ["active", "exhausted"])
            token_hash = listed[0]["token_hash"]
            self.assertTrue(store.revoke_seed_token(token_hash))
            self.assertIsNone(store.consume_seed_token("tok2"))

    def test_master_events_and_prune(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            now = int(time.time())
            store.add_master_event("master_alive", "app=0.1.0", ts=now)
            store.add_master_event("master_offline", "no heartbeat", ts=now - 40 * 86400)
            events = store.recent_master_events(10)
            self.assertEqual([event["event"] for event in events], ["master_alive"])

    def test_battery_rows_insert_stats_and_prune(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            modules = [
                {"module_index": 1, "module_serial": "LPR-1",
                 "metrics": {"soc_percent": 80, "voltage_v": 52.8, "current_a": -1.5,
                             "cell_voltage_min_v": 3.30, "cell_voltage_max_v": 3.35,
                             "cell_delta_v": 0.05, "cycles": 42},
                 "payload": {"cells_v": [3.3, 3.35]}},
                {"module_index": 2, "module_serial": "LPR-2",
                 "metrics": {"soc_percent": 81}, "payload": {}},
            ]
            inserted = store.insert_battery_frame("2026-09-02T10:00:00Z", 1788340000, modules)
            self.assertEqual(inserted, 2)
            # idempotent re-insert
            self.assertEqual(store.insert_battery_frame("2026-09-02T10:00:00Z", 1788340000, modules), 0)
            stats = store.stats()
            self.assertEqual(stats["battery_row_count"], 2)
            self.assertEqual(stats["battery_modules"], 2)
            removed = store.prune(retention_days=0)
            self.assertEqual(removed["battery_samples"], 2)

    def test_latest_battery_frame_reconstructs_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            self.assertIsNone(store.latest_battery_frame())
            modules = [
                {"module_index": 2, "module_serial": "LPR-A",
                 "metrics": {"soc_percent": 58, "voltage_v": 52.9, "current_a": 1.7},
                 "payload": {"protocol": "paceic-ascii/v25", "analog": {"cycles": 27}}},
                {"module_index": 3, "module_serial": None,
                 "metrics": {"soc_percent": 60}, "payload": {}},
            ]
            store.insert_battery_frame("2026-09-02T10:00:00Z", 1788340000, modules)
            store.insert_battery_frame("2026-09-02T10:01:00Z", 1788340060, modules[:1])
            frame = store.latest_battery_frame()
            self.assertEqual(frame["captured_ts"], 1788340060)
            self.assertEqual(frame["captured_at"], "2026-09-02T10:01:00Z")
            self.assertEqual(len(frame["modules"]), 1)
            self.assertEqual(frame["modules"][0]["module_index"], 2)
            self.assertEqual(frame["modules"][0]["module_serial"], "LPR-A")
            self.assertEqual(frame["modules"][0]["metrics"]["soc_percent"], 58)
            self.assertEqual(frame["modules"][0]["payload"]["analog"]["cycles"], 27)

    def test_prune_removes_old_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 100 * 86400))
            new = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            store.insert_sample(snapshot(old, 10))
            store.insert_sample(snapshot(new, 20))
            removed = store.prune(retention_days=90)
            self.assertEqual(removed["samples"], 1)
            self.assertEqual(store.stats()["sample_count"], 1)

    def test_existing_database_gets_new_metric_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "CREATE TABLE samples (id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL, "
                    "captured_ts INTEGER NOT NULL, connection_status TEXT NOT NULL, "
                    "battery_voltage_v REAL, payload_json TEXT NOT NULL)"
                )
                connection.commit()
            Storage(path)
            with closing(sqlite3.connect(path)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(samples)")}
            self.assertTrue(set(METRIC_COLUMNS).issubset(columns))

    def test_minute_and_half_hour_buckets(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "samples.sqlite3")
            for timestamp, load in (
                ("2026-09-02T10:00:05Z", 100),
                ("2026-09-02T10:00:55Z", 200),
                ("2026-09-02T10:01:00Z", 300),
                ("2026-09-02T10:30:00Z", 400),
            ):
                store.insert_sample(snapshot(timestamp, load))
            minute = store.history(1788340000, 1788350000, "minute")
            half_hour = store.history(1788340000, 1788350000, "30m")
            self.assertEqual([point["captured_at"] for point in minute["points"]], [
                "2026-09-02T10:00:00Z",
                "2026-09-02T10:01:00Z",
                "2026-09-02T10:30:00Z",
            ])
            self.assertEqual([point["captured_at"] for point in half_hour["points"]], [
                "2026-09-02T10:00:00Z",
                "2026-09-02T10:30:00Z",
            ])
            self.assertEqual(minute["points"][0]["load_power_w"], 150)

    def test_raw_history_keeps_latest_points_when_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "samples.sqlite3")
            for minute, load in ((0, 100), (1, 200), (2, 300)):
                store.insert_sample(snapshot(f"2026-09-02T10:{minute:02}:00Z", load))
            history = store.history(1788340000, 1788350000, "raw", max_raw_points=2)
            self.assertTrue(history["truncated"])
            self.assertEqual([point["load_power_w"] for point in history["points"]], [200, 300])


class TariffFinanceTests(unittest.TestCase):
    def test_tariff_crud_and_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            self.assertEqual(store.tariffs_list(), [])
            tariff = store.tariff_set("2026-11-01", 6.12, "зимний")
            self.assertEqual(tariff["price_per_kwh"], 6.12)
            store.tariff_set("2026-10-01", 5.35, "")
            self.assertEqual(len(store.tariffs_list()), 2)
            # same valid_from updates instead of duplicating
            store.tariff_set("2026-10-01", 5.40, "правка")
            self.assertEqual(len(store.tariffs_list()), 2)
            self.assertEqual(store.tariff_for_date("2026-10-15"), 5.4)
            self.assertEqual(store.tariff_for_date("2026-11-20"), 6.12)
            # dates before the first tariff fall back to it
            self.assertEqual(store.tariff_for_date("2026-01-01"), 5.4)
            self.assertTrue(store.tariff_delete(store.tariffs_list()[0]["id"]))
            self.assertFalse(store.tariff_delete(999999))

    def test_tariff_validation_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            with self.assertRaises(ValueError):
                store.tariff_set("2026-13-01", 5.0)
            with self.assertRaises(ValueError):
                store.tariff_set("2026-11-1", 5.0)
            with self.assertRaises(ValueError):
                store.tariff_set("2026-11-01", 0)
            with self.assertRaises(ValueError):
                store.tariff_set("2026-11-01", -3)

    def test_finance_computes_kwh_and_money_from_buckets(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.tariff_set("2026-09-01", 10.0)
            # 10:00Z hour bucket: 1000 W load for one full hour -> 1 kWh.
            store.insert_sample(snapshot(
                "2026-09-02T10:00:00Z", 1000,
                metrics_extra={"pv_power_w": 2000, "battery_power_w": 500},
            ))
            finance = store.finance(days=2, tz_offset_minutes=0, now_ts=1788356400)
            day = next((row for row in finance["rows"] if row["date"] == "2026-09-02"), None)
            self.assertIsNotNone(day)
            self.assertGreater(day["load_kwh"], 0.9)
            self.assertGreater(day["pv_kwh"], 1.9)
            self.assertGreater(day["batt_discharge_kwh"], 0.4)
            self.assertEqual(day["tariff"], 10.0)
            # money reprices instantly with the tariff
            self.assertAlmostEqual(day["pv_savings"], day["pv_kwh"] * 10.0, places=3)
            store.tariff_set("2026-09-01", 20.0)
            finance = store.finance(days=2, tz_offset_minutes=0, now_ts=1788356400)
            day = next((row for row in finance["rows"] if row["date"] == "2026-09-02"), None)
            self.assertAlmostEqual(day["pv_savings"], day["pv_kwh"] * 20.0, places=3)

    def test_finance_local_day_boundaries_follow_tz_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.tariff_set("2026-09-01", 10.0)
            # 22:00Z = local 2026-09-03T02:00 at UTC+4 (tz = -240): the sample
            # must land on the NEXT local date, not the UTC date.
            store.insert_sample(snapshot("2026-09-02T22:00:00Z", 3000))
            finance = store.finance(days=2, tz_offset_minutes=-240, now_ts=1788390000)
            dates = [row["date"] for row in finance["rows"] if row["hours"] > 0]
            self.assertIn("2026-09-03", dates)
            self.assertNotIn("2026-09-02", dates)

    @staticmethod
    def _counter_status(load, buy=0.0, sell=0.0, charge=0.0, discharge=0.0,
                        grid_charge=0.0, pv=0.0):
        return {"status": {
            "inverter": {
                "accumulated_load_power_kwh": load,
                "accumulated_buy_power_kwh": buy,
                "accumulated_sell_power_kwh": sell,
                "accumulated_charger_power_kwh": charge,
                "accumulated_discharger_power_kwh": discharge,
                "accumulated_grid_charger_power_kwh": grid_charge,
            },
            "charger": {"accumulated_pv_power_kwh": pv},
        }}

    def test_finance_uses_hardware_counters_when_available(self):
        """Counter deltas between local midnights are exact: absurd power
        values must NOT influence the day totals."""
        from datetime import datetime, timezone as tz

        day2_end = int(datetime(2026, 9, 2, 23, 59, tzinfo=tz.utc).timestamp())
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.tariff_set("2026-09-01", 10.0)
            # Day 1 tail: the midnight baseline for day 2.
            store.insert_sample(snapshot("2026-09-01T23:50:00Z", 99999, master_extra=self._counter_status(
                load=100.0, buy=20.0, sell=0.0, charge=50.0, discharge=30.0, grid_charge=5.0, pv=200.0)))
            # Day 2: spikes and dips - the counters absorb them exactly.
            store.insert_sample(snapshot("2026-09-02T00:10:00Z", 99999, master_extra=self._counter_status(
                load=100.0, buy=20.0, sell=0.0, charge=50.0, discharge=30.0, grid_charge=5.0, pv=200.0)))
            store.insert_sample(snapshot("2026-09-02T12:00:00Z", 99999, master_extra=self._counter_status(
                load=102.5, buy=21.2, sell=0.1, charge=51.0, discharge=31.5, grid_charge=5.3, pv=203.0)))
            store.insert_sample(snapshot("2026-09-02T23:50:00Z", 99999, master_extra=self._counter_status(
                load=103.6, buy=21.9, sell=0.1, charge=51.6, discharge=32.1, grid_charge=5.4, pv=203.7)))

            finance = store.finance(days=2, tz_offset_minutes=0, now_ts=day2_end)
            day2 = next((row for row in finance["rows"] if row["date"] == "2026-09-02"), None)
            self.assertIsNotNone(day2)
            self.assertEqual(day2["source"], "counters")
            self.assertAlmostEqual(day2["load_kwh"], 3.6, places=3)
            self.assertAlmostEqual(day2["grid_buy_kwh"], 1.9, places=3)
            self.assertAlmostEqual(day2["grid_sell_kwh"], 0.1, places=3)
            self.assertAlmostEqual(day2["batt_charge_kwh"], 1.6, places=3)
            self.assertAlmostEqual(day2["batt_discharge_kwh"], 2.1, places=3)
            self.assertAlmostEqual(day2["batt_charge_from_grid_kwh"], 0.4, places=3)
            self.assertAlmostEqual(day2["batt_charge_from_pv_kwh"], 1.2, places=3)
            self.assertAlmostEqual(day2["pv_kwh"], 3.7, places=3)
            self.assertAlmostEqual(day2["grid_buy_cost"], 19.0, places=3)
            self.assertAlmostEqual(day2["pv_savings"], 37.0, places=3)
            self.assertAlmostEqual(day2["net"], 18.0, places=3)

    def test_finance_falls_back_to_integration_after_counter_reset(self):
        from datetime import datetime, timezone as tz

        day2_end = int(datetime(2026, 9, 2, 23, 59, tzinfo=tz.utc).timestamp())
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "s.sqlite3")
            store.tariff_set("2026-09-01", 10.0)
            store.insert_sample(snapshot("2026-09-01T23:50:00Z", 1000, master_extra=self._counter_status(
                load=100.0, buy=20.0, sell=0.0, charge=50.0, discharge=30.0, grid_charge=5.0, pv=200.0)))
            # Someone pressed "Remove accumulated data": counters restarted.
            store.insert_sample(snapshot("2026-09-02T12:00:00Z", 1000, master_extra=self._counter_status(
                load=0.5, buy=0.1, sell=0.0, charge=0.2, discharge=0.1, grid_charge=0.05, pv=1.0)))
            finance = store.finance(days=2, tz_offset_minutes=0, now_ts=day2_end)
            day2 = next((row for row in finance["rows"] if row["date"] == "2026-09-02"), None)
            self.assertIsNotNone(day2)
            self.assertEqual(day2["source"], "integration")


if __name__ == "__main__":
    unittest.main()
