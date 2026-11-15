"""Seed (reseed) support: consistent DB snapshot + passport + token-gated download.

A seed is a consistent copy of the master database made with VACUUM INTO,
gzipped, described by a passport JSON (master_id, schema_version, created_at,
sha256, row counts, last sample ts) and downloadable over HTTP with a one-time
token (24 h, limited downloads, Range resume).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import __version__
from .storage import SCHEMA_VERSION


SEED_FILE = "seed.sqlite.gz"
PASSPORT_FILE = "passport.json"


def create_seed(
    db_path: Path,
    master_id: str,
    seed_dir: Path,
    compact_days: int | None = None,
    schema_version: int = SCHEMA_VERSION,
) -> tuple[str, Path, dict[str, Any]]:
    """Create a seed snapshot. Returns (seed_id, gz_path, passport)."""
    seed_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    seed_id = f"{master_id}-{stamp}"
    target_dir = seed_dir / seed_id
    if target_dir.exists():
        raise RuntimeError(f"seed id already exists: {seed_id}")
    target_dir.mkdir(parents=True)

    tmp_db = target_dir / "snapshot.sqlite3"
    source = sqlite3.connect(db_path, timeout=15)
    try:
        source.row_factory = sqlite3.Row
        counts_row = source.execute(
            "SELECT COUNT(*) AS c, MAX(captured_ts) AS m FROM samples"
        ).fetchone()
        battery_row = source.execute("SELECT COUNT(*) AS c FROM battery_samples").fetchone()
        samples_count = int(counts_row["c"])
        last_sample_ts = int(counts_row["m"]) if counts_row["m"] is not None else None
        battery_rows = int(battery_row["c"])
        source.execute("VACUUM INTO ?", (str(tmp_db),))
    finally:
        source.close()

    if compact_days:
        cutoff = int(time.time()) - compact_days * 86400
        compact = sqlite3.connect(tmp_db)
        try:
            compact.execute("UPDATE samples SET payload_json = '{}' WHERE captured_ts < ?", (cutoff,))
            compact.execute("UPDATE battery_samples SET payload_json = '{}' WHERE captured_ts < ?", (cutoff,))
            compact.commit()
            compact.execute("VACUUM")
        finally:
            compact.close()

    gz_path = target_dir / SEED_FILE
    raw = tmp_db.read_bytes()
    gz_path.write_bytes(gzip.compress(raw, compresslevel=6))
    tmp_db.unlink()
    tmp_db.with_name(tmp_db.name + "-wal").unlink(missing_ok=True)
    tmp_db.with_name(tmp_db.name + "-shm").unlink(missing_ok=True)

    passport = {
        "seed_id": seed_id,
        "master_id": master_id,
        "app_version": __version__,
        "schema_version": schema_version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_ts": int(time.time()),
        "sha256": hashlib.sha256(gz_path.read_bytes()).hexdigest(),
        "size_bytes": gz_path.stat().st_size,
        "samples_count": samples_count,
        "battery_rows": battery_rows,
        "last_sample_ts": last_sample_ts,
        "compact_days": compact_days or 0,
    }
    (target_dir / PASSPORT_FILE).write_text(
        json.dumps(passport, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return seed_id, gz_path, passport


def read_passport(seed_dir: Path, seed_id: str) -> dict[str, Any]:
    path = seed_dir / seed_id / PASSPORT_FILE
    if not path.is_file():
        raise FileNotFoundError(f"passport not found for seed {seed_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_passport(
    passport: dict[str, Any],
    gz_path: Path,
    receiver_schema_version: int,
    max_age_days: int | None = None,
) -> None:
    """Raise ValueError with a human-readable reason when the seed must be rejected."""
    digest = hashlib.sha256(gz_path.read_bytes()).hexdigest()
    if digest != passport.get("sha256"):
        raise ValueError("checksum mismatch: seed file is corrupted")
    schema = int(passport.get("schema_version") or 0)
    if schema > receiver_schema_version:
        raise ValueError(
            f"seed schema {schema} is newer than receiver schema {receiver_schema_version}; update the receiver"
        )
    if schema < 1:
        raise ValueError("seed schema version missing")
    if max_age_days:
        age_days = (time.time() - int(passport.get("created_ts") or 0)) / 86400
        if age_days > max_age_days:
            raise ValueError(
                f"seed is {int(age_days)} days old (max {max_age_days}); create a fresh seed"
            )


def install_seed(
    seed_dir: Path,
    seed_id: str,
    db_path: Path,
    receiver_schema_version: int,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """Verify and install a seed into db_path, backing up the current database."""
    passport = read_passport(seed_dir, seed_id)
    gz_path = seed_dir / seed_id / SEED_FILE
    if not gz_path.is_file():
        raise FileNotFoundError(f"seed archive missing for {seed_id}")
    verify_passport(passport, gz_path, receiver_schema_version, max_age_days)

    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup = db_path.with_name(db_path.name + f".bak-{stamp}")
    if db_path.exists():
        shutil.move(str(db_path), str(backup))
    for suffix in ("-wal", "-shm"):
        stale = db_path.with_name(db_path.name + suffix)
        stale.unlink(missing_ok=True)
    raw = gzip.decompress(gz_path.read_bytes())
    db_path.write_bytes(raw)
    passport["installed_backup"] = backup.name
    return passport


def estimate_seed_size(db_path: Path, compact_days: int | None) -> dict[str, Any]:
    """Rough pre-flight numbers for the installer menu."""
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        source.row_factory = sqlite3.Row
        row = source.execute(
            "SELECT COUNT(*) AS c, MIN(captured_ts) AS o, MAX(captured_ts) AS n FROM samples"
        ).fetchone()
    finally:
        source.close()
    count = int(row["c"])
    if compact_days and row["o"]:
        cutoff = int(time.time()) - compact_days * 86400
        fresh = source_get_recent_count(db_path, cutoff)
        count = fresh
    return {
        "samples": count,
        "json_mb": count * 7.0 / 1024,
        "gz_mb": count * 2.1 / 1024,
        "oldest": row["o"],
        "newest": row["n"],
    }


def source_get_recent_count(db_path: Path, cutoff: int) -> int:
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        row = source.execute(
            "SELECT COUNT(*) AS c FROM samples WHERE captured_ts >= ?", (cutoff,)
        ).fetchone()
        return int(row["c"])
    finally:
        source.close()
