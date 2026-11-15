import gzip
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from solarbridge.seed import (
    PASSPORT_FILE,
    SEED_FILE,
    create_seed,
    estimate_seed_size,
    install_seed,
    read_passport,
    verify_passport,
)
from solarbridge.storage import Storage
from tests.helpers import snapshot


class SeedTests(unittest.TestCase):
    def _prepared(self, directory: Path):
        db_path = directory / "master.sqlite3"
        store = Storage(db_path, master_id="m1")
        old_ts = int(time.time()) - 90 * 86400
        fresh_ts = int(time.time()) - 60
        old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old_ts))
        fresh = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fresh_ts))
        store.insert_sample(snapshot(old, 100))
        store.insert_sample(snapshot(fresh, 200))
        store.insert_battery_frame(old, old_ts, [
            {"module_index": 1, "module_serial": "LPR", "metrics": {"soc_percent": 70}, "payload": {"cells_v": [3.1]}}
        ])
        return db_path, old_ts, fresh_ts

    def test_full_seed_passport_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path, old_ts, fresh_ts = self._prepared(Path(directory))
            seed_id, gz_path, passport = create_seed(db_path, "m1", Path(directory) / "seeds")
            self.assertEqual(passport["samples_count"], 2)
            self.assertEqual(passport["battery_rows"], 1)
            self.assertEqual(passport["last_sample_ts"], fresh_ts)
            self.assertEqual(passport["schema_version"], 1)
            self.assertEqual(passport["compact_days"], 0)
            stored = json.loads((Path(directory) / "seeds" / seed_id / PASSPORT_FILE).read_text())
            self.assertEqual(stored["sha256"], passport["sha256"])
            data = gzip.decompress(gz_path.read_bytes())
            self.assertIn(b"payload_json", data)
            verify_passport(passport, gz_path, receiver_schema_version=1, max_age_days=None)

    def test_compact_seed_truncates_old_payloads_keeps_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path, old_ts, fresh_ts = self._prepared(Path(directory))
            seed_id, gz_path, passport = create_seed(
                db_path, "m1", Path(directory) / "seeds", compact_days=60
            )
            self.assertEqual(passport["compact_days"], 60)
            restored = Path(directory) / "restored.sqlite3"
            restored.write_bytes(gzip.decompress(gz_path.read_bytes()))
            check = Storage(restored, master_id="m1")
            # Both rows survive: charts keep working, only old payload detail is cut.
            self.assertEqual(check.stats()["sample_count"], 2)
            self.assertEqual(check.stats()["battery_row_count"], 1)
            rows = check.frames_after(old_ts - 1, 10)
            payloads = {row["captured_ts"]: row["snapshot"] for row in rows}
            self.assertEqual(payloads[old_ts], {})
            self.assertIn("metrics", payloads[fresh_ts])

    def test_verify_rejects_corrupt_stale_and_newer_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path, _old, _fresh = self._prepared(Path(directory))
            seed_id, gz_path, passport = create_seed(db_path, "m1", Path(directory) / "seeds")
            with self.assertRaises(ValueError):
                verify_passport({**passport, "sha256": "0" * 64}, gz_path, 1)
            with self.assertRaises(ValueError):
                verify_passport({**passport, "schema_version": 9}, gz_path, 1)
            stale = {**passport, "created_ts": int(time.time()) - 120 * 86400}
            with self.assertRaises(ValueError):
                verify_passport(stale, gz_path, 1, max_age_days=60)

    def test_install_seed_backs_up_and_replaces(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path, _old, _fresh = self._prepared(Path(directory))
            seed_id, gz_path, _passport = create_seed(db_path, "m1", Path(directory) / "seeds")
            seed_dir = Path(directory) / "seeds"

            target = Path(directory) / "receiver.sqlite3"
            Storage(target, master_id="m1")  # create receiver db with its own data
            with tempfile.TemporaryDirectory() as incoming:
                moved_dir = Path(incoming)
                shutil.copytree(seed_dir, moved_dir / "seeds", dirs_exist_ok=True)
                passport = install_seed(
                    moved_dir / "seeds", seed_id, target,
                    receiver_schema_version=1, max_age_days=None,
                )
                self.assertIn("installed_backup", passport)
                backups = list(Path(directory).glob("receiver.sqlite3.bak-*"))
                self.assertEqual(len(backups), 1)
                check = Storage(target, master_id="m1")
                self.assertEqual(check.stats()["sample_count"], 2)

    def test_estimate_seed_size(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path, _old, _fresh = self._prepared(Path(directory))
            full = estimate_seed_size(db_path, None)
            compact = estimate_seed_size(db_path, 60)
            self.assertEqual(full["samples"], 2)
            self.assertEqual(compact["samples"], 1)


if __name__ == "__main__":
    unittest.main()
