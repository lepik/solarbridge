"""Dashboard login (optional) backed by a plain-text user_list file.

Enabled with SB_AUTH=1. Credentials live one per line in user_list
("login:password", plaintext by design — protect the file with 0600/0640).
On a successful POST /api/auth/login the server issues a random token,
persists its hash-free record in data/auth_tokens.json (30-day TTL) and
returns it in the body plus a `sb_auth` cookie; the browser then keeps the
token in localStorage and sends it via X-Auth-Token / cookie / ?token=
(EventSource) on every dashboard request. Ingest endpoints keep their own
Bearer tokens and are never affected by this store.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

TOKEN_TTL_S = 30 * 86400


class AuthStore:
    """Users from user_list + issued tokens persisted between restarts."""

    def __init__(self, user_list_path: Path, tokens_path: Path) -> None:
        self.user_list_path = Path(user_list_path)
        self.tokens_path = Path(tokens_path)
        self._lock = threading.Lock()
        self._tokens: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------ users

    def _load_users(self) -> dict[str, str]:
        """Parse user_list; reread on every call so edits apply without restart."""
        users: dict[str, str] = {}
        try:
            text = self.user_list_path.read_text(encoding="utf-8")
        except OSError:
            return users
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            login, _, password = line.partition(":")
            login, password = login.strip(), password.strip()
            if login and password:
                users[login] = password
        return users

    def verify(self, login: str, password: str) -> bool:
        users = self._load_users()
        expected = users.get(login)
        if not expected:
            # Compare against a dummy to keep timing uniform for unknown logins.
            hmac.compare_digest(password, "nonexistent-password")
            return False
        return hmac.compare_digest(password, expected)

    # ------------------------------------------------------------------ tokens

    def _load_tokens(self) -> dict[str, dict[str, Any]]:
        if self._tokens is None:
            try:
                self._tokens = json.loads(self.tokens_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._tokens = {}
        return self._tokens

    def _save_tokens(self, tokens: dict[str, dict[str, Any]]) -> None:
        self.tokens_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokens_path.write_text(
            json.dumps(tokens, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        try:
            self.tokens_path.chmod(0o600)
        except OSError:
            pass

    def issue_token(self, login: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            tokens = self._load_tokens()
            tokens[token] = {
                "login": login,
                "issued_ts": int(time.time()),
                "expires_ts": int(time.time()) + TOKEN_TTL_S,
            }
            # Prune expired entries on every issue.
            now = int(time.time())
            for key in [k for k, v in tokens.items() if int(v.get("expires_ts", 0)) <= now]:
                del tokens[key]
            self._save_tokens(tokens)
        return token

    def validate_token(self, token: str | None) -> str | None:
        if not token:
            return None
        with self._lock:
            record = self._load_tokens().get(token)
        if not record:
            return None
        if int(record.get("expires_ts", 0)) <= int(time.time()):
            return None
        return str(record.get("login") or "")

    @staticmethod
    def hash_token(token: str) -> str:
        """Stable identifier for logs (never store raw tokens elsewhere)."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
