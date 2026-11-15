"""Environment configuration: Settings from .env with safe defaults.

The installer (install.py) writes .env; this module only reads it. Relative
paths resolve against the project directory. One Settings instance describes
either role: `serial` (master) or `ingest` (receiver).
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SERIAL_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


def _load_dotenv(path: Path) -> None:
    """Load a small .env file without adding a dotenv dependency."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _float_env(name: str, default: float, minimum: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(value, minimum)


def _int_env(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(value, minimum)


def _str_env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value.strip() if value is not None else default


def default_master_id() -> str:
    override = _str_env("SB_MASTER_ID")
    if override:
        return override
    hostname = socket.gethostname().strip()
    return hostname or "solarbridge"


def _user_list_path() -> Path:
    path = Path(_str_env("SB_USER_LIST", str(BASE_DIR / "user_list")))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


SUFFIX_ALPHABET = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def random_master_suffix(length: int = 8) -> str:
    """Random install-time suffix for master_id, e.g. 'B349HCFD'.

    Generated once by the installer and persisted in .env: master_id feeds
    frame deduplication, so it must never change retroactively or be
    regenerated on every boot."""
    import secrets

    return "".join(secrets.choice(SUFFIX_ALPHABET) for _ in range(length))


def _addresses_env(name: str) -> tuple[int, ...]:
    """Parse 'SB_BATTERY_ADDRESSES=2,3' into a sorted, de-duplicated tuple of
    valid Modbus/paceic addresses (1..15). Malformed items are ignored."""
    addresses: set[int] = set()
    for item in _str_env(name).replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item, 0)
        except ValueError:
            continue
        if 1 <= value <= 15:
            addresses.add(value)
    return tuple(sorted(addresses))


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    public_dir: Path
    db_path: Path
    seed_dir: Path
    receivers_file: Path
    host: str
    port: int

    source_mode: str  # "serial" (master) | "ingest" (receiver)
    master_id: str

    serial_port: str
    slave_id: int
    baudrate: int
    serial_timeout: float
    inter_request_delay: float

    poll_interval: float
    sample_interval: float
    config_interval: float
    retention_days: int

    forward_backfill_days: int
    forward_batch: int
    forward_pause_s: float
    forward_parallel: int
    heartbeat_interval: float
    offline_after_s: int

    seed_max_age_days: int
    seed_token_ttl_hours: int
    seed_token_max_downloads: int

    ingest_token: str
    ingest_allowlist: tuple[str, ...]
    trust_proxy: bool

    battery_mode: str  # "off" | "serial"
    battery_serial_port: str
    battery_baudrate: int
    battery_protocol: str  # auto | ascii | modbus
    battery_commandset: str  # auto | 20 | 25 (deprecated: paceic variants are probed)
    battery_variant: str  # auto | v25 | v20 | pylon (Pylontech low voltage V3.3)
    battery_protocol_version: str
    battery_addresses: tuple[int, ...]  # explicit module addresses, 1..15; empty = disabled
    battery_cmd_gap_s: float
    battery_poll_interval: float
    host_stats: bool

    auth_enabled: bool
    user_list_path: Path
    disk_min_free_percent: float  # 0 = guard disabled

    @property
    def is_master(self) -> bool:
        return self.source_mode == "serial"

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(BASE_DIR / ".env")

        db_path = Path(os.environ.get("SB_DB_PATH", BASE_DIR / "data" / "solarbridge.sqlite3"))
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path
        seed_dir = Path(_str_env("SB_SEED_DIR", str(BASE_DIR / "data" / "seeds")))
        if not seed_dir.is_absolute():
            seed_dir = BASE_DIR / seed_dir
        receivers_file = Path(
            _str_env("SB_RECEIVERS_FILE", str(BASE_DIR / "receivers.list"))
        )
        if not receivers_file.is_absolute():
            receivers_file = BASE_DIR / receivers_file

        allowlist = tuple(
            item.strip()
            for item in _str_env("SB_INGEST_ALLOWLIST").replace(";", ",").split(",")
            if item.strip()
        )

        battery_mode = _str_env("SB_BATTERY_MODE", "off").lower()
        if battery_mode not in {"off", "serial"}:
            battery_mode = "off"

        source_mode = _str_env("SB_SOURCE_MODE", "serial").lower()
        if source_mode not in {"serial", "ingest"}:
            source_mode = "serial"

        return cls(
            base_dir=BASE_DIR,
            public_dir=BASE_DIR / "public",
            db_path=db_path,
            seed_dir=seed_dir,
            receivers_file=receivers_file,
            host=os.environ.get("SB_DASH_HOST", "127.0.0.1"),
            port=_int_env("SB_DASH_PORT", 8090, 1),
            source_mode=source_mode,
            master_id=default_master_id(),
            serial_port=os.environ.get("SB_SERIAL_PORT", DEFAULT_SERIAL_PORT),
            slave_id=_int_env("SB_SLAVE_ID", 4, 1),
            baudrate=_int_env("SB_BAUDRATE", 19200, 1200),
            serial_timeout=_float_env("SB_SERIAL_TIMEOUT", 2.5, 0.2),
            inter_request_delay=_float_env("SB_INTER_REQUEST_DELAY", 0.5, 0.0),
            poll_interval=_float_env("SB_POLL_INTERVAL", 15.0, 2.0),
            sample_interval=_float_env("SB_SAMPLE_INTERVAL", 60.0, 1.0),
            config_interval=_float_env("SB_CONFIG_INTERVAL", 300.0, 30.0),
            retention_days=_int_env("SB_RETENTION_DAYS", 730, 1),
            forward_backfill_days=_int_env("SB_FORWARD_BACKFILL_DAYS", 60, 0),
            forward_batch=_int_env("SB_FORWARD_BATCH", 240, 1),
            forward_pause_s=_float_env("SB_FORWARD_PAUSE_S", 1.0, 0.0),
            forward_parallel=max(1, _int_env("SB_FORWARD_PARALLEL", 2, 1)),
            heartbeat_interval=_float_env("SB_HEARTBEAT_INTERVAL", 15.0, 5.0),
            offline_after_s=_int_env("SB_OFFLINE_AFTER_S", 180, 30),
            seed_max_age_days=_int_env("SB_SEED_MAX_AGE_DAYS", 0, 0),
            seed_token_ttl_hours=_int_env("SB_SEED_TOKEN_TTL_HOURS", 24, 1),
            seed_token_max_downloads=_int_env("SB_SEED_TOKEN_MAX_DOWNLOADS", 10, 1),
            ingest_token=_str_env("SB_INGEST_TOKEN"),
            ingest_allowlist=allowlist,
            trust_proxy=_str_env("SB_TRUST_PROXY", "0").lower() in {"1", "true", "yes", "on"},
            battery_mode=battery_mode,
            battery_serial_port=_str_env("SB_BATTERY_SERIAL_PORT"),
            battery_baudrate=_int_env("SB_BATTERY_BAUDRATE", 9600, 1200),
            battery_protocol=_str_env("SB_BATTERY_PROTOCOL", "auto").lower(),
            battery_commandset=_str_env("SB_BATTERY_COMMANDSET", "auto").lower(),
            battery_variant=_str_env("SB_BATTERY_VARIANT", "auto").lower(),
            battery_protocol_version=_str_env("SB_BATTERY_PROTOCOL_VERSION"),
            battery_addresses=_addresses_env("SB_BATTERY_ADDRESSES"),
            battery_cmd_gap_s=_float_env("SB_BATTERY_CMD_GAP_S", 1.0, 0.1),
            battery_poll_interval=_float_env("SB_BATTERY_POLL_INTERVAL", 15.0, 5.0),
            host_stats=_str_env("SB_HOST_STATS", "1").lower() in {"1", "true", "yes", "on"},
            auth_enabled=_str_env("SB_AUTH", "0").lower() in {"1", "true", "yes", "on"},
            user_list_path=_user_list_path(),
            disk_min_free_percent=_float_env("SB_DISK_MIN_FREE_PERCENT", 10.0, 0.0),
        )
