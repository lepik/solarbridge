"""Master-side forwarder: pushes frames and heartbeats to receivers.

Design (frozen):
- receivers.list is the source of truth (name | url | token | on/off), hot reloaded.
- Truth lives at the receiver: hello returns the receiver's last stored sample ts.
- One worker thread per receiver; frames > watermark are batched oldest-first.
- Idempotency: UNIQUE(master_id, captured_ts) on the receiver, so re-sends are safe.
- Window limit: rows older than SB_FORWARD_BACKFILL_DAYS are never sent; a receiver
  that fell behind the window must be reseeded.
- Heartbeats (15 s) carry the inverter/battery bus state and are fire-and-forget.
"""

from __future__ import annotations

import copy
import gzip
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .config import Settings
from .poller import InverterPoller
from .storage import SCHEMA_VERSION, Storage


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Receiver:
    name: str
    url: str
    token: str
    enabled: bool


def parse_receivers(text: str) -> tuple[list[Receiver], list[str]]:
    """Parse receivers.list content. Malformed lines are reported, not fatal."""
    receivers: list[Receiver] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            errors.append(f"line {line_no}: expected 'name | url | token | on/off'")
            continue
        name, url, token, flag = parts
        if not name or not url or not token:
            errors.append(f"line {line_no}: name, url and token are required")
            continue
        enabled = flag.lower() in {"on", "yes", "true", "1"}
        if flag.lower() not in {"on", "off", "yes", "no", "true", "false", "1", "0"}:
            errors.append(f"line {line_no}: unknown state '{flag}' (use on/off)")
            continue
        if name in seen:
            errors.append(f"line {line_no}: duplicate name '{name}'")
            continue
        seen.add(name)
        receivers.append(Receiver(name=name, url=url.rstrip("/"), token=token, enabled=enabled))
    return receivers, errors


def build_frame_payload(
    master_id: str,
    app_version: str,
    schema_version: int,
    rows: list[dict[str, Any]],
    battery_by_ts: dict[int, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    frames = []
    for row in rows:
        frame: dict[str, Any] = {
            "captured_at": row["captured_at"],
            "captured_ts": row["captured_ts"],
            "inverter": row["snapshot"],
        }
        if battery_by_ts and row["captured_ts"] in battery_by_ts:
            frame["battery"] = {"modules": battery_by_ts[row["captured_ts"]]}
        frames.append(frame)
    return {
        "master_id": master_id,
        "app_version": app_version,
        "schema_version": schema_version,
        "frames": frames,
    }


def build_heartbeat(
    master_id: str,
    app_version: str,
    schema_version: int,
    uptime_s: float,
    poller: InverterPoller | None,
    battery_health: dict[str, Any] | None = None,
    host_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = poller.health() if poller else {}
    bus: dict[str, Any] = {
        "inverter": {
            "ok": health.get("status") in {"online", "degraded"},
            "last_ok_ts": health.get("last_success_at"),
            "last_error": health.get("last_error"),
            "consecutive_errors": health.get("consecutive_failures") or 0,
        }
    }
    if battery_health is not None:
        bus["battery"] = battery_health
    heartbeat = {
        "master_id": master_id,
        "sent_at": _utc_now(),
        "app_version": app_version,
        "schema_version": schema_version,
        "uptime_s": round(uptime_s, 1),
        "last_frame_ts": None,
        "bus": bus,
    }
    if host_stats is not None:
        # Subset for the «09 / МАШИНА» section on receivers: machine load,
        # temperature and power health. Full payload stays on the master.
        heartbeat["host"] = host_stats
    return heartbeat


class ReceiverWorker:
    def __init__(
        self,
        receiver: Receiver,
        settings: Settings,
        storage: Storage,
        poller: InverterPoller | None,
        parallel_semaphore: threading.Semaphore,
        started_at: float,
        battery_health: Callable[[], dict[str, Any]] | None = None,
        host_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.receiver = receiver
        self.settings = settings
        self.storage = storage
        self.poller = poller
        self.battery_health = battery_health
        self.host_provider = host_provider
        self._semaphore = parallel_semaphore
        self._started_at = started_at
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_acked_ts: int | None = None
        self._last_heartbeat_at = 0.0
        self._backoff = 0.0
        # Frames produced while the master's local storage is paused (disk
        # guard). Sent promptly, but they do NOT advance the watermark: the
        # receiver stores them idempotently, the master DB has no such rows.
        self.live_queue: queue.Queue = queue.Queue(maxsize=128)

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name=f"solarbridge-forward-{self.receiver.name}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def state(self) -> dict[str, Any]:
        return self.storage.forward_state(self.receiver.name)

    # ------------------------------------------------------------------ loop

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self.receiver.enabled:
                self.storage.save_forward_state(self.receiver.name, last_result="disabled")
                self._stop.wait(5.0)
                self._reload_receiver()
                continue
            try:
                if self._last_acked_ts is None:
                    self._hello()
                self._maybe_heartbeat()
                # Push even when hello returned None (empty receiver):
                # frames_after() caps the floor at the backfill window.
                self._push_frames()
                self._flush_live()
            except _HttpError as exc:
                self._record_failure(str(exc), exc.status)
            except Exception as exc:  # noqa: BLE001 - worker must survive anything
                self._record_failure(str(exc), None)
            wait = min(max(self._backoff, 0.5), 60.0)
            self._stop.wait(wait)

    def enqueue_live(self, frame: dict[str, Any]) -> None:
        """Queue a frame produced while local storage is paused (never blocks)."""
        try:
            self.live_queue.put_nowait(frame)
        except queue.Full:
            LOGGER.warning("live queue for %s is full - frame dropped", self.receiver.name)

    def _flush_live(self) -> None:
        frames: list[dict[str, Any]] = []
        while True:
            try:
                frames.append(self.live_queue.get_nowait())
            except queue.Empty:
                break
            if len(frames) >= self.settings.forward_batch:
                break
        if not frames:
            return
        rows = [
            {
                "captured_at": frame["captured_at"],
                "captured_ts": frame["captured_ts"],
                "snapshot": frame["inverter"],
            }
            for frame in frames
        ]
        battery_by_ts = {
            frame["captured_ts"]: frame["battery"]["modules"]
            for frame in frames
            if isinstance(frame.get("battery"), dict)
        }
        payload = build_frame_payload(
            self.settings.master_id, __version__, SCHEMA_VERSION, rows, battery_by_ts
        )
        with self._semaphore:
            self._post("/api/ingest/frames", payload)
        state = self.storage.forward_state(self.receiver.name)
        self.storage.save_forward_state(
            self.receiver.name,
            last_attempt_ts=int(time.time()),
            last_ok_ts=int(time.time()),
            last_result="ok-live",
            last_error=None,
            sent_total=state["sent_total"] + len(frames),
        )

    def _reload_receiver(self) -> None:
        updated = reload_receivers(self.settings.receivers_file)
        for receiver in updated:
            if receiver.name == self.receiver.name:
                self.receiver = receiver

    # ------------------------------------------------------------------ steps

    def _hello(self) -> None:
        payload = {
            "master_id": self.settings.master_id,
            "app_version": __version__,
            "schema_version": SCHEMA_VERSION,
        }
        response = self._post("/api/ingest/hello", payload, expect_json=True)
        last_ts = response.get("last_sample_ts")
        self._last_acked_ts = int(last_ts) if last_ts is not None else None
        window_start = int(time.time()) - self.settings.forward_backfill_days * 86400
        if self._last_acked_ts is not None and self._last_acked_ts < window_start:
            self.storage.save_forward_state(
                self.receiver.name,
                last_result="reseed_required",
                last_error=f"receiver is {int((time.time() - self._last_acked_ts) / 86400)} days behind",
            )
        else:
            self.storage.save_forward_state(self.receiver.name, last_result="hello", last_error=None)

    def _maybe_heartbeat(self) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat_at < self.settings.heartbeat_interval:
            return
        self._last_heartbeat_at = now
        heartbeat = build_heartbeat(
            self.settings.master_id,
            __version__,
            SCHEMA_VERSION,
            now - self._started_at,
            self.poller,
            self.battery_health() if self.battery_health is not None else None,
            self.host_provider() if self.host_provider is not None else None,
        )
        heartbeat["last_frame_ts"] = self.storage.last_sample_ts(self.settings.master_id)
        try:
            self._post("/api/ingest/heartbeat", heartbeat)
            # Heartbeat must not overwrite frame-level status ('ok'/'reseed_required');
            # it only refreshes the attempt timestamp.
            self.storage.save_forward_state(
                self.receiver.name,
                last_attempt_ts=int(time.time()),
            )
        except _HttpError as exc:
            # Heartbeats are fire-and-forget: never let them stall frame pushing.
            LOGGER.debug("heartbeat to %s failed: %s", self.receiver.name, exc)

    def _push_frames(self) -> None:
        window_start = int(time.time()) - self.settings.forward_backfill_days * 86400
        floor = max(self._last_acked_ts or 0, window_start) if self._last_acked_ts else window_start
        rows = self.storage.frames_after(floor, self.settings.forward_batch, self.settings.master_id)
        if not rows:
            return
        newest = rows[-1]["captured_ts"]
        battery = self.storage.battery_frames_after(floor, self.settings.forward_batch * 8, self.settings.master_id)
        payload = build_frame_payload(
            self.settings.master_id, __version__, SCHEMA_VERSION, rows, battery
        )
        with self._semaphore:
            response = self._post("/api/ingest/frames", payload, expect_json=True)
        acked = response.get("last_sample_ts")
        self._last_acked_ts = int(acked) if acked is not None else newest
        self._backoff = 0.0
        self.storage.save_forward_state(
            self.receiver.name,
            last_acked_ts=self._last_acked_ts,
            last_attempt_ts=int(time.time()),
            last_ok_ts=int(time.time()),
            last_result="ok",
            last_error=None,
            consecutive_failures=0,
            sent_total=self.storage.forward_state(self.receiver.name)["sent_total"] + len(rows),
            acked_total=self.storage.forward_state(self.receiver.name)["acked_total"]
            + int(response.get("accepted") or 0),
        )
        if len(rows) >= self.settings.forward_batch:
            self._stop.wait(self.settings.forward_pause_s)

    def _record_failure(self, error: str, status: int | None) -> None:
        self._backoff = min(max(self._backoff * 2, 2.0), 60.0)
        state = self.storage.forward_state(self.receiver.name)
        self.storage.save_forward_state(
            self.receiver.name,
            last_attempt_ts=int(time.time()),
            last_result=f"http_{status}" if status else "network",
            last_error=error[:300],
            consecutive_failures=state["consecutive_failures"] + 1,
        )
        LOGGER.warning("forward to %s failed: %s", self.receiver.name, error)

    def _post(self, path: str, payload: dict[str, Any], expect_json: bool = False) -> dict[str, Any] | None:
        url = f"{self.receiver.url}{path}"
        body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Authorization": f"Bearer {self.receiver.token}",
                "User-Agent": f"SolarBridge/{__version__}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raise _HttpError(f"HTTP {exc.code}: {exc.reason[:200]}", exc.code) from exc
        except Exception as exc:  # noqa: BLE001
            raise _HttpError(str(exc), None) from exc
        if status != 200:
            raise _HttpError(f"HTTP {status}", status)
        if expect_json:
            try:
                return json.loads(data.decode("utf-8"))
            except ValueError:
                raise _HttpError("invalid JSON response", status) from None
        return None


class _HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None) -> None:
        super().__init__(message)
        self.status = status


class Forwarder:
    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        poller: InverterPoller | None,
        battery_health: Callable[[], dict[str, Any]] | None = None,
        host_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.poller = poller
        self.battery_health = battery_health
        self.host_provider = host_provider
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._workers: dict[str, ReceiverWorker] = {}
        self._file_mtime: float | None = None
        self._semaphore = threading.Semaphore(settings.forward_parallel)
        self._started_at = time.monotonic()

    def start(self) -> None:
        threading.Thread(target=self._reload_loop, name="solarbridge-forward-supervisor", daemon=True).start()

    def enqueue_live(self, frame: dict[str, Any]) -> None:
        """Fan a storage-paused frame out to every active receiver worker."""
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            worker.enqueue_live(frame)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for worker in self._workers.values():
                worker.stop()
            self._workers.clear()

    def status(self) -> dict[str, Any]:
        receivers, errors = reload_receivers(self.settings.receivers_file)
        states = self.storage.all_forward_states()
        return {
            "receivers": [
                {"name": receiver.name, "url": receiver.url, "enabled": receiver.enabled,
                 "state": states.get(receiver.name, {})}
                for receiver in receivers
            ],
            "errors": errors,
        }

    # ------------------------------------------------------------------ supervisor

    def _reload_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sync_workers()
            except Exception:  # noqa: BLE001
                LOGGER.exception("forwarder reload failed")
            self._stop.wait(3.0)

    def _sync_workers(self) -> None:
        path = Path(self.settings.receivers_file)
        mtime = path.stat().st_mtime if path.is_file() else None
        with self._lock:
            if mtime == self._file_mtime:
                return
            self._file_mtime = mtime
            receivers, errors = reload_receivers(self.settings.receivers_file)
            for error in errors:
                LOGGER.warning("receivers.list: %s", error)
            wanted = {receiver.name: receiver for receiver in receivers}
            for name in list(self._workers):
                if name not in wanted:
                    self._workers[name].stop()
                    del self._workers[name]
            for name, receiver in wanted.items():
                if name not in self._workers:
                    worker = ReceiverWorker(
                        receiver,
                        self.settings,
                        self.storage,
                        self.poller,
                        self._semaphore,
                        self._started_at,
                        self.battery_health,
                        self.host_provider,
                    )
                    self._workers[name] = worker
                    worker.start()
                else:
                    self._workers[name].receiver = receiver


def reload_receivers(path: Path | str) -> tuple[list[Receiver], list[str]]:
    path = Path(path)
    if not path.is_file():
        return [], []
    return parse_receivers(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
