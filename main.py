"""SolarBridge entry point (systemd runs `python main.py`).

Reads Settings from .env, picks the role and serves until SIGTERM/SIGINT:
  - master  (`SB_SOURCE_MODE=serial`):  poller + forwarder + dashboard;
  - receiver (`SB_SOURCE_MODE=ingest`): ingest + master-state + dashboard.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time

from solarbridge import __version__
from solarbridge.auth import AuthStore
from solarbridge.config import Settings
from solarbridge.forwarder import Forwarder
from solarbridge.hoststats import DiskGuard, HostStats
from solarbridge.http import AppContext, DashboardServer
from solarbridge.poller import EventHub, InverterPoller
from solarbridge.receiver import MasterState
from solarbridge.storage import Storage


LOGGER = logging.getLogger("solarbridge")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_master(settings: Settings, storage: Storage) -> tuple[DashboardServer, InverterPoller, Forwarder, Any | None]:
    """Master role: poll the inverter over RS485, store frames, forward to receivers."""
    battery_poller = None
    battery_supplier = None
    battery_health = None
    if settings.battery_mode == "serial":
        if not settings.battery_serial_port:
            LOGGER.warning("battery mode is 'serial' but SB_BATTERY_SERIAL_PORT is empty; battery disabled")
        elif not settings.battery_addresses:
            LOGGER.warning(
                "battery mode is 'serial' but SB_BATTERY_ADDRESSES is empty; "
                "set module DIP addresses (e.g. SB_BATTERY_ADDRESSES=2,3); battery disabled"
            )
        else:
            from solarbridge.battery import BatteryPoller, detect_client

            client = detect_client(settings)
            if client is not None:
                battery_poller = BatteryPoller(settings, client, settings.battery_addresses)
                battery_supplier = battery_poller.latest_modules
                battery_health = battery_poller.health
            else:
                LOGGER.warning(
                    "battery mode is 'serial' but no battery answered on %s (addresses %s)",
                    settings.battery_serial_port, ",".join(str(a) for a in settings.battery_addresses),
                )

    events = EventHub()
    # Disk guard pauses local writes when free space drops below the
    # threshold; forwarded frames keep flowing via the live passthrough.
    disk_guard = (
        DiskGuard(settings.db_path.parent, settings.disk_min_free_percent)
        if settings.disk_min_free_percent > 0
        else None
    )
    poller = InverterPoller(
        settings, storage, events, battery_supplier=battery_supplier, disk_guard=disk_guard
    )
    host_provider = (
        HostStats(watch_dir=settings.db_path.parent).snapshot if settings.host_stats else None
    )
    forwarder = Forwarder(
        settings, storage, poller, battery_health=battery_health, host_provider=host_provider
    )
    # When storage is paused, the poller hands frames to the forwarder directly.
    poller.live_sink = forwarder.enqueue_live
    auth_store = (
        AuthStore(settings.user_list_path, settings.db_path.parent / "auth_tokens.json")
        if settings.auth_enabled
        else None
    )
    context = AppContext(
        settings=settings,
        storage=storage,
        poller=poller,
        battery_health=battery_health,
        host_provider=host_provider,
        auth_store=auth_store,
    )
    server = DashboardServer((settings.host, settings.port), context)

    def stop(*_args: object) -> None:
        threading.Thread(target=server.shutdown, name="solarbridge-shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poller.start()
    forwarder.start()
    if battery_poller is not None:
        battery_poller.start()
    LOGGER.info(
        "SolarBridge %s master listening at http://%s:%s (master_id=%s)",
        __version__, settings.host, settings.port, settings.master_id,
    )
    if not settings.ingest_token:
        pass  # master does not need an ingest token; receivers do
    return server, poller, forwarder, battery_poller


def run_receiver(settings: Settings, storage: Storage) -> DashboardServer:
    """Receiver role: ingest frames from a master and serve a full mirror."""
    if not settings.ingest_token:
        LOGGER.warning(
            "SB_INGEST_TOKEN is empty: receivers will reject ingest until a token is configured"
        )
    master_state = MasterState(storage, offline_after_s=settings.offline_after_s)
    auth_store = (
        AuthStore(settings.user_list_path, settings.db_path.parent / "auth_tokens.json")
        if settings.auth_enabled
        else None
    )
    context = AppContext(
        settings=settings, storage=storage, master_state=master_state, auth_store=auth_store
    )
    server = DashboardServer((settings.host, settings.port), context)
    storage.set_master_id(settings.master_id)

    def stop(*_args: object) -> None:
        threading.Thread(target=server.shutdown, name="solarbridge-shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def tick() -> None:
        last_prune = 0.0
        while not server._BaseServer__shutdown_request:  # noqa: SLF001 - loop until server stops
            for event in master_state.tick():
                storage.add_master_event(event["event"], event["detail"])
            if time.monotonic() - last_prune >= 21600:
                deleted = storage.prune(settings.retention_days)
                last_prune = time.monotonic()
                if deleted.get("samples"):
                    LOGGER.info("pruned %s samples", deleted["samples"])
            time.sleep(5.0)

    threading.Thread(target=tick, name="solarbridge-receiver-tick", daemon=True).start()
    LOGGER.info(
        "SolarBridge %s receiver listening at http://%s:%s",
        __version__, settings.host, settings.port,
    )
    return server


def main() -> int:
    settings = Settings.from_env()
    _configure_logging()
    storage = Storage(settings.db_path, master_id=settings.master_id)

    if settings.is_master:
        server, poller, forwarder, battery_poller = run_master(settings, storage)
    else:
        server = run_receiver(settings, storage)
        poller = forwarder = battery_poller = None

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        if forwarder is not None:
            forwarder.stop()
        if poller is not None:
            poller.stop()
        if battery_poller is not None:
            battery_poller.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
