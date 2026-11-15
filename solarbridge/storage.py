"""SQLite storage shared by both roles (identical schema everywhere).

Samples are idempotent per (master_id, captured_ts): duplicates from
re-sends, imports or restores are silently ignored. Also holds tariff
history, forward watermarks, seed tokens and master events, plus the
restore-from-receiver copy path used for master recovery.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


SCHEMA_VERSION = 1
MIN_SUPPORTED_SCHEMA = 1
EVENT_RETENTION_DAYS = 30

METRIC_COLUMNS = (
    "battery_voltage_v",
    "pv_voltage_v",
    "pv_current_a",
    "pv_power_w",
    "inverter_voltage_v",
    "grid_voltage_v",
    "bus_voltage_v",
    "inverter_current_a",
    "grid_current_a",
    "load_current_a",
    "inverter_power_w",
    "grid_power_w",
    "load_power_w",
    "load_percent",
    "inverter_frequency_hz",
    "grid_frequency_hz",
    "battery_power_w",
    "ac_radiator_temperature_c",
    "transformer_temperature_c",
    "dc_radiator_temperature_c",
)

FORWARD_RESULT_DEFAULTS = {
    "last_acked_ts": None,
    "last_attempt_ts": None,
    "last_ok_ts": None,
    "last_result": None,
    "last_error": None,
    "consecutive_failures": 0,
    "sent_total": 0,
    "acked_total": 0,
    "updated_ts": None,
}


class Storage:
    def __init__(self, path: Path, master_id: str = "local") -> None:
        self.path = path
        self.master_id = master_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY,
                    master_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    captured_ts INTEGER NOT NULL,
                    connection_status TEXT NOT NULL,
                    battery_voltage_v REAL,
                    pv_voltage_v REAL,
                    pv_current_a REAL,
                    pv_power_w REAL,
                    inverter_voltage_v REAL,
                    grid_voltage_v REAL,
                    bus_voltage_v REAL,
                    inverter_current_a REAL,
                    grid_current_a REAL,
                    load_current_a REAL,
                    inverter_power_w REAL,
                    grid_power_w REAL,
                    load_power_w REAL,
                    load_percent REAL,
                    inverter_frequency_hz REAL,
                    grid_frequency_hz REAL,
                    battery_power_w REAL,
                    ac_radiator_temperature_c REAL,
                    transformer_temperature_c REAL,
                    dc_radiator_temperature_c REAL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(master_id, captured_ts)
                );
                CREATE INDEX IF NOT EXISTS idx_samples_captured_ts
                    ON samples(captured_ts);
                CREATE TABLE IF NOT EXISTS battery_samples (
                    id INTEGER PRIMARY KEY,
                    master_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    captured_ts INTEGER NOT NULL,
                    module_index INTEGER NOT NULL,
                    module_serial TEXT,
                    soc_percent REAL,
                    voltage_v REAL,
                    current_a REAL,
                    temp_min_c REAL,
                    temp_max_c REAL,
                    cell_voltage_min_v REAL,
                    cell_voltage_max_v REAL,
                    cell_delta_v REAL,
                    soh_percent REAL,
                    cycles INTEGER,
                    protection_bits INTEGER,
                    alarm_bits INTEGER,
                    payload_json TEXT NOT NULL,
                    UNIQUE(master_id, captured_ts, module_index)
                );
                CREATE INDEX IF NOT EXISTS idx_battery_ts
                    ON battery_samples(captured_ts);
                CREATE TABLE IF NOT EXISTS forward_state (
                    receiver_name TEXT PRIMARY KEY,
                    last_acked_ts INTEGER,
                    last_attempt_ts INTEGER,
                    last_ok_ts INTEGER,
                    last_result TEXT,
                    last_error TEXT,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    sent_total INTEGER NOT NULL DEFAULT 0,
                    acked_total INTEGER NOT NULL DEFAULT 0,
                    updated_ts INTEGER
                );
                CREATE TABLE IF NOT EXISTS seed_tokens (
                    token_hash TEXT PRIMARY KEY,
                    seed_id TEXT NOT NULL,
                    label TEXT,
                    created_ts INTEGER NOT NULL,
                    expires_ts INTEGER NOT NULL,
                    max_downloads INTEGER NOT NULL DEFAULT 10,
                    downloads_used INTEGER NOT NULL DEFAULT 0,
                    last_used_ts INTEGER,
                    revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS master_events (
                    id INTEGER PRIMARY KEY,
                    ts INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_master_events_ts
                    ON master_events(ts);
                CREATE TABLE IF NOT EXISTS tariffs (
                    id INTEGER PRIMARY KEY,
                    valid_from TEXT NOT NULL UNIQUE,
                    price_per_kwh REAL NOT NULL,
                    note TEXT,
                    created_ts INTEGER NOT NULL
                );
                """
            )
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(samples)").fetchall()
            }
            for column in METRIC_COLUMNS:
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE samples ADD COLUMN {column} REAL")

            now = int(time.time())
            connection.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', ?)",
                (str(now),),
            )
            connection.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('app_version', ?)",
                (__import__("solarbridge", fromlist=["__version__"]).__version__,),
            )

    def schema_version(self) -> int:
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        try:
            return int(row["value"]) if row else SCHEMA_VERSION
        except (TypeError, ValueError):
            return SCHEMA_VERSION

    def set_master_id(self, master_id: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO meta (key, value) VALUES ('master_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (master_id,),
            )

    # ------------------------------------------------------------------ samples

    def insert_sample(self, snapshot: dict[str, Any], master_id: str | None = None) -> bool:
        """Insert one inverter snapshot. Idempotent per (master_id, captured_ts)."""
        metrics = snapshot.get("metrics", {})
        captured_at = snapshot["captured_at"]
        captured_ts = int(datetime.fromisoformat(captured_at.replace("Z", "+00:00")).timestamp())
        values = [metrics.get(column) for column in METRIC_COLUMNS]
        columns = ("master_id", "captured_at", "captured_ts", "connection_status", *METRIC_COLUMNS, "payload_json")
        placeholders = ", ".join("?" for _ in columns)
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO samples ({', '.join(columns)}) VALUES ({placeholders}) "
                "ON CONFLICT(master_id, captured_ts) DO NOTHING",
                [
                    master_id or self.master_id,
                    captured_at,
                    captured_ts,
                    snapshot.get("connection", {}).get("status", "unknown"),
                    *values,
                    json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                ],
            )
            return cursor.rowcount > 0

    def latest_payload(self) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM samples ORDER BY captured_ts DESC, id DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def last_sample_ts(self, master_id: str | None = None) -> int | None:
        query = "SELECT MAX(captured_ts) AS captured_ts FROM samples"
        params: tuple = ()
        if master_id:
            query += " WHERE master_id = ?"
            params = (master_id,)
        with self._lock, self._connection() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row["captured_ts"]) if row and row["captured_ts"] is not None else None

    def frames_after(self, after_ts: int, limit: int, master_id: str | None = None) -> list[dict[str, Any]]:
        """Frames strictly newer than after_ts, oldest first, at most limit."""
        query = (
            "SELECT captured_at, captured_ts, connection_status, payload_json FROM samples "
            "WHERE captured_ts > ?"
        )
        params: list[Any] = [after_ts]
        if master_id:
            query += " AND master_id = ?"
            params.append(master_id)
        query += " ORDER BY captured_ts LIMIT ?"
        params.append(limit)
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "captured_at": row["captured_at"],
                "captured_ts": int(row["captured_ts"]),
                "connection_status": row["connection_status"],
                "snapshot": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def restore_from_db(
        self,
        source_path: Path,
        since_ts: int | None = None,
        until_ts: int | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, int]:
        """Copy frames from another SolarBridge database (receiver mirror) into
        this one, rewriting master_id to ours. Rows are matched by payload
        columns, deduplicated by UNIQUE(master_id, captured_ts); range bounds
        are inclusive unix timestamps and may be None (open-ended).

        This is the master-recovery path: after an SD-card loss the fresh
        master pulls everything the receiver kept. The source database is
        attached read-only in spirit: only SELECTs run against it and nothing
        is ever written to the source file.
        """
        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"source database not found: {source_path}")
        condition = ""
        params: list[Any] = []
        if since_ts is not None:
            condition += " AND captured_ts >= ?"
            params.append(int(since_ts))
        if until_ts is not None:
            condition += " AND captured_ts <= ?"
            params.append(int(until_ts))
        sample_columns = (
            "captured_at, captured_ts, connection_status, " + ", ".join(METRIC_COLUMNS) + ", payload_json"
        )
        battery_columns = (
            "captured_at, captured_ts, module_index, module_serial, soc_percent, voltage_v, "
            "current_a, temp_min_c, temp_max_c, cell_voltage_min_v, cell_voltage_max_v, "
            "cell_delta_v, soh_percent, cycles, protection_bits, alarm_bits, payload_json"
        )
        inserted = skipped = total = 0
        with self._lock, self._connection() as connection:
            connection.execute("ATTACH DATABASE ? AS rx", (str(source_path),))
            try:
                total = int(connection.execute(
                    f"SELECT COUNT(*) AS n FROM rx.samples WHERE 1=1{condition}", params
                ).fetchone()["n"])
                rows = connection.execute(
                    f"SELECT {sample_columns} FROM rx.samples WHERE 1=1{condition}", params
                ).fetchall()
                for index, row in enumerate(rows):
                    placeholders = ", ".join("?" for _ in row)
                    cursor = connection.execute(
                        f"INSERT OR IGNORE INTO samples (master_id, {sample_columns}) "
                        f"VALUES (?{', ' if placeholders else ''}{placeholders})",
                        [self.master_id, *tuple(row)],
                    )
                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                    if progress and (index % 200 == 0 or index + 1 == len(rows)):
                        progress(index + 1, len(rows))
                connection.execute(
                    f"INSERT OR IGNORE INTO battery_samples (master_id, {battery_columns}) "
                    f"SELECT ?, {battery_columns} FROM rx.battery_samples WHERE 1=1{condition}",
                    [self.master_id, *params],
                )
                # End the read/write transaction, otherwise DETACH sees rx
                # locks still held and raises "database rx is locked".
                connection.commit()
            finally:
                connection.execute("DETACH DATABASE rx")
        return {
            "inserted": inserted,
            "skipped": skipped,
            "total": total,
            "battery": self.battery_row_count(),
        }

    def battery_row_count(self) -> int:
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM battery_samples").fetchone()
        return int(row["n"])

    def purge_before(self, cutoff_ts: int, vacuum: bool = True) -> dict[str, int]:
        """Delete frames older than cutoff_ts (unix seconds) and reclaim space.

        Manual counterpart of the retention prune, exposed through the
        installer menu: "delete data before this date" when the disk runs out
        but the old history is no longer needed. VACUUM runs in its own
        transaction — SQLite cannot vacuum inside another one."""
        with self._lock, self._connection() as connection:
            samples = connection.execute(
                "DELETE FROM samples WHERE captured_ts < ?", (int(cutoff_ts),)
            ).rowcount
            battery = connection.execute(
                "DELETE FROM battery_samples WHERE captured_ts < ?", (int(cutoff_ts),)
            ).rowcount
        if vacuum:
            with self._lock, self._connection() as connection:
                connection.execute("VACUUM")
        return {"samples": samples, "battery": battery}

    def latest_battery_frame(self) -> dict[str, Any] | None:
        """The newest battery frame: {"captured_at", "captured_ts", "modules": [...]} or None.

        Shape mirrors the ingest format (frame["battery"]), with per-module
        metrics reconstructed from the battery_samples columns."""
        with self._lock, self._connection() as connection:
            newest = connection.execute(
                "SELECT captured_at, captured_ts FROM battery_samples ORDER BY captured_ts DESC LIMIT 1"
            ).fetchone()
            if newest is None:
                return None
            captured_ts = int(newest["captured_ts"])
            rows = connection.execute(
                "SELECT module_index, module_serial, soc_percent, voltage_v, current_a, "
                "temp_min_c, temp_max_c, cell_voltage_min_v, cell_voltage_max_v, cell_delta_v, "
                "soh_percent, cycles, protection_bits, alarm_bits, payload_json "
                "FROM battery_samples WHERE captured_ts = ? ORDER BY module_index",
                (captured_ts,),
            ).fetchall()
        modules = []
        for row in rows:
            modules.append({
                "module_index": int(row["module_index"]),
                "module_serial": row["module_serial"],
                "metrics": {
                    "soc_percent": row["soc_percent"],
                    "voltage_v": row["voltage_v"],
                    "current_a": row["current_a"],
                    "temp_min_c": row["temp_min_c"],
                    "temp_max_c": row["temp_max_c"],
                    "cell_voltage_min_v": row["cell_voltage_min_v"],
                    "cell_voltage_max_v": row["cell_voltage_max_v"],
                    "cell_delta_v": row["cell_delta_v"],
                    "soh_percent": row["soh_percent"],
                    "cycles": row["cycles"],
                    "protection_bits": row["protection_bits"],
                    "alarm_bits": row["alarm_bits"],
                },
                "payload": json.loads(row["payload_json"]),
            })
        return {"captured_at": newest["captured_at"], "captured_ts": captured_ts, "modules": modules}

    def battery_frames_after(self, after_ts: int, limit: int, master_id: str | None = None) -> dict[int, list[dict[str, Any]]]:
        """Battery frames newer than after_ts, grouped by captured_ts.

        Modules are returned in the same shape ingest expects
        ({module_index, module_serial, metrics, payload}): the receiver side
        writes them back through insert_battery_frame, which fills the metric
        columns from module["metrics"] and keeps payload_json for details."""
        query = (
            "SELECT captured_at, captured_ts, module_index, module_serial, "
            "soc_percent, voltage_v, current_a, temp_min_c, temp_max_c, "
            "cell_voltage_min_v, cell_voltage_max_v, cell_delta_v, "
            "soh_percent, cycles, protection_bits, alarm_bits, payload_json "
            "FROM battery_samples WHERE captured_ts > ?"
        )
        params: list[Any] = [after_ts]
        if master_id:
            query += " AND master_id = ?"
            params.append(master_id)
        query += " ORDER BY captured_ts LIMIT ?"
        params.append(limit)
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            module = {
                "module_index": int(row["module_index"]),
                "module_serial": row["module_serial"],
                "metrics": {
                    "soc_percent": row["soc_percent"],
                    "voltage_v": row["voltage_v"],
                    "current_a": row["current_a"],
                    "temp_min_c": row["temp_min_c"],
                    "temp_max_c": row["temp_max_c"],
                    "cell_voltage_min_v": row["cell_voltage_min_v"],
                    "cell_voltage_max_v": row["cell_voltage_max_v"],
                    "cell_delta_v": row["cell_delta_v"],
                    "soh_percent": row["soh_percent"],
                    "cycles": row["cycles"],
                    "protection_bits": row["protection_bits"],
                    "alarm_bits": row["alarm_bits"],
                },
                "payload": json.loads(row["payload_json"]),
            }
            result.setdefault(int(row["captured_ts"]), []).append(module)
        return result

    def stats(self) -> dict[str, Any]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count, MIN(captured_ts) AS oldest, MAX(captured_ts) AS newest FROM samples"
            ).fetchone()
            battery = connection.execute(
                "SELECT COUNT(*) AS count, COUNT(DISTINCT module_index) AS modules, "
                "MAX(captured_ts) AS newest FROM battery_samples"
            ).fetchone()
        return {
            "sample_count": int(row["count"]),
            "oldest_at": _iso_from_ts(row["oldest"]),
            "newest_at": _iso_from_ts(row["newest"]),
            "battery_row_count": int(battery["count"]),
            "battery_modules": int(battery["modules"]),
            "battery_newest_at": _iso_from_ts(battery["newest"]),
        }

    # ------------------------------------------------------------------ tariffs

    def tariffs_list(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT id, valid_from, price_per_kwh, note, created_ts "
                "FROM tariffs ORDER BY valid_from DESC, id DESC"
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "valid_from": row["valid_from"],
                "price_per_kwh": _number(row["price_per_kwh"]),
                "note": row["note"] or "",
                "created_ts": int(row["created_ts"]) if row["created_ts"] else None,
            }
            for row in rows
        ]

    def tariff_set(self, valid_from: str, price: float, note: str = "") -> dict[str, Any]:
        """Insert or replace the tariff effective from valid_from (YYYY-MM-DD).

        History is never mutated silently: each change is a row keyed by its
        start date, so past recalculations stay reproducible."""
        valid_from = (valid_from or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valid_from):
            raise ValueError("valid_from must be YYYY-MM-DD")
        try:
            time.strptime(valid_from, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("valid_from is not a real date") from exc
        price = round(float(price), 4)
        if not price > 0:
            raise ValueError("price must be greater than zero")
        with self._lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO tariffs (valid_from, price_per_kwh, note, created_ts) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(valid_from) DO UPDATE SET price_per_kwh=excluded.price_per_kwh, "
                "note=excluded.note, created_ts=excluded.created_ts",
                (valid_from, price, (note or "").strip(), int(time.time())),
            )
            row = connection.execute(
                "SELECT id, valid_from, price_per_kwh, note, created_ts FROM tariffs WHERE valid_from = ?",
                (valid_from,),
            ).fetchone()
        return {
            "id": int(row["id"]),
            "valid_from": row["valid_from"],
            "price_per_kwh": _number(row["price_per_kwh"]),
            "note": row["note"] or "",
            "created_ts": int(row["created_ts"]),
        }

    def tariff_delete(self, tariff_id: int) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute("DELETE FROM tariffs WHERE id = ?", (int(tariff_id),))
        return bool(cursor.rowcount)

    def tariff_for_date(self, date_str: str) -> float | None:
        """Price effective on date_str; dates before the first tariff use it too."""
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT price_per_kwh FROM tariffs WHERE valid_from <= ? ORDER BY valid_from DESC LIMIT 1",
                (date_str,),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT price_per_kwh FROM tariffs ORDER BY valid_from LIMIT 1"
                ).fetchone()
        return _number(row["price_per_kwh"]) if row else None

    # Accumulated counters used by finance(): payload paths and output fields.
    ACCUMULATED_PATHS = {
        "pv": ("status", "charger", "accumulated_pv_power_kwh"),
        "load": ("status", "inverter", "accumulated_load_power_kwh"),
        "buy": ("status", "inverter", "accumulated_buy_power_kwh"),
        "sell": ("status", "inverter", "accumulated_sell_power_kwh"),
        "charge": ("status", "inverter", "accumulated_charger_power_kwh"),
        "discharge": ("status", "inverter", "accumulated_discharger_power_kwh"),
        "grid_charge": ("status", "inverter", "accumulated_grid_charger_power_kwh"),
    }

    @classmethod
    def _accumulated_from_payload(cls, payload: dict[str, Any] | None) -> dict[str, float] | None:
        """Read the inverter's hardware energy counters from a stored frame.

        All seven counters must be present and finite; otherwise the frame
        cannot anchor a counter-based day and finance() falls back to the
        power-integration path."""
        if not isinstance(payload, dict):
            return None
        values: dict[str, float] = {}
        for key, path in cls.ACCUMULATED_PATHS.items():
            node: Any = payload
            for part in path:
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    break
            if not isinstance(node, (int, float)) or not math.isfinite(node) or node < 0:
                return None
            values[key] = float(node)
        return values

    def _boundary_payload(self, before_ts: int) -> dict[str, Any] | None:
        """Last frame stored strictly before before_ts (its payload JSON)."""
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM samples WHERE master_id = ? AND captured_ts < ? "
                "ORDER BY captured_ts DESC LIMIT 1",
                (self.master_id, int(before_ts)),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def finance(
        self,
        days: int = 2,
        tz_offset_minutes: int = 0,
        now_ts: int | None = None,
    ) -> dict[str, Any]:
        """Per-day energy and money totals.

        Preferred source: the inverter's hardware accumulated counters
        (0.1 kWh resolution, decoded into every stored frame). The day value
        is counter(end of day) - counter(before midnight) - exact, immune to
        load spikes and independent of the poll rate. Days whose frames lack
        usable counters fall back to power integration over hourly buckets
        (row["source"] == "integration"). Local day boundaries come from the
        client-provided UTC offset (JS getTimezoneOffset() convention:
        UTC+3 arrives as -180); money uses the tariff effective on that
        date, so tariff edits reprice the past instantly.
        """
        days = max(1, min(int(days), 400))
        tzoff_s = int(tz_offset_minutes) * 60
        now_ts = int(now_ts if now_ts is not None else time.time())
        local_now = now_ts - tzoff_s
        midnight_local = local_now - (local_now % 86400)
        range_start = midnight_local + tzoff_s - (days - 1) * 86400

        query = """
            SELECT strftime('%Y-%m-%dT%H:00:00Z', captured_at) AS bucket,
                   AVG(pv_power_w) AS pv_w, AVG(load_power_w) AS load_w,
                   AVG(grid_power_w) AS grid_w, AVG(battery_power_w) AS batt_w
            FROM samples WHERE captured_ts >= ? AND captured_ts <= ?
            GROUP BY bucket ORDER BY bucket
        """
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, (range_start, now_ts)).fetchall()

        day_order: list[str] = []
        totals: dict[str, dict[str, float]] = {}

        def day_row(key: str) -> dict[str, float]:
            if key not in totals:
                day_order.append(key)
                totals[key] = {
                    "pv_wh": 0.0, "load_wh": 0.0, "grid_buy_wh": 0.0, "grid_sell_wh": 0.0,
                    "batt_charge_wh": 0.0, "batt_charge_pv_wh": 0.0, "batt_charge_grid_wh": 0.0,
                    "batt_discharge_wh": 0.0, "hours": 0.0,
                }
            return totals[key]

        for row in rows:
            try:
                hour_start = int(datetime.strptime(
                    row["bucket"], "%Y-%m-%dT%H:00:00Z"
                ).replace(tzinfo=timezone.utc).timestamp())
            except (TypeError, ValueError):
                continue
            clip_from = max(hour_start, range_start)
            clip_to = min(hour_start + 3600, now_ts)
            weight_h = (clip_to - clip_from) / 3600
            if weight_h <= 0:
                continue
            day = day_row(time.strftime("%Y-%m-%d", time.gmtime(hour_start - tzoff_s)))
            pv_w = max(0.0, _number(row["pv_w"]) or 0.0)
            load_w = max(0.0, _number(row["load_w"]) or 0.0)
            grid_w = _number(row["grid_w"]) or 0.0
            batt_w = _number(row["batt_w"]) or 0.0
            day["pv_wh"] += pv_w * weight_h
            day["load_wh"] += load_w * weight_h
            # HIDEN sign convention (verified on live hardware): grid < 0 = buying.
            day["grid_buy_wh"] += max(0.0, -grid_w) * weight_h
            day["grid_sell_wh"] += max(0.0, grid_w) * weight_h
            charge_wh = max(0.0, -batt_w) * weight_h
            discharge_wh = max(0.0, batt_w) * weight_h
            day["batt_charge_wh"] += charge_wh
            day["batt_discharge_wh"] += discharge_wh
            # Hour-level attribution: PV surplus feeds the battery first, the
            # rest of the charge is billed to the grid (SolarUse-style logic).
            surplus_pv_wh = max(0.0, pv_w - load_w) * weight_h
            from_pv = min(charge_wh, surplus_pv_wh)
            day["batt_charge_pv_wh"] += from_pv
            day["batt_charge_grid_wh"] += max(0.0, charge_wh - from_pv)
            day["hours"] += weight_h

        rows_out = []
        for key in day_order:
            data = totals[key]
            tariff = self.tariff_for_date(key)
            row = {
                "date": key,
                "hours": round(data["hours"], 3),
                "pv_kwh": round(data["pv_wh"] / 1000, 4),
                "load_kwh": round(data["load_wh"] / 1000, 4),
                "grid_buy_kwh": round(data["grid_buy_wh"] / 1000, 4),
                "grid_sell_kwh": round(data["grid_sell_wh"] / 1000, 4),
                "batt_charge_kwh": round(data["batt_charge_wh"] / 1000, 4),
                "batt_charge_from_pv_kwh": round(data["batt_charge_pv_wh"] / 1000, 4),
                "batt_charge_from_grid_kwh": round(data["batt_charge_grid_wh"] / 1000, 4),
                "batt_discharge_kwh": round(data["batt_discharge_wh"] / 1000, 4),
                "tariff": tariff,
                "pv_savings": round(data["pv_wh"] / 1000 * tariff, 4) if tariff else None,
                "grid_buy_cost": round(data["grid_buy_wh"] / 1000 * tariff, 4) if tariff else None,
                "charge_grid_cost": round(data["batt_charge_grid_wh"] / 1000 * tariff, 4) if tariff else None,
                "source": "integration",
            }
            if tariff:
                row["net"] = round((row["pv_savings"] or 0) - (row["grid_buy_cost"] or 0), 4)
            else:
                row["net"] = None
            rows_out.append(row)

        # Counter-based override: replace the integration values with exact
        # hardware-counter deltas wherever day boundaries have usable frames.
        day_keys = {row["date"] for row in rows_out}
        for key in sorted(day_keys):
            try:
                day_index = (date.fromisoformat(key) - date.fromisoformat(
                    time.strftime("%Y-%m-%d", time.gmtime(midnight_local)))).days
                day_start = midnight_local + tzoff_s + day_index * 86400
            except ValueError:
                continue
            day_end = min(day_start + 86400, now_ts)
            if day_end <= day_start:
                continue
            base_payload = self._boundary_payload(day_start)
            final_payload = self._boundary_payload(day_end)
            base = self._accumulated_from_payload(base_payload)
            final = self._accumulated_from_payload(final_payload)
            if not base or not final:
                continue
            deltas = {key2: final[key2] - base[key2] for key2 in base}
            if any(delta < 0 for delta in deltas.values()):
                continue  # counters were reset mid-day: keep integration
            row = next((r for r in rows_out if r["date"] == key), None)
            if row is None:
                continue
            tariff = row["tariff"]
            row.update({
                "pv_kwh": round(deltas["pv"], 4),
                "load_kwh": round(deltas["load"], 4),
                "grid_buy_kwh": round(deltas["buy"], 4),
                "grid_sell_kwh": round(deltas["sell"], 4),
                "batt_charge_kwh": round(deltas["charge"], 4),
                "batt_charge_from_grid_kwh": round(deltas["grid_charge"], 4),
                "batt_charge_from_pv_kwh": round(max(0.0, deltas["charge"] - deltas["grid_charge"]), 4),
                "batt_discharge_kwh": round(deltas["discharge"], 4),
                "source": "counters",
            })
            if tariff:
                row["pv_savings"] = round(deltas["pv"] * tariff, 4)
                row["grid_buy_cost"] = round(deltas["buy"] * tariff, 4)
                row["charge_grid_cost"] = round(deltas["grid_charge"] * tariff, 4)
                row["net"] = round(row["pv_savings"] - row["grid_buy_cost"], 4)
        return {
            "days": days,
            "tz_offset_minutes": int(tz_offset_minutes),
            "rows": rows_out,
        }

    def prune(self, retention_days: int) -> dict[str, int]:
        cutoff = int(time.time()) - retention_days * 86400
        with self._lock, self._connection() as connection:
            samples = connection.execute("DELETE FROM samples WHERE captured_ts < ?", (cutoff,))
            battery = connection.execute("DELETE FROM battery_samples WHERE captured_ts < ?", (cutoff,))
            return {"samples": samples.rowcount, "battery_samples": battery.rowcount}

    def history(
        self,
        start_ts: int,
        end_ts: int,
        period: str,
        max_raw_points: int = 20000,
    ) -> dict[str, Any]:
        period = {"1m": "minute", "30min": "30m"}.get(period, period)
        if period == "raw":
            return self._raw_history(start_ts, end_ts, max_raw_points)
        if period not in {"minute", "30m", "hour", "day", "week", "month"}:
            raise ValueError("period must be raw, minute, 30m, hour, day, week, or month")

        bucket_expression = {
            "minute": "strftime('%Y-%m-%dT%H:%M:00Z', captured_at)",
            "30m": (
                "strftime('%Y-%m-%dT%H:', captured_at) || "
                "printf('%02d:00Z', (CAST(strftime('%M', captured_at) AS INTEGER) / 30) * 30)"
            ),
            "hour": "strftime('%Y-%m-%dT%H:00:00Z', captured_at)",
            "day": "strftime('%Y-%m-%dT00:00:00Z', captured_at)",
            "week": (
                "strftime('%Y-%m-%dT00:00:00Z', date(captured_at, "
                "'-' || ((CAST(strftime('%w', captured_at) AS INTEGER) + 6) % 7) || ' days'))"
            ),
            "month": "strftime('%Y-%m-01T00:00:00Z', captured_at)",
        }[period]
        average_columns = ", ".join(f"AVG({column}) AS {column}" for column in METRIC_COLUMNS)
        min_max_columns = ", MIN(load_power_w) AS load_power_min_w, MAX(load_power_w) AS load_power_max_w"
        query = f"""
            SELECT bucket, COUNT(*) AS samples, {average_columns}{min_max_columns}
            FROM (
                SELECT captured_at, {', '.join(METRIC_COLUMNS)}, {bucket_expression} AS bucket
                FROM samples
                WHERE captured_ts >= ? AND captured_ts <= ?
            )
            GROUP BY bucket
            ORDER BY bucket
        """
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, (start_ts, end_ts)).fetchall()

        points = []
        for row in rows:
            point = {"captured_at": row["bucket"], "samples": row["samples"]}
            for column in METRIC_COLUMNS:
                point[column] = _number(row[column])
            point["load_power_min_w"] = _number(row["load_power_min_w"])
            point["load_power_max_w"] = _number(row["load_power_max_w"])
            points.append(point)
        return {
            "from": _iso_from_ts(start_ts),
            "to": _iso_from_ts(end_ts),
            "period": period,
            "truncated": False,
            "points": points,
        }

    def _raw_history(self, start_ts: int, end_ts: int, limit: int) -> dict[str, Any]:
        selected = ", ".join(("captured_at", "captured_ts", "connection_status", *METRIC_COLUMNS))
        with self._lock, self._connection() as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM samples WHERE captured_ts >= ? AND captured_ts <= ?",
                (start_ts, end_ts),
            ).fetchone()
            rows = connection.execute(
                f"SELECT {selected} FROM ("
                f"SELECT {selected} FROM samples WHERE captured_ts >= ? AND captured_ts <= ? "
                "ORDER BY captured_ts DESC LIMIT ?"
                ") ORDER BY captured_ts",
                (start_ts, end_ts, limit),
            ).fetchall()

        truncated = int(count_row["count"]) > limit
        points = []
        for row in rows[:limit]:
            point = {
                "captured_at": row["captured_at"],
                "captured_ts": row["captured_ts"],
                "connection_status": row["connection_status"],
            }
            point.update({column: _number(row[column]) for column in METRIC_COLUMNS})
            points.append(point)
        return {
            "from": _iso_from_ts(start_ts),
            "to": _iso_from_ts(end_ts),
            "period": "raw",
            "truncated": truncated,
            "points": points,
        }

    # ------------------------------------------------------------------ battery

    def insert_battery_frame(
        self,
        captured_at: str,
        captured_ts: int,
        modules: list[dict[str, Any]],
        master_id: str | None = None,
    ) -> int:
        """Insert per-module battery rows for one frame. Returns rows inserted."""
        if not modules:
            return 0
        columns = (
            "master_id", "captured_at", "captured_ts", "module_index", "module_serial",
            "soc_percent", "voltage_v", "current_a", "temp_min_c", "temp_max_c",
            "cell_voltage_min_v", "cell_voltage_max_v", "cell_delta_v",
            "soh_percent", "cycles", "protection_bits", "alarm_bits", "payload_json",
        )
        placeholders = ", ".join("?" for _ in columns)
        inserted = 0
        with self._lock, self._connection() as connection:
            for module in modules:
                metrics = module.get("metrics", {})
                cursor = connection.execute(
                    f"INSERT INTO battery_samples ({', '.join(columns)}) VALUES ({placeholders}) "
                    "ON CONFLICT(master_id, captured_ts, module_index) DO NOTHING",
                    [
                        master_id or self.master_id,
                        captured_at,
                        captured_ts,
                        int(module.get("module_index", 0)),
                        module.get("module_serial"),
                        metrics.get("soc_percent"),
                        metrics.get("voltage_v"),
                        metrics.get("current_a"),
                        metrics.get("temp_min_c"),
                        metrics.get("temp_max_c"),
                        metrics.get("cell_voltage_min_v"),
                        metrics.get("cell_voltage_max_v"),
                        metrics.get("cell_delta_v"),
                        metrics.get("soh_percent"),
                        metrics.get("cycles"),
                        metrics.get("protection_bits"),
                        metrics.get("alarm_bits"),
                        json.dumps(module.get("payload", module), ensure_ascii=False, separators=(",", ":")),
                    ],
                )
                inserted += cursor.rowcount
        return inserted

    # ------------------------------------------------------------------ forward_state

    def forward_state(self, receiver_name: str) -> dict[str, Any]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM forward_state WHERE receiver_name = ?", (receiver_name,)
            ).fetchone()
        state = dict(FORWARD_RESULT_DEFAULTS)
        if row:
            state.update({key: row[key] for key in state if key in row.keys()})
        return state

    def all_forward_states(self) -> dict[str, dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute("SELECT * FROM forward_state").fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            state = dict(FORWARD_RESULT_DEFAULTS)
            state.update({key: row[key] for key in state if key in row.keys()})
            result[row["receiver_name"]] = state
        return result

    def save_forward_state(self, receiver_name: str, **updates: Any) -> None:
        allowed = set(FORWARD_RESULT_DEFAULTS)
        clean = {key: value for key, value in updates.items() if key in allowed}
        clean["updated_ts"] = int(time.time())
        state = self.forward_state(receiver_name)
        state.update(clean)
        columns = ("receiver_name", *FORWARD_RESULT_DEFAULTS)
        placeholders = ", ".join("?" for _ in columns)
        assignments = ", ".join(f"{column} = excluded.{column}" for column in FORWARD_RESULT_DEFAULTS)
        with self._lock, self._connection() as connection:
            connection.execute(
                f"INSERT INTO forward_state ({', '.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT(receiver_name) DO UPDATE SET {assignments}",
                [receiver_name, *[state[column] for column in FORWARD_RESULT_DEFAULTS]],
            )

    # ------------------------------------------------------------------ seed tokens

    def add_seed_token(
        self,
        token: str,
        seed_id: str,
        label: str | None,
        ttl_hours: int,
        max_downloads: int,
    ) -> dict[str, Any]:
        created = int(time.time())
        row = {
            "token_hash": _hash_token(token),
            "seed_id": seed_id,
            "label": label,
            "created_ts": created,
            "expires_ts": created + ttl_hours * 3600,
            "max_downloads": max_downloads,
            "downloads_used": 0,
            "last_used_ts": None,
            "revoked": 0,
        }
        columns = tuple(row)
        placeholders = ", ".join("?" for _ in columns)
        with self._lock, self._connection() as connection:
            connection.execute(
                f"INSERT INTO seed_tokens ({', '.join(columns)}) VALUES ({placeholders})",
                [row[column] for column in columns],
            )
        return row

    def consume_seed_token(self, token: str) -> dict[str, Any] | None:
        """Validate a seed download token and count one download. None when rejected."""
        token_hash = _hash_token(token)
        now = int(time.time())
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM seed_tokens WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if row is None or row["revoked"]:
                return None
            if now > int(row["expires_ts"]):
                return None
            if int(row["downloads_used"]) >= int(row["max_downloads"]):
                return None
            connection.execute(
                "UPDATE seed_tokens SET downloads_used = downloads_used + 1, last_used_ts = ? "
                "WHERE token_hash = ?",
                (now, token_hash),
            )
            result = {key: row[key] for key in row.keys()}
            result["downloads_used"] = int(row["downloads_used"]) + 1
            return result

    def list_seed_tokens(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM seed_tokens ORDER BY created_ts DESC, rowid DESC"
            ).fetchall()
        now = int(time.time())
        result = []
        for row in rows:
            item = {key: row[key] for key in row.keys()}
            if item["revoked"]:
                item["status"] = "revoked"
            elif now > int(item["expires_ts"]):
                item["status"] = "expired"
            elif int(item["downloads_used"]) >= int(item["max_downloads"]):
                item["status"] = "exhausted"
            else:
                item["status"] = "active"
            result.append(item)
        return result

    def revoke_seed_token(self, token_hash: str) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "UPDATE seed_tokens SET revoked = 1 WHERE token_hash = ?", (token_hash,)
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------ master events

    def add_master_event(self, event: str, detail: str | None = None, ts: int | None = None) -> None:
        now = int(ts or time.time())
        cutoff = int(time.time()) - EVENT_RETENTION_DAYS * 86400
        with self._lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO master_events (ts, event, detail) VALUES (?, ?, ?)",
                (now, event, detail),
            )
            connection.execute("DELETE FROM master_events WHERE ts < ?", (cutoff,))

    def recent_master_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT ts, event, detail FROM master_events ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"ts": int(row["ts"]), "event": row["event"], "detail": row["detail"], "at": _iso_from_ts(row["ts"])}
            for row in rows
        ]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else round(numeric, 3)


def _iso_from_ts(value: Any) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), timezone.utc).isoformat().replace("+00:00", "Z")
