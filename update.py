#!/usr/bin/env python3
"""SolarBridge updater: single file, stdlib only.

Update a running installation from a public release. The release is a zip
plus a sibling ".sha256" checksum file (the same pair attached to the GitHub
release). Machine state (.env, data/, receivers.list, .venv) is never touched.

Usage (on the machine that runs SolarBridge):
  sudo python3 update.py                 # fetch the latest release and apply
  sudo python3 update.py --check         # compare versions only, no changes
  sudo python3 update.py --from FILE.zip # apply a local zip (offline)
  sudo python3 update.py --url URL       # override the release source once
  sudo python3 update.py --force         # allow a downgrade

The release source (SB_UPDATE_URL in .env or --url) defaults to
https://github.com/lepik/solarbridge and is either:
  - a GitHub repository ("https://github.com/owner/repo"): the latest release
    is resolved via the GitHub API and its "*.zip" asset is used, or
  - a direct zip URL: the checksum is expected at "<url>.sha256".

Safety: the current install is copied to backups/ first; after extraction the
service is restarted and /healthz is polled. If the new version does not come
up, the backup is restored automatically and the service is restarted again.
A downgrade is refused unless --force is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

BASE_DIR = Path(__file__).resolve().parent
INSTALL_DIR = Path("/opt/solarbridge")
if (INSTALL_DIR / "solarbridge" / "__init__.py").exists():
    sys.path.insert(0, str(INSTALL_DIR))
elif (BASE_DIR / "solarbridge" / "__init__.py").exists():
    INSTALL_DIR = BASE_DIR

SERVICE = "solarbridge.service"
SERVICE_USER = "sbridge"
DEFAULT_UPDATE_URL = "https://github.com/lepik/solarbridge"
BACKUPS_KEEP = 2
HEALTH_TIMEOUT_S = 60
GITHUB_REPO_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/?$")
GITHUB_API_RE = re.compile(r"^https?://api\.github\.com/repos/([^/]+)/([^/]+)/?$")
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# Never extracted over the running installation (machine state).
PROTECTED_FILES = {".env", "receivers.list"}
PROTECTED_TOP_DIRS = {"data", ".venv", "backups"}
JUNK_DIRS = {"__pycache__", ".git"}


# ------------------------------------------------------------------ helpers

def run(command: list[str], quiet: bool = False) -> subprocess.CompletedProcess | None:
    """Run a system command, reporting instead of raising."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if not quiet and (result.stdout or result.stderr):
        for line in (result.stdout + result.stderr).splitlines():
            if line.strip():
                print(f"  {line}")
    return result


def fetch(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "solarbridge-update"})
    with urllib.request.urlopen(request, timeout=60) as response, open(dest, "wb") as handle:
        shutil.copyfileobj(response, handle)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "solarbridge-update"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_version(text: str) -> tuple[int, int, int]:
    match = VERSION_RE.search(text or "")
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def installed_version() -> str:
    init_path = INSTALL_DIR / "solarbridge" / "__init__.py"
    if not init_path.exists():
        return "0.0.0"
    match = VERSION_RE.search(init_path.read_text(encoding="utf-8"))
    return match.group(0) if match else "0.0.0"


def version_from_zip(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("solarbridge/__init__.py"):
                text = archive.read(name).decode("utf-8")
                match = VERSION_RE.search(text)
                if match:
                    return match.group(0)
    return "0.0.0"


# ------------------------------------------------------------------ sources

def resolve_release(url: str) -> tuple[str, str | None, str | None]:
    """Return (zip_url, sha256_url | None, remote_version | None).

    GitHub repository URLs are resolved through the API, where the checksum
    file and the release tag come from the release assets. Direct zip URLs
    expect "<url>.sha256" and yield no version until the zip is downloaded.
    """
    repo = GITHUB_REPO_RE.match(url) or GITHUB_API_RE.match(url)
    if repo is None:
        return url, f"{url}.sha256", None
    owner, name = repo.group(1), repo.group(2)
    api_url = f"https://api.github.com/repos/{owner}/{name}/releases/latest"
    payload = json.loads(fetch_text(api_url))
    assets = payload.get("assets") or []
    zip_asset = next((a for a in assets if a.get("name", "").endswith(".zip")), None)
    if zip_asset is None:
        raise RuntimeError("в последнем release нет .zip-файла")
    sha_asset = next(
        (a for a in assets if a.get("name") == f"{zip_asset['name']}.sha256"), None
    )
    version = parse_version(payload.get("tag_name") or payload.get("name") or "")
    return (
        zip_asset["browser_download_url"],
        sha_asset["browser_download_url"] if sha_asset else None,
        ".".join(str(part) for part in version) if version != (0, 0, 0) else None,
    )


def download_release(url: str, workdir: Path) -> tuple[Path, str | None]:
    zip_url, sha_url, remote_version = resolve_release(url)
    zip_path = workdir / "release.zip"
    print(f"Скачиваю: {zip_url}")
    fetch(zip_url, zip_path)
    if sha_url:
        sha_path = workdir / "release.zip.sha256"
        print(f"Контрольная сумма: {sha_url}")
        fetch(sha_url, sha_path)
        expected = sha_path.read_text(encoding="utf-8").strip().split()[0].lower()
        actual = sha256_of(zip_path)
        if actual != expected:
            raise RuntimeError(f"sha256 не совпал: {actual} != {expected}")
        print("sha256 OK")
    else:
        print("ВНИМАНИЕ: файла .sha256 нет — целостность не проверена")
    return zip_path, remote_version


def verify_local_zip(zip_path: Path) -> None:
    sibling = zip_path.with_name(zip_path.name + ".sha256")
    if not sibling.exists():
        print("ВНИМАНИЕ: рядом с zip нет .sha256 — целостность не проверена")
        return
    expected = sibling.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = sha256_of(zip_path)
    if actual != expected:
        raise RuntimeError(f"sha256 не совпал: {actual} != {expected}")
    print("sha256 OK")


# ------------------------------------------------------------------ zip

def strip_root(names: list[str]) -> str | None:
    """Common first path component of every member, if there is exactly one.

    Known project directories are never treated as a wrapper, so a zip with
    only solarbridge/* members is applied in place instead of being shifted
    one level up."""
    tops = {PurePosixPath(name).parts[0] for name in names if name.strip("/")}
    if len(tops) != 1:
        return None
    top = tops.pop()
    return None if top in {"solarbridge", "public", "tests", "doc", "data", "venv", ".venv"} else top


def is_skipped(rel_parts: tuple[str, ...]) -> bool:
    if not rel_parts:
        return True
    joined = "/".join(rel_parts)
    if joined in PROTECTED_FILES:
        return True
    if rel_parts[0] in PROTECTED_TOP_DIRS or rel_parts[0] in JUNK_DIRS:
        return True
    return any(part in JUNK_DIRS or part.endswith(".pyc") for part in rel_parts)


def extract(zip_path: Path) -> int:
    """Extract code over INSTALL_DIR, keeping machine state untouched."""
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        root = strip_root(names)
        app_root = INSTALL_DIR.resolve()
        applied = 0
        for name in names:
            parts = PurePosixPath(name).parts
            if root and parts and parts[0] == root:
                parts = parts[1:]
            if is_skipped(parts):
                continue
            target = (app_root / Path(*parts)).resolve()
            if app_root != target and app_root not in target.parents:
                raise RuntimeError(f"zip-путь вне каталога установки: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, open(target, "wb") as handle:
                shutil.copyfileobj(source, handle)
            applied += 1
    for pycache in INSTALL_DIR.rglob("__pycache__"):
        if pycache.is_dir() and ".venv" not in pycache.parts:
            shutil.rmtree(pycache, ignore_errors=True)
    return applied


# ------------------------------------------------------------------ service

def backup() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = INSTALL_DIR / "backups" / f"backup-{stamp}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        INSTALL_DIR,
        dest,
        ignore=shutil.ignore_patterns("data", ".venv", "backups", "__pycache__", "*.pyc", ".git"),
    )
    print(f"Бэкап: {dest}")
    for old in sorted(dest.parent.glob("backup-*"))[:-BACKUPS_KEEP]:
        if old != dest:
            shutil.rmtree(old, ignore_errors=True)
            print(f"Старый бэкап удалён: {old.name}")
    return dest


def restore(backup_dir: Path) -> None:
    shutil.copytree(backup_dir, INSTALL_DIR, dirs_exist_ok=True)
    for pycache in INSTALL_DIR.rglob("__pycache__"):
        if pycache.is_dir() and ".venv" not in pycache.parts:
            shutil.rmtree(pycache, ignore_errors=True)
    print(f"Восстановлено из {backup_dir}")


def read_dash_port() -> int:
    env_path = INSTALL_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SB_DASH_PORT="):
                try:
                    return int(line.split("=", 1)[1])
                except ValueError:
                    break
    return 8090


def restart_service() -> bool:
    if run(["systemctl", "restart", SERVICE]) is None:
        print("systemctl недоступен — перезапустите службу вручную")
        return False
    print(f"Служба {SERVICE} перезапущена")
    return True


def wait_healthz(port: int, timeout_s: int = HEALTH_TIMEOUT_S) -> bool:
    import urllib.error

    url = f"http://127.0.0.1:{port}/healthz"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    return False


def pip_install() -> None:
    venv_python = INSTALL_DIR / ".venv" / "bin" / "python"
    requirements = INSTALL_DIR / "requirements.txt"
    if not venv_python.exists() or not requirements.exists():
        return
    print("Обновляю зависимости venv...")
    run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check",
         "--no-cache-dir", "-r", str(requirements)], quiet=True)


def fix_ownership() -> None:
    if run(["id", "-u", SERVICE_USER], quiet=True) is None:
        return
    run(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", str(INSTALL_DIR)], quiet=True)


# ------------------------------------------------------------------ flow

def apply_update(zip_path: Path, force: bool) -> bool:
    local = installed_version()
    remote = version_from_zip(zip_path)
    local_v, remote_v = parse_version(local), parse_version(remote)
    if remote_v < local_v and not force:
        print(f"Отказ: {remote} старше установленной {local}. Даунгрейд — только с --force")
        return False
    if remote_v == local_v:
        print(f"Версия {local} уже установлена (zip содержит {remote})")
        if not force:
            return True

    applied = extract(zip_path)
    print(f"Файлов применено: {applied} (без .env, data/, receivers.list, .venv)")
    pip_install()
    fix_ownership()
    port = read_dash_port()
    if not restart_service():
        print(f"Файлы обновлены до {remote}. Перезапустите службу вручную: "
              f"sudo systemctl restart {SERVICE}")
        return True
    if not wait_healthz(port):
        print(f"healthz не ответил за {HEALTH_TIMEOUT_S} с — откатываю")
        backup_dirs = sorted((INSTALL_DIR / "backups").glob("backup-*"))
        if backup_dirs:
            restore(backup_dirs[-1])
            restart_service()
            if wait_healthz(port):
                print("Откат выполнен, служба работает на предыдущей версии")
            else:
                print("ОШИБКА: служба не поднялась даже после отката. "
                      "Логи: journalctl -u solarbridge -n 50")
        else:
            print("ОШИБКА: бэкапов нет, откат невозможен")
        return False
    print(f"Готово: SolarBridge обновлён до {remote} (была {local}). "
          f"Интерфейс: http://127.0.0.1:{port}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Обновление SolarBridge из публичного релиза")
    parser.add_argument("--url", help="источник релиза (репозиторий GitHub или прямой URL zip)")
    parser.add_argument("--from", dest="from_zip", help="обновиться из локального zip-файла")
    parser.add_argument("--check", action="store_true", help="только сравнить версии")
    parser.add_argument("--force", action="store_true", help="разрешить даунгрейд")
    args = parser.parse_args()

    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if str(INSTALL_DIR) == "/opt/solarbridge":
            print("Запустите с sudo: sudo python3 update.py")
            return 1
        print("ВНИМАНИЕ: запуск без root — изменения могут не примениться к службе")

    url = args.url or os.environ.get("SB_UPDATE_URL", "")
    if not url and not args.from_zip:
        env_path = INSTALL_DIR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SB_UPDATE_URL="):
                    url = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not url and not args.from_zip:
        url = DEFAULT_UPDATE_URL
    workdir = Path(tempfile.mkdtemp(prefix="solarbridge-update-"))
    try:
        local = installed_version()
        if args.from_zip:
            zip_path = Path(args.from_zip).resolve()
            if not zip_path.exists():
                print(f"Файл не найден: {zip_path}")
                return 1
            verify_local_zip(zip_path)
            remote = version_from_zip(zip_path)
            remote_v = parse_version(remote)
        else:
            zip_path, remote_api = download_release(url, workdir)
            remote = remote_api or version_from_zip(zip_path)
            remote_v = parse_version(remote)
            if remote_api and remote_api != remote:
                print(f"ВНИМАНИЕ: версия в zip ({remote}) не совпадает с release tag ({remote_api})")

        if remote_v < parse_version(local) and not args.force:
            print(f"Установлена: {local} · доступна: {remote} — это даунгрейд, нужен --force")
            return 1
        if remote_v == parse_version(local) and not args.force:
            print(f"Установлена: {local} · доступна: {remote} — уже последняя версия "
                  f"(переустановить/починить: --force)")
            return 0
        print(f"Установлена: {local} · доступна: {remote}"
              + (" — та же версия, применяется принудительно (--force)" if remote_v == parse_version(local) else ""))
        if args.check:
            print("Режим --check: обновление не выполнялось")
            return 0
        print("Каталог установки:", INSTALL_DIR)
        backup()
        if not apply_update(zip_path, force=args.force):
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ОШИБКА: {exc}")
        return 1
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
