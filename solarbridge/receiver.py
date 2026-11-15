"""Receiver-side master state tracking.

The receiver keeps the master's health in memory (heartbeats are not stored)
and records only state *transitions* into master_events, so diagnostics
survive restarts without growing the database.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from . import __version__
from .storage import Storage


MASTER_ALIVE = "alive"
MASTER_BUS_ERROR = "bus_error"
MASTER_OFFLINE = "offline"
MASTER_UNKNOWN = "unknown"


class MasterState:
    def __init__(self, storage: Storage, offline_after_s: int = 180) -> None:
        self.storage = storage
        self.offline_after_s = offline_after_s
        self._lock = threading.RLock()
        self._state = MASTER_UNKNOWN
        self._last_heartbeat_ts: float | None = None
        self._last_frame_ts: int | None = None
        self._last_frame_at: str | None = None
        self._master_id: str | None = None
        self._master_app_version: str | None = None
        self._master_service_uptime_s: float | None = None
        self._bus: dict[str, Any] = {}
        self._host: dict[str, Any] | None = None
        self._offline_threshold_s = 45.0

    # ------------------------------------------------------------------ input

    def on_heartbeat(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        now = time.time()
        events: list[dict[str, str]] = []
        with self._lock:
            previous = self._state
            previous_version = self._master_app_version
            bus_error_active = self._bus_has_error(payload.get("bus") or {})
            self._last_heartbeat_ts = now
            self._master_id = payload.get("master_id")
            self._master_app_version = payload.get("app_version")
            self._master_service_uptime_s = payload.get("uptime_s")
            self._bus = payload.get("bus") or {}
            self._host = payload.get("host") if isinstance(payload.get("host"), dict) else None
            if payload.get("last_frame_ts"):
                self._last_frame_ts = int(payload["last_frame_ts"])
            # Stay in bus_error while the bus stays broken; do not reset to alive.
            self._state = MASTER_BUS_ERROR if bus_error_active else MASTER_ALIVE
        if previous in {MASTER_OFFLINE, MASTER_UNKNOWN}:
            events.append({"event": "master_alive", "detail": f"app={payload.get('app_version')}"})
        if previous_version and payload.get("app_version") and previous_version != payload.get("app_version"):
            events.append(
                {"event": "master_version", "detail": f"app={payload.get('app_version')} (was {previous_version})"}
            )
        if bus_error_active and previous != MASTER_BUS_ERROR:
            events.append(
                {"event": "bus_error", "detail": self._bus_error_detail(self._bus)}
            )
        return events

    def on_frames(self, master_id: str, captured_ts: int, captured_at: str) -> list[dict[str, str]]:
        now = time.time()
        with self._lock:
            previous = self._state
            self._last_frame_ts = int(captured_ts)
            self._last_frame_at = captured_at
            if self._master_id is None:
                self._master_id = master_id
            if previous == MASTER_BUS_ERROR:
                self._state = MASTER_ALIVE
                return [{"event": "bus_ok", "detail": f"frame captured_at={captured_at}"}]
            if previous == MASTER_UNKNOWN:
                self._state = MASTER_ALIVE
            return []

    def tick(self) -> list[dict[str, str]]:
        """Periodic evaluation of offline / bus-error transitions."""
        now = time.time()
        events: list[dict[str, str]] = []
        with self._lock:
            if self._state == MASTER_UNKNOWN:
                return events
            heartbeat_age = now - self._last_heartbeat_ts if self._last_heartbeat_ts else None
            if heartbeat_age is not None and heartbeat_age > self._offline_threshold_s:
                if self._state != MASTER_OFFLINE:
                    self._state = MASTER_OFFLINE
                    events.append({"event": "master_offline", "detail": f"no heartbeat for {int(heartbeat_age)}s"})
                return events
            frame_age = now - self._last_frame_ts if self._last_frame_ts else None
            if frame_age is not None and frame_age > self.offline_after_s:
                if self._state != MASTER_BUS_ERROR:
                    self._state = MASTER_BUS_ERROR
                    events.append(
                        {"event": "bus_error", "detail": f"no frames for {int(frame_age)}s while master alive"}
                    )
        return events

    # ------------------------------------------------------------------ output

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            heartbeat_age = (
                round(now - self._last_heartbeat_ts, 1) if self._last_heartbeat_ts else None
            )
            frame_age = round(now - self._last_frame_ts, 1) if self._last_frame_ts else None
            status = {MASTER_ALIVE: "online", MASTER_BUS_ERROR: "stale", MASTER_OFFLINE: "offline"}.get(
                self._state, "offline"
            )
            return {
                "version": __version__,
                "mode": "ingest",
                "master_state": self._state,
                "status": status,
                "master_id": self._master_id,
                "master_app_version": self._master_app_version,
                "master_service_uptime_s": self._master_service_uptime_s,
                "heartbeat_age_seconds": heartbeat_age,
                "frame_age_seconds": frame_age,
                "last_frame_at": self._last_frame_at,
                "bus": self._bus,
                "host": self._host,
            }

    def health(self) -> dict[str, Any]:
        """Health payload shaped like the master's, so the unchanged frontend works."""
        snap = self.snapshot()
        return {
            "version": __version__,
            "status": snap["status"],
            "mode": "ingest",
            "master_id": snap["master_id"],
            "master_state": snap["master_state"],
            "master_app_version": snap["master_app_version"],
            "master_service_uptime_s": snap["master_service_uptime_s"],
            "heartbeat_age_seconds": snap["heartbeat_age_seconds"],
            "frame_age_seconds": snap["frame_age_seconds"],
            "last_success_at": snap["last_frame_at"],
            "last_error": self._bus_error_detail(snap.get("bus") or {}),
            "consecutive_failures": None,
            "storage": self.storage.stats(),
        }

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _bus_has_error(bus: dict[str, Any]) -> bool:
        inverter = bus.get("inverter") or {}
        return bool(inverter.get("consecutive_errors")) or inverter.get("ok") is False

    @staticmethod
    def _bus_error_detail(bus: dict[str, Any]) -> str | None:
        inverter = bus.get("inverter") or {}
        error = inverter.get("last_error")
        if inverter.get("ok") is False or inverter.get("consecutive_errors"):
            return error or "inverter bus unhealthy"
        return None
