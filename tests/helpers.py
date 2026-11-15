from __future__ import annotations

import sys
from pathlib import Path

from solarbridge.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_settings(tmp: Path, **overrides) -> Settings:
    fields = dict(
        base_dir=tmp,
        public_dir=PROJECT_ROOT / "public",
        db_path=tmp / "test.sqlite3",
        seed_dir=tmp / "seeds",
        receivers_file=tmp / "receivers.list",
        host="127.0.0.1",
        port=0,
        source_mode="serial",
        master_id="testmaster",
        serial_port="fake",
        slave_id=4,
        baudrate=19200,
        serial_timeout=0.2,
        inter_request_delay=0.0,
        poll_interval=15.0,
        sample_interval=60.0,
        config_interval=300.0,
        retention_days=730,
        forward_backfill_days=60,
        forward_batch=240,
        forward_pause_s=0.0,
        forward_parallel=2,
        heartbeat_interval=15.0,
        offline_after_s=180,
        seed_max_age_days=0,
        seed_token_ttl_hours=24,
        seed_token_max_downloads=10,
        ingest_token="",
        ingest_allowlist=(),
        trust_proxy=False,
        battery_mode="off",
        battery_serial_port="",
        battery_baudrate=9600,
        battery_protocol="auto",
        battery_commandset="auto",
        battery_variant="auto",
        battery_protocol_version="",
        battery_addresses=(),
        battery_cmd_gap_s=1.0,
        battery_poll_interval=15.0,
        host_stats=True,
        auth_enabled=False,
        user_list_path=tmp / "user_list",
        disk_min_free_percent=10.0,
    )
    fields.update(overrides)
    return Settings(**fields)


def snapshot(
    captured_at: str,
    load_power: float,
    master_extra: dict | None = None,
    metrics_extra: dict | None = None,
) -> dict:
    metrics = {
        "battery_voltage_v": 51.2,
        "pv_voltage_v": 120.0,
        "pv_power_w": 900,
        "inverter_voltage_v": 229.7,
        "grid_voltage_v": 230.6,
        "inverter_power_w": -220,
        "grid_power_w": -380,
        "load_power_w": load_power,
        "load_percent": 16,
        "inverter_frequency_hz": 49.95,
        "grid_frequency_hz": 49.95,
        "battery_power_w": 300,
        **(metrics_extra or {}),
    }
    return {
        "captured_at": captured_at,
        "connection": {"status": "online", "section_errors": {}},
        "metrics": metrics,
        **(master_extra or {}),
    }
