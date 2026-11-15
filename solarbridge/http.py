"""HTTP dashboard and ingest API (stdlib http.server, no framework).

One server serves both roles: the master gets dashboard + seed routes, the
receiver adds /api/ingest/* (Bearer token, IP allowlist, rate limiting).
Optional dashboard login (SB_AUTH) protects data endpoints with tokens from
user_list; ingest and seed keep their own authentication.
"""

from __future__ import annotations

import csv
import gzip
import io
import ipaddress
import json
import logging
import mimetypes
import queue
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .config import Settings
from .poller import InverterPoller
from .receiver import MasterState
from .storage import MIN_SUPPORTED_SCHEMA, SCHEMA_VERSION, Storage


LOGGER = logging.getLogger(__name__)

FRAME_KEYS = {"captured_at", "captured_ts", "inverter", "battery"}
MAX_BODY_BYTES = 64 * 1024 * 1024
AUTH_OPEN_PREFIXES = ("/api/ingest/", "/api/auth/", "/api/seed/")
AUTH_OPEN_PATHS = {"/healthz", "/api/auth/status", "/api/auth/login"}
AUTH_COOKIE = "sb_auth"
AUTH_COOKIE_MAX_AGE = 30 * 86400


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    storage: Storage
    poller: InverterPoller | None = None
    master_state: MasterState | None = None
    battery_health: Callable[[], dict[str, Any]] | None = None
    host_provider: Callable[[], dict[str, Any]] | None = None
    auth_store: Any = None  # solarbridge.auth.AuthStore when SB_AUTH is on
    started_at: float = field(default_factory=time.time)


class FailureLimiter:
    """Rate limit for failed (unauthenticated) ingest requests only."""

    def __init__(self, window_s: int = 60, max_failures: int = 30) -> None:
        self.window_s = window_s
        self.max_failures = max_failures
        self._lock = threading.Lock()
        self._events: dict[str, list[float]] = {}

    def check(self, ip: str) -> bool:
        """True when the request may proceed."""
        with self._lock:
            events = [ts for ts in self._events.get(ip, []) if ts > time.monotonic() - self.window_s]
            return len(events) < self.max_failures

    def record(self, ip: str) -> None:
        with self._lock:
            events = [ts for ts in self._events.get(ip, []) if ts > time.monotonic() - self.window_s]
            events.append(time.monotonic())
            self._events[ip] = events

    def seconds_blocked(self, ip: str) -> int:
        with self._lock:
            events = [ts for ts in self._events.get(ip, []) if ts > time.monotonic() - self.window_s]
            if len(events) < self.max_failures:
                return 0
            oldest = min(events)
            return max(1, int(self.window_s - (time.monotonic() - oldest)))


def allowlist_allows(allowlist: tuple[str, ...], ip: str) -> bool:
    if not allowlist:
        return True
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in allowlist:
        try:
            if "/" in item:
                if address in ipaddress.ip_network(item, strict=False):
                    return True
            elif address == ipaddress.ip_address(item):
                return True
        except ValueError:
            continue
    return False


class DashboardServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], context: AppContext) -> None:
        self.context = context
        self.limiter = FailureLimiter()
        super().__init__(address, DashboardHandler)


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer
    protocol_version = "HTTP/1.1"
    server_version = f"SolarBridge/{__version__}"
    sys_version = ""

    # ------------------------------------------------------------------ routing

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if not self._guard_dashboard(path):
                return
            if path.startswith("/api/seed/"):
                self._handle_seed_get(path, query)
            elif path in {"/", "/index.html"}:
                self._serve_static("index.html")
            elif path == "/api/current":
                self._json_response(self._current_payload())
            elif path == "/api/health":
                self._json_response(self._health_payload())
            elif path == "/healthz":
                self._json_response(self._health_payload())
            elif path == "/api/auth/status":
                self._auth_status()
            elif path == "/api/history":
                self._history(query)
            elif path == "/api/export.csv":
                self._export_csv(query)
            elif path == "/api/events":
                self._events()
            elif path == "/api/master":
                self._master_status()
            elif path == "/api/tariffs":
                self._tariffs_get()
            elif path == "/api/finance":
                self._finance(query)
            elif path == "/report":
                self._serve_static("report.html")
            elif path.startswith("/assets/"):
                self._serve_static(path.removeprefix("/assets/"))
            else:
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except BrokenPipeError:
            pass
        except Exception:
            LOGGER.exception("request failed: %s", self.path)
            if not self.wfile.closed:
                self._json_response({"error": "internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/index.html"}:
            self._serve_static("index.html", head_only=True)
        elif path.startswith("/assets/"):
            self._serve_static(path.removeprefix("/assets/"), head_only=True)
        else:
            self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND, head_only=True)

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/auth/login":
                self._auth_login()
                return
            if not self._guard_dashboard(path):
                return
            if path == "/api/tariffs":
                body = self._read_body()
                self._tariffs_post(body)
                return
            if not path.startswith("/api/ingest/"):
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            ip = self.client_ip()
            limiter = self.server.limiter
            if not limiter.check(ip):
                self._json_response(
                    {"error": "too many failed attempts"},
                    HTTPStatus.TOO_MANY_REQUESTS,
                )
                return
            allowed, status, reason = self._authorize_ingest()
            if not allowed:
                limiter.record(ip)
                self._json_response({"error": reason}, status)
                return
            body = self._read_body()
            if path == "/api/ingest/hello":
                self._ingest_hello(body)
            elif path == "/api/ingest/frames":
                self._ingest_frames(body)
            elif path == "/api/ingest/heartbeat":
                self._ingest_heartbeat(body)
            else:
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception:
            LOGGER.exception("ingest request failed: %s", self.path)
            if not self.wfile.closed:
                self._json_response({"error": "internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_DELETE(self) -> None:
        path = unquote(urlparse(self.path).path)
        try:
            if not self._guard_dashboard(path):
                return
            if not path.startswith("/api/tariffs/"):
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            if not self._same_origin():
                self._json_response({"error": "cross-origin request rejected"}, HTTPStatus.FORBIDDEN)
                return
            raw = path.removeprefix("/api/tariffs/")
            if not raw.isdigit():
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            deleted = self.server.context.storage.tariff_delete(int(raw))
            if not deleted:
                self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json_response({"deleted": True, "tariffs": self.server.context.storage.tariffs_list()})
        except Exception:
            LOGGER.exception("tariff delete failed: %s", self.path)
            if not self.wfile.closed:
                self._json_response({"error": "internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------- dashboard auth

    def _auth_token(self) -> str | None:
        """Dashboard token from X-Auth-Token header, sb_auth cookie or ?token=
        (the last one exists for EventSource, which cannot set headers)."""
        header = (self.headers.get("X-Auth-Token") or "").strip()
        if header:
            return header
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == AUTH_COOKIE:
                return value.strip() or None
        query = parse_qs(urlparse(self.path).query)
        values = query.get("token")
        return values[0] if values else None

    def _authenticated(self) -> bool:
        store = self.server.context.auth_store
        if store is None:
            return True
        return store.validate_token(self._auth_token()) is not None

    def _guard_dashboard(self, path: str) -> bool:
        """True when the request may proceed; otherwise 401 has been sent.

        SB_AUTH=0 -> always True. With auth on, the HTML shells and assets
        stay reachable (the login UI lives there), while every data endpoint
        requires the token issued by /api/auth/login. Ingest and seed
        endpoints keep their own separate Bearer authentication."""
        store = self.server.context.auth_store
        if store is None or path in AUTH_OPEN_PATHS or path.startswith(AUTH_OPEN_PREFIXES):
            return True
        if path in {"/", "/index.html", "/report"} or path.startswith("/assets/"):
            return True
        if self._authenticated():
            return True
        self._json_response(
            {"error": "unauthorized", "auth_required": True}, HTTPStatus.UNAUTHORIZED
        )
        return False

    def _auth_status(self) -> None:
        store = self.server.context.auth_store
        if store is None:
            self._json_response({"auth_required": False, "authenticated": True})
            return
        self._json_response({"auth_required": True, "authenticated": self._authenticated()})

    def _auth_login(self) -> None:
        store = self.server.context.auth_store
        if store is None:
            self._json_response({"auth_required": False, "authenticated": True})
            return
        ip = self.client_ip()
        if not self.server.limiter.check(ip):
            self._json_response(
                {"error": "too many failed attempts"}, HTTPStatus.TOO_MANY_REQUESTS
            )
            return
        body = self._read_body()
        login = str(body.get("login") or "")
        password = str(body.get("password") or "")
        if not login or not password or not store.verify(login, password):
            self.server.limiter.record(ip)
            self._json_response(
                {"error": "invalid login or password", "auth_required": True},
                HTTPStatus.UNAUTHORIZED,
            )
            return
        token = store.issue_token(login)
        payload = json.dumps({"ok": True, "token": token, "login": login}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Set-Cookie",
            f"{AUTH_COOKIE}={token}; Path=/; Max-Age={AUTH_COOKIE_MAX_AGE}; SameSite=Strict",
        )
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ------------------------------------------------------- dashboard settings

    def _same_origin(self) -> bool:
        """Light CSRF guard for browser-driven POST/DELETE: Origin/Referer (when
        present) must match Host. Requests without them (curl, health checks)
        are allowed — the dashboard itself is a LAN/local service."""
        host = (self.headers.get("Host") or "").strip().lower()
        header = (self.headers.get("Origin") or self.headers.get("Referer") or "").strip()
        if not header:
            return True
        try:
            source_host = urlparse(header).netloc.lower()
        except ValueError:
            return False
        return bool(host) and source_host == host

    def _tariffs_get(self) -> None:
        self._json_response({"tariffs": self.server.context.storage.tariffs_list()})

    def _tariffs_post(self, body: dict[str, Any]) -> None:
        if not self._same_origin():
            self._json_response({"error": "cross-origin request rejected"}, HTTPStatus.FORBIDDEN)
            return
        price = body.get("price_per_kwh")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError("price_per_kwh must be a number")
        tariff = self.server.context.storage.tariff_set(
            str(body.get("valid_from") or ""),
            float(price),
            str(body.get("note") or "")[:200],
        )
        self._json_response({
            "tariff": tariff,
            "tariffs": self.server.context.storage.tariffs_list(),
        })

    def _finance(self, query: dict[str, list[str]]) -> None:
        days = int(query.get("days", ["2"])[0])
        tz = int(query.get("tz", ["0"])[0])
        anchor = int(time.time())
        to_raw = (query.get("to") or [""])[0]
        if to_raw:
            # Report custom range: "to" is a local YYYY-MM-DD; anchor the
            # finance window at the end of that local day (tz uses the JS
            # getTimezoneOffset() convention, UTC+3 arrives as -180).
            to_date = date.fromisoformat(to_raw)
            epoch_of_date = to_date.toordinal() * 86400 + 62135596800
            anchor = epoch_of_date + 86400 - 1 - tz * 60
        self._json_response(
            self.server.context.storage.finance(days=days, tz_offset_minutes=tz, now_ts=anchor)
        )

    # ------------------------------------------------------------------ auth

    def client_ip(self) -> str:
        if self.server.context.settings.trust_proxy:
            forwarded = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            if forwarded:
                return forwarded
        try:
            return self.connection.getpeername()[0]
        except OSError:
            return "unknown"

    def _authorize_ingest(self) -> tuple[bool, HTTPStatus, str]:
        settings = self.server.context.settings
        ip = self.client_ip()
        if not allowlist_allows(settings.ingest_allowlist, ip):
            return False, HTTPStatus.FORBIDDEN, "source address not allowed"
        if not settings.ingest_token:
            return False, HTTPStatus.SERVICE_UNAVAILABLE, "ingest token is not configured"
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer ") or auth[7:].strip() != settings.ingest_token:
            return False, HTTPStatus.UNAUTHORIZED, "invalid or missing bearer token"
        return True, HTTPStatus.OK, ""

    def _check_schema(self, master_schema: Any) -> HTTPStatus | None:
        try:
            schema = int(master_schema)
        except (TypeError, ValueError):
            return HTTPStatus.BAD_REQUEST
        if schema > SCHEMA_VERSION:
            return HTTPStatus.CONFLICT
        if schema < MIN_SUPPORTED_SCHEMA:
            return HTTPStatus.CONFLICT
        return None

    # ------------------------------------------------------------------ ingest

    def _ingest_hello(self, body: dict[str, Any]) -> None:
        status = self._check_schema(body.get("schema_version"))
        if status is HTTPStatus.CONFLICT:
            self._json_response(
                {
                    "error": "schema_too_new" if int(body.get("schema_version") or 0) > SCHEMA_VERSION
                    else "schema_too_old",
                    "receiver_schema": SCHEMA_VERSION,
                    "min_supported": MIN_SUPPORTED_SCHEMA,
                },
                HTTPStatus.CONFLICT,
            )
            return
        master_id = str(body.get("master_id") or "")
        self._json_response(
            {
                "ok": True,
                "schema_version": SCHEMA_VERSION,
                "min_supported": MIN_SUPPORTED_SCHEMA,
                "app_version": __version__,
                "last_sample_ts": self.server.context.storage.last_sample_ts(master_id),
                "receiver_time": int(time.time()),
            }
        )

    def _ingest_frames(self, body: dict[str, Any]) -> None:
        status = self._check_schema(body.get("schema_version"))
        if status is HTTPStatus.CONFLICT:
            self._json_response(
                {"error": "schema_mismatch", "receiver_schema": SCHEMA_VERSION},
                HTTPStatus.CONFLICT,
            )
            return
        storage = self.server.context.storage
        master_id = str(body.get("master_id") or "")
        frames = body.get("frames") or []
        accepted = 0
        for frame in frames:
            try:
                captured_at = str(frame["captured_at"])
                captured_ts = int(frame["captured_ts"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("frame requires captured_at and captured_ts") from None
            snapshot = frame.get("inverter")
            if not isinstance(snapshot, dict):
                raise ValueError("frame requires an inverter snapshot object")
            extra = {
                key: value for key, value in frame.items()
                if key not in FRAME_KEYS and isinstance(value, (dict, list))
            }
            if extra:
                snapshot = dict(snapshot)
                snapshot["_extra_sections"] = extra
            if storage.insert_sample(snapshot, master_id=master_id):
                accepted += 1
            battery = frame.get("battery")
            if isinstance(battery, dict):
                storage.insert_battery_frame(
                    captured_at, captured_ts, battery.get("modules") or [], master_id=master_id
                )
        master_state = self.server.context.master_state
        if master_state is not None and frames:
            newest = max(int(frame.get("captured_ts") or 0) for frame in frames)
            newest_at = [
                str(frame.get("captured_at")) for frame in frames
                if int(frame.get("captured_ts") or 0) == newest
            ]
            for event in master_state.on_frames(master_id, newest, newest_at[0] if newest_at else ""):
                storage.add_master_event(event["event"], event["detail"])
        self._json_response(
            {
                "ok": True,
                "accepted": accepted,
                "duplicates": len(frames) - accepted,
                "last_sample_ts": storage.last_sample_ts(master_id),
            }
        )

    def _ingest_heartbeat(self, body: dict[str, Any]) -> None:
        master_state = self.server.context.master_state
        if master_state is None:
            self._json_response({"error": "not an ingest receiver"}, HTTPStatus.NOT_FOUND)
            return
        status = self._check_schema(body.get("schema_version"))
        if status is HTTPStatus.CONFLICT:
            storage = self.server.context.storage
            storage.add_master_event("schema_mismatch", f"master schema {body.get('schema_version')}")
            self._json_response(
                {"error": "schema_mismatch", "receiver_schema": SCHEMA_VERSION},
                HTTPStatus.CONFLICT,
            )
            return
        for event in master_state.on_heartbeat(body):
            self.server.context.storage.add_master_event(event["event"], event["detail"])
        self._json_response({"ok": True})

    # ------------------------------------------------------------------ seed

    def _handle_seed_get(self, path: str, query: dict[str, list[str]]) -> None:
        settings = self.server.context.settings
        ip = self.client_ip()
        limiter = self.server.limiter
        if not limiter.check(ip):
            self._json_response({"error": "too many failed attempts"}, HTTPStatus.TOO_MANY_REQUESTS)
            return
        if not allowlist_allows(settings.ingest_allowlist, ip):
            limiter.record(ip)
            self._json_response({"error": "source address not allowed"}, HTTPStatus.FORBIDDEN)
            return
        token = (query.get("t") or [""])[0].strip()
        parts = path.strip("/").split("/")
        # /api/seed/passport/<id>  /api/seed/download/<id>
        if len(parts) != 4 or parts[1] != "seed" or parts[2] not in {"passport", "download"}:
            self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        seed_id = parts[3]
        row = self.server.context.storage.consume_seed_token(token)
        if row is None or row.get("seed_id") != seed_id:
            limiter.record(ip)
            self._json_response(
                {"error": "invalid, expired, exhausted, or revoked seed token"},
                HTTPStatus.FORBIDDEN,
            )
            return
        file_path = settings.seed_dir / seed_id / (
            "passport.json" if parts[2] == "passport" else "seed.sqlite.gz"
        )
        if not file_path.is_file():
            self._json_response({"error": "seed file not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = "application/json" if parts[2] == "passport" else "application/gzip"
        disposition = None if parts[2] == "passport" else f'attachment; filename="{seed_id}.sqlite.gz"'
        self._send_file_range(file_path, content_type, disposition)

    # ------------------------------------------------------------------ payloads

    def _current_payload(self) -> dict[str, Any]:
        context = self.server.context
        battery = context.storage.latest_battery_frame()
        if context.poller is not None:
            health = context.poller.health()
            if context.battery_health is not None:
                health["battery"] = context.battery_health()
            payload = {"data": context.poller.latest(), "health": health}
            if context.host_provider is not None:
                host = dict(context.host_provider())
                host["master_id"] = context.settings.master_id
                host["service_uptime_s"] = max(0.0, round(time.time() - context.started_at, 1))
                payload["host"] = host
        else:
            state = context.master_state
            if state is not None:
                payload = {"data": context.storage.latest_payload(), "health": state.health()}
                host = state.snapshot().get("host")
                if host:
                    payload["host"] = host
            else:
                payload = {"data": None, "health": {"version": __version__, "status": "offline"}}
        if battery is not None:
            payload["battery"] = battery
        return payload

    def _health_payload(self) -> dict[str, Any]:
        return self._current_payload()["health"]

    def _master_status(self) -> None:
        state = self.server.context.master_state
        if state is None:
            self._json_response({"error": "not an ingest receiver"}, HTTPStatus.NOT_FOUND)
            return
        payload = state.snapshot()
        payload["events"] = self.server.context.storage.recent_master_events(20)
        self._json_response(payload)

    # ------------------------------------------------------------------ history/csv (carried)

    def _history(self, query: dict[str, list[str]]) -> None:
        end_ts = _query_timestamp(query, "to") or int(time.time())
        range_value = query.get("range", ["24h"])[0]
        start_value = _query_timestamp(query, "from")
        if start_value is None:
            start_value = _range_start(range_value, end_ts, self.server.context.storage)
        if start_value > end_ts:
            raise ValueError("from must be before to")
        period = query.get("period", ["auto"])[0]
        if period == "auto":
            period = _auto_period(end_ts - start_value)
        result = self.server.context.storage.history(start_value, end_ts, period)
        self._json_response(result)

    def _export_csv(self, query: dict[str, list[str]]) -> None:
        end_ts = _query_timestamp(query, "to") or int(time.time())
        range_value = query.get("range", ["24h"])[0]
        start_ts = _query_timestamp(query, "from")
        if start_ts is None:
            start_ts = _range_start(range_value, end_ts, self.server.context.storage)
        period = query.get("period", ["auto"])[0]
        if period == "auto":
            period = _auto_period(end_ts - start_ts)
        result = self.server.context.storage.history(start_ts, end_ts, period)

        output = io.StringIO()
        points = result["points"]
        columns = list(points[0].keys()) if points else ["captured_at"]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(points)
        payload = output.getvalue().encode("utf-8")
        self._send_bytes(
            payload,
            content_type="text/csv; charset=utf-8",
            disposition=f'attachment; filename="solarbridge-{period}.csv"',
        )

    def _events(self) -> None:
        context = self.server.context
        if context.poller is None and context.master_state is not None:
            self._events_receiver()
            return
        subscriber = context.poller.events.subscribe()
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 5000\n\n")
            self.wfile.flush()
            latest = context.poller.latest()
            if latest:
                self._send_event(
                    "snapshot",
                    self._events_payload(
                        {"type": "snapshot", "data": latest, "health": context.poller.health()},
                        context,
                    ),
                )
            while True:
                try:
                    event = subscriber.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                self._send_event(event["type"], self._events_payload(event, context))
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            context.poller.events.unsubscribe(subscriber)

    @staticmethod
    def _events_payload(event: dict[str, Any], context: Any) -> dict[str, Any]:
        """SSE event body; "snapshot" events also carry the latest battery frame."""
        data = {key: value for key, value in event.items() if key != "type"}
        if event.get("type") == "snapshot":
            battery = context.storage.latest_battery_frame()
            if battery is not None and data.get("data") is not None:
                data["battery"] = battery
            if context.host_provider is not None:
                host = dict(context.host_provider())
                host["master_id"] = context.settings.master_id
                host["service_uptime_s"] = max(0.0, round(time.time() - context.started_at, 1))
                data["host"] = host
        return data

    def _send_event(self, event_name: str, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        self.wfile.write(f"event: {event_name}\ndata: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _events_receiver(self) -> None:
        """Receiver-side SSE: replay the latest stored frame + master health."""
        context = self.server.context
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 5000\n\n")
            self.wfile.flush()
            while True:
                payload = {"data": context.storage.latest_payload(), "health": context.master_state.health()}
                battery = context.storage.latest_battery_frame()
                if battery is not None:
                    payload["battery"] = battery
                host = context.master_state.snapshot().get("host")
                if host:
                    payload["host"] = host
                self._send_event("snapshot", payload)
                time.sleep(5)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass

    # ------------------------------------------------------------------ serving

    def _serve_static(self, relative: str, head_only: bool = False) -> None:
        public_dir = self.server.context.settings.public_dir.resolve()
        requested = (public_dir / relative).resolve()
        try:
            requested.relative_to(public_dir)
        except ValueError:
            self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND, head_only=head_only)
            return
        if not requested.is_file():
            self._json_response({"error": "not found"}, HTTPStatus.NOT_FOUND, head_only=head_only)
            return
        payload = requested.read_bytes()
        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self._send_bytes(payload, content_type=content_type, head_only=head_only)

    def _send_file_range(self, path: Path, content_type: str, disposition: str | None = None) -> None:
        size = path.stat().st_size
        range_header = self.headers.get("Range") or ""
        start, end = 0, size - 1
        partial = False
        if range_header.startswith("bytes="):
            try:
                first, last = range_header[6:].split("-", 1)
                if first:
                    start = max(0, int(first))
                    end = int(last) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
                end = min(end, size - 1)
                partial = start > 0 or end < size - 1
            except ValueError:
                start, end, partial = 0, size - 1, False
        if start > end or start >= size:
            self.send_response(HTTPStatus.RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _json_response(self, payload: object, status: HTTPStatus = HTTPStatus.OK, head_only: bool = False) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _send_bytes(
        self,
        data: bytes,
        *,
        content_type: str,
        disposition: str | None = None,
        head_only: bool = False,
    ) -> None:
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("request body is required")
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        body = self.rfile.read(length)
        if (self.headers.get("Content-Encoding") or "").lower() == "gzip":
            body = gzip.decompress(body)
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("JSON object expected")
        return parsed

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        if self._coop_applicable():
            # Browsers honour Cross-Origin-Opener-Policy only in trustworthy
            # origins (HTTPS or localhost). Over plain HTTP from a LAN address
            # the header is silently ignored and Chrome logs a console warning,
            # so it is sent only where it can actually be applied.
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _coop_applicable(self) -> bool:
        """True when the browser will actually honour Cross-Origin-Opener-Policy."""
        if isinstance(self.connection, (ssl.SSLSocket, ssl.SSLObject)):
            return True
        forwarded = (
            self.headers.get("X-Forwarded-Proto")
            or self.headers.get("X-Forwarded-Scheme")
            or ""
        ).strip().lower()
        if forwarded == "https":
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        if "]" in host:  # bracketed IPv6 literal, e.g. [::1]:8080
            hostname = host.split("]", 1)[0] + "]"
        else:
            hostname = host.rsplit(":", 1)[0]
        return hostname in {"localhost", "127.0.0.1", "::1", "[::1]"}

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def _query_timestamp(query: dict[str, list[str]], key: str) -> int | None:
    value = query.get(key, [None])[0]
    if value is None:
        return None
    try:
        if value.isdigit():
            return int(float(value))
        from datetime import datetime, timezone

        if len(value) == 10:
            return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"invalid {key} timestamp") from None


def _range_start(range_value: str, end_ts: int, storage: Storage) -> int:
    if range_value == "all":
        oldest = storage.stats()["oldest_at"]
        if oldest:
            from datetime import datetime

            return int(datetime.fromisoformat(oldest.replace("Z", "+00:00")).timestamp())
        return end_ts - 86400
    ranges = {
        "1h": 3600,
        "6h": 6 * 3600,
        "24h": 24 * 3600,
        "7d": 7 * 86400,
        "30d": 30 * 86400,
        "90d": 90 * 86400,
        "1y": 365 * 86400,
    }
    if range_value not in ranges:
        raise ValueError("range must be 1h, 6h, 24h, 7d, 30d, 90d, 1y, or all")
    return end_ts - ranges[range_value]


def _auto_period(seconds: int) -> str:
    if seconds <= 6 * 3600:
        return "minute"
    if seconds <= 3 * 86400:
        return "30m"
    if seconds <= 45 * 86400:
        return "day"
    if seconds <= 180 * 86400:
        return "week"
    return "month"
