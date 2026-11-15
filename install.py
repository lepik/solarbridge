#!/usr/bin/env python3
"""SolarBridge installer and control menu.

Run with:  sudo python3 install.py
No arguments, no flags. Everything happens through numbered menus where
Enter always accepts the safe default. Works fully offline.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent
INSTALL_DIR = Path("/opt/solarbridge")
# Once installed, the /opt copy is authoritative: Settings and .env live there.
if INSTALL_DIR != BASE_DIR and (INSTALL_DIR / "solarbridge" / "__init__.py").exists():
    sys.path.insert(0, str(INSTALL_DIR))
    BASE_DIR = INSTALL_DIR
else:
    sys.path.insert(0, str(BASE_DIR))
SERVICE = "solarbridge.service"
SERVICE_USER = "sbridge"
DATA_DIR_NAME = "data"


from solarbridge import __version__  # noqa: E402
from solarbridge import seed as sb_seed  # noqa: E402
from solarbridge.config import Settings, default_master_id, random_master_suffix  # noqa: E402
from solarbridge.forwarder import parse_receivers  # noqa: E402
from solarbridge.storage import Storage  # noqa: E402


# --------------------------------------------------------------------- helpers


def require_root() -> None:
    if os.geteuid() == 0:
        return
    print("\nУстановщику нужны права root. Запустите:")
    print(f"  sudo python3 {Path(sys.argv[0]).name}\n")
    sys.exit(1)


def run(cmd: list[str], check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def systemctl(action: str, quiet: bool = False) -> subprocess.CompletedProcess | None:
    if not Path(f"/etc/systemd/system/{SERVICE}").exists():
        return None
    return run(["systemctl", action, SERVICE], check=False, quiet=quiet)


def service_active() -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def service_installed() -> bool:
    return Path(f"/etc/systemd/system/{SERVICE}").exists()


def ask(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{text}{suffix}: ").strip()
    return answer or default


def ask_int(text: str, default: int, minimum: int = 1, maximum: int = 10**9) -> int:
    while True:
        raw = ask(text, str(default))
        try:
            value = int(raw)
            if minimum <= value <= maximum:
                return value
        except ValueError:
            pass
        print(f"  Введите число от {minimum} до {maximum}.")


def confirm(text: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{text} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "д", "да"}


def choose(title: str, options: list[str]) -> int | None:
    print(f"\n{title}")
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")
    raw = input("Номер (Enter = выход): ").strip()
    if not raw:
        return None
    try:
        index = int(raw)
        if 1 <= index <= len(options):
            return index
    except ValueError:
        pass
    print("  Неверный номер, попробуйте ещё раз.")
    return choose(title, options)


def hr() -> None:
    print("-" * 70)


def header(text: str) -> None:
    print()
    hr()
    print(text)
    hr()


def gen_token() -> str:
    import secrets

    return secrets.token_hex(32)


def project_dir() -> Path:
    return BASE_DIR


def load_settings() -> Settings:
    return Settings.from_env()


def open_storage(settings: Settings) -> Storage:
    return Storage(settings.db_path, master_id=settings.master_id)


def fmt_ts(value: Any) -> str:
    if not value:
        return "нет"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(value)))
    except (TypeError, ValueError):
        return str(value)


def fmt_age(value: Any, now: int | None = None) -> str:
    if not value:
        return "нет"
    try:
        seconds = int((now or time.time()) - int(value))
    except (TypeError, ValueError):
        return str(value)
    if seconds < 90:
        return f"{seconds} с"
    if seconds < 7200:
        return f"{seconds // 60} мин"
    if seconds < 172800:
        return f"{seconds // 3600} ч"
    return f"{seconds // 86400} дн"


# --------------------------------------------------------------------- .env


ENV_HEADER = """\
# SolarBridge {version} — сгенерировано install.py
# Роль: {role}
"""


def write_env(path: Path, values: dict[str, Any], role: str) -> None:
    """Write .env with comments. Never append: the file is fully regenerated."""
    lines: list[str] = [ENV_HEADER.format(version=__version__, role=role), ""]
    lines += [
        "# --- Роль -------------------------------------------------------",
        "# serial  = мастер: опрашивает инвертор по RS485 и рассылает кадры",
        "# ingest  = приёмник: принимает кадры от мастера и зеркалит их",
        f"SB_SOURCE_MODE={values['source_mode']}",
        "",
        "# Идентификатор мастера (hostname-XXXXXXXX, суффикс генерируется при установке;"
        " не меняйте задним числом)",
        f"SB_MASTER_ID={values['master_id']}",
        "",
        "# --- Дашборд ----------------------------------------------------",
        "# Адрес и порт веб-интерфейса; 127.0.0.1 = только локально, за nginx",
        f"SB_DASH_HOST={values['dash_host']}",
        f"SB_DASH_PORT={values['dash_port']}",
        "",
        "# --- Хранение ---------------------------------------------------",
        f"SB_DB_PATH={values['db_path']}",
        "# Глубина истории в днях. 730 дней при 60-сек кадре ~ 7,6 ГБ на диске",
        f"SB_RETENTION_DAYS={values['retention_days']}",
    ]
    if values["source_mode"] == "serial":
        lines += [
            "",
            "# --- Инвертор (только для мастера) ------------------------------",
            "# Стабильный by-id путь переживает смену ttyUSB-номеров",
            f"SB_SERIAL_PORT={values['serial_port']}",
            f"SB_SLAVE_ID={values['slave_id']}",
            f"SB_BAUDRATE={values['baudrate']}",
            "# Опрос шины 15 с, запись кадра в БД 60 с, конфиги 300 с",
            f"SB_POLL_INTERVAL={values['poll_interval']}",
            f"SB_SAMPLE_INTERVAL={values['sample_interval']}",
            f"SB_CONFIG_INTERVAL={values['config_interval']}",
        ]
        lines += [
            "",
            "# --- Пересылка (только для мастера) -----------------------------",
            "# Список приёмников — файл receivers.list рядом с .env",
            "# Окно догрузки в днях; 0 = только live; >окна приёмник нуждается в пересеве",
            f"SB_FORWARD_BACKFILL_DAYS={values['forward_backfill_days']}",
            "# Батч догрузки (сэмплов), пауза между батчами (с), параллельных догрузок",
            f"SB_FORWARD_BATCH={values['forward_batch']}",
            f"SB_FORWARD_PAUSE_S={values['forward_pause_s']}",
            f"SB_FORWARD_PARALLEL={values['forward_parallel']}",
            "# Heartbeat каждые 15 с; кадры старше 180 с = ошибка шины на приёмнике",
            f"SB_HEARTBEAT_INTERVAL={values['heartbeat_interval']}",
            f"SB_OFFLINE_AFTER_S={values['offline_after_s']}",
        ]
        if values.get("battery_mode") == "serial":
            lines += [
                "",
                "# --- Батареи (экспериментально, по умолчанию выключено) ---------",
                "# DIP-адреса модулей на шине через запятую; автоскан не выполняется",
                f"SB_BATTERY_MODE={values['battery_mode']}",
                f"SB_BATTERY_SERIAL_PORT={values['battery_serial_port']}",
                f"SB_BATTERY_BAUDRATE={values['battery_baudrate']}",
                f"SB_BATTERY_PROTOCOL={values['battery_protocol']}",
                f"SB_BATTERY_VARIANT={values['battery_variant']}",
                f"SB_BATTERY_ADDRESSES={values['battery_addresses']}",
            ]
    else:
        lines += [
            "",
            "# --- Приём (только для приёмника) -------------------------------",
            "# Токен этого приёмника — совпадает с токеном в receivers.list мастера",
            f"SB_INGEST_TOKEN={values['ingest_token']}",
            "# IP-allowlist для приёма (CIDR через запятую; пусто = выключено)",
            f"SB_INGEST_ALLOWLIST={values['ingest_allowlist']}",
            "# 1 = доверять X-Forwarded-For (приёмник за nginx)",
            f"SB_TRUST_PROXY={values['trust_proxy']}",
        ]
    lines += ["", "# Свежесть пересева: 0 = равно окну догрузки",
              f"SB_SEED_MAX_AGE_DAYS={values['seed_max_age_days']}"]
    lines += [
        "",
        "# --- Дашборд: вход и дисковый сторож ----------------------------",
        f"# 1 = дашборд требует вход по логину/паролю (файл {values.get('user_list_name', 'user_list')} рядом с .env)",
        f"SB_AUTH={values.get('auth_enabled', '0')}",
        "# Минимальный свободный процент диска с БД. Ниже порога мастер",
        "# прекращает писать в свою БД и шлёт кадры только приёмникам.",
        f"SB_DISK_MIN_FREE_PERCENT={values.get('disk_min_free_percent', 10)}",
    ]
    if values.get("update_url"):
        lines += ["# Источник релизов для update.py (репозиторий GitHub или прямой URL zip)",
                  f"SB_UPDATE_URL={values['update_url']}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def receiver_env_block(token: str, name: str, dash_port: int, retention: int = 730) -> str:
    return "\n".join([
        f"# SolarBridge .env для приёмника '{name}' — готовый блок",
        "SB_SOURCE_MODE=ingest",
        f"SB_INGEST_TOKEN={token}",
        "# 0.0.0.0 если приёмник доступен напрямую; 127.0.0.1 если за nginx",
        "SB_DASH_HOST=0.0.0.0",
        f"SB_DASH_PORT={dash_port}",
        f"SB_RETENTION_DAYS={retention}",
        "",
    ])


# --------------------------------------------------------------------- wizard


def scan_serial_devices() -> list[str]:
    """Candidate ports: stable symlinks from /dev/serial, by-id first, then
    by-path. Identical cheap adapters without a USB serial number have no
    usable by-id entry - there by-path (physical USB socket) is what works."""
    import glob

    entries: list[str] = []
    seen_targets: set[str] = set()
    patterns = ("/dev/serial/by-id/*", "/dev/serial/by-path/*")
    for path in sorted(sum((glob.glob(pattern) for pattern in patterns), [])):
        try:
            target = os.path.realpath(path)
        except OSError:
            target = path
        if target in seen_targets:  # same adapter: keep the by-id name only
            continue
        seen_targets.add(target)
        entries.append(path)
    return entries


def wizard_master(values: dict[str, Any]) -> dict[str, Any]:
    header("Настройка МАСТЕРА (RS485 у инвертора)")
    devices = scan_serial_devices()
    print("\nНайденные serial-адаптеры:")
    if devices:
        for index, device in enumerate(devices, start=1):
            print(f"  {index}. {device}")
    else:
        print("  (не найдено; введите путь вручную)")
    options = [str(device) for device in devices] + ["Ввести путь вручную"]
    choice = choose("Выберите адаптер", options)
    if choice == len(options):
        values["serial_port"] = ask("Путь к порту", "/dev/ttyUSB0")
    elif choice:
        values["serial_port"] = str(devices[choice - 1])
    else:
        values["serial_port"] = ask("Путь к порту", "/dev/ttyUSB0")
    values["slave_id"] = ask_int("Modbus slave id инвертора", 4, 1, 247)
    values["baudrate"] = ask_int("Скорость порта", 19200, 1200, 115200)
    values["dash_port"] = ask_int("Порт дашборда", 8090, 1, 65535)
    values["retention_days"] = ask_int("Глубина истории (дней)", 730, 1, 36500)
    values["forward_backfill_days"] = ask_int("Окно догрузки для приёмников (дней)", 60, 0, 365)
    if confirm("Подключить мониторинг батарей? (экспериментально)", default=False):
        values["battery_mode"] = "serial"
        values["battery_serial_port"] = ask("Порт батареи (by-id/by-path)", "")
        print("  DIP-адреса модулей на шине; автоскан не выполняется, задайте явно.")
        while True:
            raw = ask("Адреса модулей (через запятую, например 2,3)", "2,3")
            items = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
            try:
                parsed = [int(item, 0) for item in items]
            except ValueError:
                print("  Ожидаются числа через запятую, например 2,3.")
                continue
            parsed = sorted({addr for addr in parsed if 1 <= addr <= 15})
            if parsed:
                values["battery_addresses"] = ",".join(str(addr) for addr in parsed)
                break
            print("  Нужен хотя бы один корректный адрес (1..15).")
    else:
        values["battery_mode"] = "off"
        values["battery_serial_port"] = ""
        values["battery_addresses"] = ""
    values["disk_min_free_percent"] = ask_int(
        "Минимальный свободный процент диска (0 = не проверять)", 10, 0, 90
    )
    if confirm("Включить вход по логину/паролю на дашборде?", default=False):
        while True:
            login = ask("Логин", "admin")
            password = ask("Пароль", "")
            if login and password:
                break
            print("  Нужны и логин, и пароль.")
        values["auth_enabled"] = "1"
        values["auth_login"] = login
        values["auth_password"] = password
    else:
        values["auth_enabled"] = "0"
    return values


def wizard_receiver(values: dict[str, Any]) -> dict[str, Any]:
    header("Настройка ПРИЁМНИКА (зеркало на VPS)")
    print("\nВставьте токен этого приёмника (напечатан на мастере при добавлении).")
    while True:
        token = ask("Токен")
        if len(token) >= 16:
            break
        print("  Токен выглядит слишком коротким (ожидается 64 hex-символа).")
    values["ingest_token"] = token
    values["dash_port"] = ask_int("Порт дашборда", 8090, 1, 65535)
    values["retention_days"] = ask_int("Глубина истории приёмника (дней)", 730, 1, 36500)
    values["ingest_allowlist"] = ask("IP-allowlist (CIDR через запятую, Enter = выкл)", "")
    values["trust_proxy"] = "1" if confirm("Приёмник за nginx (доверять X-Forwarded-For)?", default=False) else "0"
    return values


def build_env_values(values: dict[str, Any], role: str) -> dict[str, Any]:
    if values.get("master_id"):
        master_id = values["master_id"]
    else:
        # Fresh install: hostname plus a random suffix persisted in .env, so
        # frame deduplication keeps a stable, collision-free identifier
        # (example: raspberrypi-B349HCFD).
        hostname = socket.gethostname().strip() or "solarbridge"
        master_id = f"{hostname}-{random_master_suffix()}"
        values["master_id"] = master_id
    full = {
        "source_mode": role,
        "master_id": master_id,
        "dash_host": values.get("dash_host", "127.0.0.1" if role == "serial" else "0.0.0.0"),
        "dash_port": values.get("dash_port", 8090),
        "db_path": str(INSTALL_DIR / DATA_DIR_NAME / "solarbridge.sqlite3"),
        "retention_days": values.get("retention_days", 730),
        "serial_port": values.get("serial_port", ""),
        "slave_id": values.get("slave_id", 4),
        "baudrate": values.get("baudrate", 19200),
        "poll_interval": 15,
        "sample_interval": 60,
        "config_interval": 300,
        "forward_backfill_days": values.get("forward_backfill_days", 60),
        "forward_batch": 240,
        "forward_pause_s": 1.0,
        "forward_parallel": 2,
        "heartbeat_interval": 15,
        "offline_after_s": 180,
        "seed_max_age_days": 0,
        "ingest_token": values.get("ingest_token", ""),
        "ingest_allowlist": values.get("ingest_allowlist", ""),
        "trust_proxy": values.get("trust_proxy", "0"),
        "battery_mode": values.get("battery_mode", "off"),
        "battery_serial_port": values.get("battery_serial_port", ""),
        "battery_baudrate": values.get("battery_baudrate", 9600),
        "battery_protocol": values.get("battery_protocol", "auto"),
        "battery_variant": values.get("battery_variant", "auto"),
        "battery_addresses": values.get("battery_addresses", ""),
        "auth_enabled": values.get("auth_enabled", "0"),
        "auth_login": values.get("auth_login", ""),
        "auth_password": values.get("auth_password", ""),
        "disk_min_free_percent": values.get("disk_min_free_percent", 10),
        "update_url": values.get("update_url", ""),
        "user_list_name": "user_list",
    }
    return full


def write_user_list(env_values: dict[str, Any], directory: Path) -> None:
    """Create the dashboard user_list file when auth was enabled in the wizard."""
    if str(env_values.get("auth_enabled", "0")) != "1":
        return
    login = str(env_values.get("auth_login") or "").strip()
    password = str(env_values.get("auth_password") or "").strip()
    if not login or not password:
        return
    path = directory / str(env_values.get("user_list_name") or "user_list")
    if path.exists():
        print(f"user_list уже существует, оставлен без изменений: {path}")
        return
    path.write_text(
        "# Логины дашборда: формат 'login:password', по одной паре на строку.\n"
        "# Файл в открытом тексте по требованию владельца; держите права 0640.\n"
        f"{login}:{password}\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o640)
    except OSError:
        pass
    print(f"user_list создан: {path}")


def wizard_role() -> str:
    choice = choose(
        "Роль этой машины?",
        [
            "Мастер — инвертор подключён по RS485, раздаёт кадры приёмникам",
            "Приёмник — принимает кадры от мастера (VPS или вторая машина)",
        ],
    )
    if choice is None:
        print("Установка отменена.")
        sys.exit(0)
    return "serial" if choice == 1 else "ingest"


# --------------------------------------------------------------------- install


UNIT_TEMPLATE = """\
[Unit]
Description=SolarBridge inverter dashboard and forwarder
After=local-fs.target network.target
Wants=local-fs.target

[Service]
Type=simple
# Read-only application: it exposes no inverter write operation.
User={user}
Group={user}
SupplementaryGroups=dialout
WorkingDirectory={install_dir}
Environment=PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ExecStart={install_dir}/.venv/bin/python {install_dir}/main.py
Restart=always
RestartSec=5
UMask=0027

NoNewPrivileges=true
CapabilityBoundingSet=
AmbientCapabilities=
PrivateTmp=true
PrivateDevices=false
DevicePolicy=closed
# Two RS485 adapters (inverter + battery bus) enumerate as ttyUSB0/1 and may
# swap numbering across reconnects. char-ttyUSB whitelists the whole USB-serial
# class, so every /dev/ttyUSB* node stays accessible regardless of numbering.
# If a converter ever enumerates as ttyACM (CDC-ACM driver), add:
#   DeviceAllow=char-ttyACM rw
DeviceAllow=char-ttyUSB rw
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={install_dir}/data
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
ProtectControlGroups=true
ProtectHostname=true
ProtectClock=true
RestrictSUIDSGID=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
SystemCallArchitectures=native
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
"""


def install_system(env_values: dict[str, Any], role: str) -> Path:
    header(f"Установка в {INSTALL_DIR}")
    if not INSTALL_DIR.exists() or not (INSTALL_DIR / "solarbridge").exists():
        print("Копирую файлы проекта...")
        shutil.copytree(
            BASE_DIR,
            INSTALL_DIR,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("data", ".env", "__pycache__", "*.pyc", ".git"),
        )
    else:
        print("Обновляю файлы проекта (data и .env не трогаю)...")
        shutil.copytree(
            BASE_DIR,
            INSTALL_DIR,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("data", ".env", "__pycache__", "*.pyc", ".git"),
        )

    run(["apt-get", "install", "-y", "python3-venv"], check=False, quiet=True)

    if subprocess.run(["id", "-u", SERVICE_USER], capture_output=True).returncode != 0:
        run(["useradd", "--system", "--user-group", "--home-dir", str(INSTALL_DIR),
             "--shell", "/usr/sbin/nologin", SERVICE_USER])
    run(["usermod", "--append", "--groups", "dialout", SERVICE_USER], check=False)

    venv_python = INSTALL_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        run([sys.executable, "-m", "venv", str(INSTALL_DIR / ".venv")])
    run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check",
         "--no-cache-dir", "-r", str(INSTALL_DIR / "requirements.txt")], check=False, quiet=True)

    (INSTALL_DIR / DATA_DIR_NAME).mkdir(parents=True, exist_ok=True)
    (INSTALL_DIR / DATA_DIR_NAME / "seeds").mkdir(parents=True, exist_ok=True)

    env_path = INSTALL_DIR / ".env"
    if confirm("Настроить .env сейчас? (Enter по умолчанию = да, если .env ещё нет)", default=not env_path.exists()):
        if env_path.exists():
            shutil.copy2(env_path, env_path.with_suffix(".env.bak"))
        write_env(env_path, env_values, role)
        print(f".env записан: {env_path}")
    elif not env_path.exists():
        write_env(env_path, env_values, role)
        print(f".env записан: {env_path}")
    write_user_list(env_values, INSTALL_DIR)

    (INSTALL_DIR / "receivers.list").touch(exist_ok=True)

    unit_path = Path("/etc/systemd/system") / SERVICE
    unit_path.write_text(UNIT_TEMPLATE.format(user=SERVICE_USER, install_dir=INSTALL_DIR), encoding="utf-8")
    run(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", str(INSTALL_DIR)])
    run(["chmod", "0640", str(env_path), str(INSTALL_DIR / "receivers.list")], check=False)
    run(["chmod", "0750", str(INSTALL_DIR / DATA_DIR_NAME)], check=False)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", SERVICE], check=False)
    run(["systemctl", "restart", SERVICE])
    if _wait_healthz(env_values["dash_port"]):
        print(f"\nSolarBridge {__version__} установлен и работает: http://127.0.0.1:{env_values['dash_port']}")
    else:
        print("\nСлужба запущена, но healthz ещё не ответил. Логи: journalctl -u solarbridge -n 50")
    return INSTALL_DIR


def _wait_healthz(port: int, timeout_s: int = 30) -> bool:
    url = f"http://127.0.0.1:{port}/healthz"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(1.0)
    return False


# --------------------------------------------------------------------- master menu


def forwarding_status() -> None:
    settings = load_settings()
    receivers, errors = parse_receivers(
        settings.receivers_file.read_text(encoding="utf-8")
    ) if settings.receivers_file.exists() else ([], [])
    storage = open_storage(settings)
    states = storage.all_forward_states()
    header("Статус пересылки")
    if errors:
        for error in errors:
            print(f"  ! receivers.list: {error}")
    if not receivers:
        print("  Приёмников нет. receivers.list пуст (добавьте пунктом 2).")
        return
    now = int(time.time())
    print(f"  {'Имя':<12} {'Вкл':<5} {'Состояние':<16} {'Водяной знак':<14} {'Сбои':<5} {'Отправлено':<10}")
    for receiver in receivers:
        state = states.get(receiver.name, {})
        print(
            f"  {receiver.name:<12} {'да' if receiver.enabled else 'нет':<5} "
            f"{str(state.get('last_result') or '—'):<16} "
            f"{fmt_age(state.get('last_acked_ts'), now):<14} "
            f"{state.get('consecutive_failures') or 0:<5} "
            f"{state.get('sent_total') or 0}/{state.get('acked_total') or 0}"
        )
        if state.get("last_error"):
            print(f"      ошибка: {state['last_error']}")


def add_receiver() -> None:
    settings = load_settings()
    header("Добавить приёмник")
    name = ask("Имя приёмника (например vps1)")
    if not name:
        print("Отменено: имя обязательно.")
        return
    print("URL приёмника — адрес, по которому мастер будет слать кадры,")
    print("например https://vps1.example.com или http://203.0.113.10:8090")
    url = ask("URL").rstrip("/")
    token = gen_token()
    line = f"{name} | {url} | {token} | on"
    with settings.receivers_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    run(["chmod", "0640", str(settings.receivers_file)], check=False)
    print(f"\nСтрока добавлена в {settings.receivers_file}:")
    print(f"  {line}")
    block = receiver_env_block(token, name, settings.port)
    seed_dir = settings.seed_dir
    seed_dir.mkdir(parents=True, exist_ok=True)
    block_path = seed_dir / f"env-{name}.txt"
    block_path.write_text(block + "\n", encoding="utf-8")
    run(["chmod", "0600", str(block_path)], check=False)
    print(f"\nГотовый .env для приёмника сохранён в: {block_path}")
    print("Перенесите его на приёмник как .env (или скопируйте содержимое вручную):")
    print(block)
    if confirm("Проверить связь с приёмником сейчас?", default=False):
        _probe_receiver(url, token)


def _probe_receiver(url: str, token: str) -> None:
    import gzip as _gzip

    payload = {
        "master_id": load_settings().master_id,
        "app_version": __version__,
        "schema_version": 1,
    }
    body = _gzip.compress(json.dumps(payload).encode())
    request = urllib.request.Request(
        f"{url}/api/ingest/hello",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(f"  Связь есть. Схема приёмника: {data.get('schema_version')}, "
                  f"последний сэмпл: {data.get('last_sample_ts')}")
    except Exception as exc:  # noqa: BLE001
        print(f"  Приёмник не ответил: {exc}")
        print("  Это нормально, если он ещё не установлен — мастер повторит сам.")


def manage_receivers() -> None:
    settings = load_settings()
    receivers, _errors = parse_receivers(
        settings.receivers_file.read_text(encoding="utf-8")
    ) if settings.receivers_file.exists() else ([], [])
    if not receivers:
        print("Список приёмников пуст.")
        return
    header("Управление приёмниками")
    for index, receiver in enumerate(receivers, start=1):
        print(f"  {index}. {receiver.name} — {receiver.url} [{'вкл' if receiver.enabled else 'выкл'}]")
    index = choose("Выберите приёмника", [str(r) for r in receivers])
    if index is None:
        return
    receiver = receivers[index - 1]
    action = choose(
        f"Приёмник {receiver.name}",
        ["Включить/выключить", "Сменить токен", "Показать .env-блок", "Удалить"],
    )
    if action is None:
        return
    lines = settings.receivers_file.read_text(encoding="utf-8").splitlines()
    new_lines = []
    new_token = gen_token() if action == 2 else None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        parts = [part.strip() for part in stripped.split("|")]
        if len(parts) == 4 and parts[0] == receiver.name:
            if action == 1:
                parts[3] = "off" if receiver.enabled else "on"
                new_lines.append(" | ".join(parts))
            elif action == 2:
                parts[2] = new_token or parts[2]
                new_lines.append(" | ".join(parts))
            elif action == 4:
                if not confirm(f"Удалить приёмника {receiver.name}?", default=False):
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    settings.receivers_file.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    if action == 2:
        print(f"\nНовый токен для {receiver.name} (внесён в receivers.list):")
        print(f"  {new_token}")
        print(receiver_env_block(new_token, receiver.name, settings.port))
    elif action == 4:
        print(f"Приёмник {receiver.name} удалён из списка.")


def create_seed_menu() -> None:
    settings = load_settings()
    header("Создать пересев (seed)")
    try:
        estimates = {
            "compact": sb_seed.estimate_seed_size(settings.db_path, settings.forward_backfill_days or 60),
            "full": sb_seed.estimate_seed_size(settings.db_path, None),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"Не удалось оценить базу: {exc}")
        return
    print(f"  В базе сэмплов: {estimates['full']['samples']}")
    print(f"  Компактный (срез {settings.forward_backfill_days or 60} дней): "
          f"~{estimates['compact']['gz_mb']:.0f} МБ .gz, {estimates['compact']['samples']} сэмплов")
    print(f"  Полный:                          ~{estimates['full']['gz_mb']:.0f} МБ .gz, {estimates['full']['samples']} сэмплов")
    choice = choose("Вариант", [
        f"Компактный (payload старше {settings.forward_backfill_days or 60} дней обрезан, графики остаются)",
        "Полный (всё, включая payload)",
    ])
    if choice is None:
        return
    compact_days = (settings.forward_backfill_days or 60) if choice == 1 else None

    receivers, _ = parse_receivers(settings.receivers_file.read_text(encoding="utf-8")) \
        if settings.receivers_file.exists() else ([], [])
    label = "any"
    if receivers:
        names = [r.name for r in receivers] + ["Без привязки к приёмнику"]
        pick = choose("Для какого приёмника (влияет на подпись токена)", names)
        if pick is None:
            return
        if pick <= len(receivers):
            label = receivers[pick - 1].name

    print("\nСоздаю согласованный снимок (VACUUM INTO)...")
    try:
        seed_id, gz_path, passport = sb_seed.create_seed(
            settings.db_path, settings.master_id, settings.seed_dir,
            compact_days=compact_days, schema_version=1,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка создания пересева: {exc}")
        return
    token = gen_token()
    storage = open_storage(settings)
    storage.add_seed_token(token, seed_id, label, settings.seed_token_ttl_hours, settings.seed_token_max_downloads)
    host_hint = settings.host if settings.host not in {"0.0.0.0", "::"} else "IP-ЭТОЙ-МАШИНЫ"
    base = f"http://{host_hint}:{settings.port}"
    print("\nПересев создан:")
    print(f"  id:       {seed_id}")
    print(f"  файл:     {gz_path} ({passport['size_bytes'] / 1024 / 1024:.1f} МБ)")
    print(f"  сэмплов:  {passport['samples_count']}  (компактный: {'да' if compact_days else 'нет'})")
    print(f"  последний сэмпл: {fmt_ts(passport['last_sample_ts'])}")
    print(f"\nСсылка для приёмника (токен: {settings.seed_token_ttl_hours} ч, "
          f"до {settings.seed_token_max_downloads} скачиваний):")
    print(f"  {base}/api/seed/download/{seed_id}?t={token}")
    if label != "any":
        receiver = next((r for r in receivers if r.name == label), None)
        if receiver is not None:
            print("\n" + receiver_env_block(receiver.token, label, settings.port))
    print("На приёмнике: пункт меню «Скачать seed по ссылке» → вставьте ссылку выше.")


def _token_for_label(storage: Storage, label: str) -> str | None:
    for row in storage.list_seed_tokens():
        if row.get("label") == label and row.get("status") == "active":
            return None  # tokens are one-way printed; do not reconstruct
    return None


def seed_links_menu() -> None:
    settings = load_settings()
    storage = open_storage(settings)
    header("Активные seed-ссылки")
    rows = storage.list_seed_tokens()
    if not rows:
        print("  Ссылок нет.")
        return
    print(f"  {'#':<3} {'seed':<26} {'Для':<10} {'Статус':<10} {'Скачиваний':<11} Истекает")
    for index, row in enumerate(rows, start=1):
        print(f"  {index:<3} {row['seed_id']:<26} {str(row.get('label') or '-'):<10} "
              f"{row['status']:<10} {row['downloads_used']}/{row['max_downloads']:<7} {fmt_ts(row['expires_ts'])}")
    index = choose("Выберите ссылку для отзыва (Enter = назад)", [f"{row['seed_id']} ({row['status']})" for row in rows])
    if index is None:
        return
    row = rows[index - 1]
    if confirm(f"Отозвать ссылку на {row['seed_id']}?", default=False):
        storage.revoke_seed_token(row["token_hash"])
        print("Ссылка отозвана.")


def diagnostics_menu() -> None:
    settings = load_settings()
    header("Диагностика")
    storage = open_storage(settings)
    stats = storage.stats()
    print(f"  Роль:            {'мастер (serial)' if settings.is_master else 'приёмник (ingest)'}")
    print(f"  master_id:       {settings.master_id}")
    print(f"  БД:              {settings.db_path}")
    print(f"  Сэмплов:         {stats['sample_count']}  ({stats['oldest_at']} … {stats['newest_at']})")
    print(f"  Батарейных строк: {stats['battery_row_count']} (модулей: {stats['battery_modules']})")
    try:
        size_mb = settings.db_path.stat().st_size / 1024 / 1024
        print(f"  Размер БД:       {size_mb:.1f} МБ")
    except OSError:
        pass
    if not settings.is_master:
        events = storage.recent_master_events(10)
        print("\n  Последние события мастера:")
        if not events:
            print("    (нет)")
        for event in events:
            print(f"    {fmt_ts(event['ts'])}  {event['event']}  {event['detail'] or ''}")
    print("\n  Последние строки журнала службы:")
    subprocess.run(["journalctl", "-u", SERVICE, "-n", "15", "--no-pager"], check=False)


def service_menu() -> None:
    while True:
        action = choose(
            f"Служба {SERVICE} (сейчас: {'работает' if service_active() else 'остановлена'})",
            ["Запустить", "Остановить", "Перезапустить", "Статус", "Логи (последние 50)"],
        )
        if action is None:
            return
        if action == 1:
            systemctl("start")
        elif action == 2:
            systemctl("stop")
        elif action == 3:
            systemctl("restart")
        elif action == 4:
            subprocess.run(["systemctl", "status", SERVICE, "--no-pager", "-l"], check=False)
        elif action == 5:
            subprocess.run(["journalctl", "-u", SERVICE, "-n", "50", "--no-pager"], check=False)


def reconfigure_menu() -> None:
    settings = load_settings()
    header("Перенастройка роли и параметров")
    values: dict[str, Any] = {
        "master_id": settings.master_id,
        "dash_port": settings.port,
        "retention_days": settings.retention_days,
    }
    role = wizard_role()
    if role == "serial":
        values["dash_host"] = "127.0.0.1"
        wizard_master(values)
    else:
        values["dash_host"] = "0.0.0.0"
        wizard_receiver(values)
    env_values = build_env_values(values, role)
    target = INSTALL_DIR / ".env" if service_installed() else (BASE_DIR / ".env")
    if target.exists():
        shutil.copy2(target, target.with_suffix(".env.bak"))
    write_env(target, env_values, role)
    print(f".env записан: {target}")
    write_user_list(env_values, target.parent)
    if service_installed():
        systemctl("restart")
        print("Служба перезапущена.")


def master_menu() -> None:
    while True:
        action = choose(
            f"SolarBridge {__version__} — МЕНЮ МАСТЕРА ({settings_summary()})",
            [
                "Статус пересылки",
                "Добавить приёмник",
                "Управление приёмниками",
                "Создать пересев (seed)",
                "Активные seed-ссылки",
                "Восстановить данные из базы приёмника",
                "Обслуживание базы: удалить данные до даты",
                "Диагностика",
                "Служба",
                "Перенастроить роль и параметры",
            ],
        )
        if action is None:
            return
        if action == 1:
            forwarding_status()
        elif action == 2:
            add_receiver()
        elif action == 3:
            manage_receivers()
        elif action == 4:
            create_seed_menu()
        elif action == 5:
            seed_links_menu()
        elif action == 6:
            restore_from_receiver_menu()
        elif action == 7:
            db_cleanup_menu()
        elif action == 8:
            diagnostics_menu()
        elif action == 9:
            service_menu()
        elif action == 10:
            reconfigure_menu()


def restore_from_receiver_menu() -> None:
    """Master recovery: pull the frames a receiver kept into the local DB.

    Scenario: the master's SD card died; the fresh install has an empty
    database while the receiver still holds the full mirror. Copy the
    receiver's data/*.sqlite3 over (scp/USB), then import it here."""
    settings = load_settings()
    header("Восстановление данных мастера из базы приёмника")
    print("Скопируйте базу приёмника на эту машину, например:")
    print("  scp user@receiver:/opt/solarbridge/data/solarbridge.sqlite3 /tmp/rx.sqlite3")
    default_candidates = [Path("/tmp/rx.sqlite3"), Path.home() / "rx.sqlite3"]
    default = next((str(p) for p in default_candidates if p.is_file()), "/tmp/rx.sqlite3")
    source = Path(ask("Путь к базе приёмника", default))
    if not source.is_file():
        print("Файл не найден.")
        return
    print("\nЧто переносим?")
    mode = choose(
        "Режим",
        ["Всё, что есть в базе приёмника",
         "Диапазон дат (с … по …)",
         "С даты до конца"],
    )
    if mode is None:
        return
    since_ts = until_ts = None
    if mode == 2:
        while True:
            raw_from = ask("Дата С (ГГГГ-ММ-ДД)")
            raw_to = ask("Дата ПО (ГГГГ-ММ-ДД)")
            try:
                since_ts = int(datetime.strptime(raw_from, "%Y-%m-%d")
                               .replace(tzinfo=timezone.utc).timestamp())
                until_ts = int(datetime.strptime(raw_to, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc).timestamp()) + 86399
                if since_ts > until_ts:
                    since_ts, until_ts = until_ts, since_ts
                break
            except ValueError:
                print("  Ожидается ГГГГ-ММ-ДД, например 2026-01-31.")
    elif mode == 3:
        while True:
            raw_from = ask("Дата С (ГГГГ-ММ-ДД), кадры этой даты и новее")
            try:
                since_ts = int(datetime.strptime(raw_from, "%Y-%m-%d")
                               .replace(tzinfo=timezone.utc).timestamp())
                break
            except ValueError:
                print("  Ожидается ГГГГ-ММ-ДД, например 2026-01-31.")

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    backup = settings.db_path.with_name(settings.db_path.name + f".bak-{stamp}")
    if settings.db_path.exists():
        shutil.copy2(settings.db_path, backup)
        print(f"Бэкап текущей базы: {backup.name}")

    was_active = service_active()
    if was_active:
        print("Останавливаю службу на время восстановления...")
        systemctl("stop")
    try:
        storage = Storage(settings.db_path, master_id=settings.master_id)
        if since_ts is None:
            print("Смотрю, что есть в базе приёмника...")
        else:
            print("Смотрю, что есть в базе приёмника (диапазон задан)...")
        info = storage.restore_from_db(
            source, since_ts=since_ts, until_ts=until_ts,
            progress=lambda done, total: print(f"\r  {done}/{total}", end="", flush=True),
        )
        print()
        print(f"  Перенесено: {info['inserted']}, пропущено (дубликаты): {info['skipped']}, "
              f"всего в приёмнике: {info['total']}")
        stats = storage.stats()
        print(f"  Теперь в базе мастера: {stats['sample_count']} сэмплов "
              f"({stats['oldest_at']} … {stats['newest_at']})")
    except Exception as exc:  # noqa: BLE001
        print(f"\nОшибка восстановления: {exc}")
    if was_active:
        print("Запускаю службу...")
        systemctl("start")
    print("Готово.")


def db_cleanup_menu() -> None:
    """Free disk space by deleting history older than a chosen date."""
    settings = load_settings()
    header("Обслуживание базы: удалить данные до даты")
    storage = open_storage(settings)
    stats = storage.stats()
    print(f"  Сэмплов: {stats['sample_count']}  ({stats['oldest_at']} … {stats['newest_at']})")
    print(f"  Батарейных строк: {stats['battery_row_count']}")
    try:
        print(f"  Размер БД: {settings.db_path.stat().st_size / 1024 / 1024:.1f} МБ")
    except OSError:
        pass
    raw = ask("Удалить данные ДО даты (ГГГГ-ММ-ДД), Enter = отмена", "")
    if not raw:
        return
    try:
        cutoff = int(datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        print("  Ожидается ГГГГ-ММ-ДД, например 2026-01-31.")
        return
    if not confirm(f"Удалить всё старше {raw}? Действие необратимо (после VACUUM)", default=False):
        return
    was_active = service_active()
    if was_active:
        print("Останавливаю службу на время очистки...")
        systemctl("stop")
    try:
        before = settings.db_path.stat().st_size if settings.db_path.exists() else 0
        deleted = storage.purge_before(cutoff, vacuum=True)
        after = settings.db_path.stat().st_size if settings.db_path.exists() else 0
        print(f"  Удалено сэмплов: {deleted['samples']}, батарейных строк: {deleted['battery']}")
        print(f"  Размер БД: {before / 1024 / 1024:.1f} → {after / 1024 / 1024:.1f} МБ")
    except Exception as exc:  # noqa: BLE001
        print(f"\nОшибка очистки: {exc}")
    if was_active:
        print("Запускаю службу...")
        systemctl("start")
    print("Готово.")


# --------------------------------------------------------------------- receiver menu


def receiver_status() -> None:
    settings = load_settings()
    header("Статус приёмника")
    storage = open_storage(settings)
    stats = storage.stats()
    print(f"  Служба:          {'работает' if service_active() else 'остановлена'}")
    print(f"  master_id (ожидался от мастера): появится после первого кадра")
    print(f"  Сэмплов:         {stats['sample_count']}  ({stats['oldest_at']} … {stats['newest_at']})")
    print(f"  Батарейных строк: {stats['battery_row_count']} (модулей: {stats['battery_modules']})")
    if service_active():
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{settings.port}/api/master", timeout=5) as response:
                state = json.loads(response.read().decode())
            print(f"  Мастер:          {state.get('master_state')} (версия мастера: {state.get('master_app_version')})")
            print(f"  Heartbeat:       {fmt_age(int(time.time() - (state.get('heartbeat_age_seconds') or 0)))} назад")
            print(f"  Последний кадр:  {state.get('last_frame_at') or 'нет'}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Локальный API недоступен: {exc}")


def pull_seed_menu() -> None:
    settings = load_settings()
    header("Скачать и установить пересев по ссылке")
    url = ask("Ссылка из мастера (…/api/seed/download/<id>?t=…)")
    if not url:
        return
    base, seed_id, token = _parse_seed_url(url)
    if not seed_id or not token:
        print("Не удалось разобрать ссылку: ожидается …/api/seed/download/<id>?t=<токен>")
        return
    target_dir = settings.seed_dir / seed_id
    target_dir.mkdir(parents=True, exist_ok=True)
    passport_url = f"{base}/api/seed/passport/{seed_id}?t={token}"
    gz_path = target_dir / sb_seed.SEED_FILE
    try:
        passport = _download_json(passport_url)
        print(f"  Паспорт: сэмплов {passport.get('samples_count')}, схема {passport.get('schema_version')}, "
              f"создан {fmt_ts(passport.get('created_ts'))}")
        _download_file(f"{base}/api/seed/download/{seed_id}?t={token}", gz_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Скачивание не удалось: {exc}")
        return
    was_active = service_active()
    if was_active:
        print("Останавливаю службу для установки...")
        systemctl("stop")
    try:
        installed = sb_seed.install_seed(
            settings.seed_dir, seed_id, settings.db_path,
            receiver_schema_version=1,
            max_age_days=settings.seed_max_age_days or settings.forward_backfill_days or 60,
        )
        print(f"  Проверка: sha256 ок, схема ок, свежесть ок.")
        print(f"  Бэкап прежней базы: {installed.get('installed_backup')}")
        print(f"  Сэмплов установлено: {installed.get('samples_count')}")
    except Exception as exc:  # noqa: BLE001
        print(f"Установка отменена: {exc}")
        if was_active:
            systemctl("start")
        return
    if confirm("Настроить .env сейчас (токен приёма)?", default=False):
        values: dict[str, Any] = {"master_id": settings.master_id}
        wizard_receiver(values)
        env_values = build_env_values(values, "ingest")
        env_path = BASE_DIR / ".env" if not service_installed() else (INSTALL_DIR / ".env")
        if env_path.exists():
            shutil.copy2(env_path, env_path.with_suffix(".env.bak"))
        write_env(env_path, env_values, "ingest")
        print(f".env записан: {env_path}")
    if confirm("Запустить службу?", default=True):
        systemctl("start")
    print("Готово. Мастер автоматически догрузит кадры, накопившиеся за время копирования.")


def _parse_seed_url(url: str) -> tuple[str, str, str]:
    base = url.split("/api/seed/")[0]
    tail = url.split("/api/seed/")[-1]
    path, _, query = tail.partition("?")
    seed_id = path.split("/")[-1]
    token = ""
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key == "t":
            token = value
    return base, seed_id, token


def _download_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode())


def _download_file(url: str, dest: Path) -> None:
    total_seen = 0
    if dest.exists():
        total_seen = dest.stat().st_size
    request = urllib.request.Request(url)
    if total_seen:
        request.add_header("Range", f"bytes={total_seen}-")
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0) + total_seen
        mode = "ab" if total_seen and response.status == 206 else "wb"
        done = total_seen if mode == "ab" else 0
        with dest.open(mode) as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  Скачано {done / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} МБ "
                          f"({int(done / total * 100)}%)", end="", flush=True)
    print()


def receiver_menu() -> None:
    while True:
        action = choose(
            f"SolarBridge {__version__} — МЕНЮ ПРИЁМНИКА ({settings_summary()})",
            [
                "Статус приёмника",
                "Скачать и установить пересев по ссылке",
                "Настроить .env (токен, порт, retention)",
                "Диагностика",
                "Служба",
                "Перенастроить роль и параметры",
            ],
        )
        if action is None:
            return
        if action == 1:
            receiver_status()
        elif action == 2:
            pull_seed_menu()
        elif action == 3:
            reconfigure_menu()
        elif action == 4:
            diagnostics_menu()
        elif action == 5:
            service_menu()
        elif action == 6:
            reconfigure_menu()


def settings_summary() -> str:
    try:
        settings = load_settings()
        role = "мастер" if settings.is_master else "приёмник"
        return f"{role}, порт {settings.port}"
    except Exception:  # noqa: BLE001
        return "не настроен"


# --------------------------------------------------------------------- entry


def main() -> int:
    require_root()
    print(f"\nSolarBridge {__version__} — установщик и меню управления")
    print(f"Каталог проекта: {BASE_DIR}")

    env_path = INSTALL_DIR / ".env" if service_installed() else BASE_DIR / ".env"
    fresh = not env_path.exists()
    if fresh:
        role = wizard_role()
        values: dict[str, Any] = {}
        if role == "serial":
            values["dash_host"] = "127.0.0.1"
            wizard_master(values)
        else:
            values["dash_host"] = "0.0.0.0"
            wizard_receiver(values)
        env_values = build_env_values(values, role)
        install_system(env_values, role)
    else:
        print(f"Найден существующий .env: {env_path}")

    settings_summary()
    role = load_settings().source_mode
    if role == "serial":
        master_menu()
    else:
        receiver_menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
