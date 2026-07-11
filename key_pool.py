"""
key_pool.py — Rotating Gemini API key pool with per-key daily usage tracking.

How it works
------------
* Loads all configured keys from env vars (GEMINI_API_KEY, GEMINI_API_KEY1,
  GEMINI_API_KEY2, GEMINI_API_KEY3, …).
* Tracks how many requests each key has made today in data/key_usage.json.
* When the active key gets a 429 daily-quota error, marks it exhausted and
  rotates to the next key automatically.
* If ALL keys are exhausted, raises AllKeysExhaustedException.
"""

from __future__ import annotations

import json
import os
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DAILY_LIMIT          = 20              # Gemini free-tier daily cap
USAGE_FILE           = Path(__file__).parent / "data" / "key_usage.json"
_USAGE_LOCK = threading.Lock()


def _today_str() -> str:
    """UTC date used to scope Gemini's daily usage counters."""
    return str(datetime.now(timezone.utc).date())


# ── Exceptions ─────────────────────────────────────────────────────────────────

class AllKeysExhaustedException(Exception):
    """Raised when every configured API key has hit its daily quota."""


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_usage() -> dict:
    """Load usage data from disk, reset counts if it's a new UTC day."""
    if not USAGE_FILE.exists():
        return {}
    try:
        data = json.loads(USAGE_FILE.read_text())
    except Exception:
        return {}
    # If the saved date is not today, start fresh
    if data.get("date") != _today_str():
        return {}
    return data


def _save_usage(data: dict):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["date"] = _today_str()
    # Write-and-replace means a restart can never observe a partially-written
    # usage file.
    temp_file = USAGE_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2))
    temp_file.replace(USAGE_FILE)


# ── Key pool ───────────────────────────────────────────────────────────────────

class ApiKeyPool:
    """
    A rotating pool of Gemini API keys.

    Usage
    -----
    pool = ApiKeyPool()
    pool.current_key()          # → the active key string
    pool.record_success()       # call after each successful API request
    pool.mark_exhausted()       # call when the current key hits daily limit
    pool.rotate()               # advance to next available key (raises if all done)
    """

    # Env var names to probe, in order
    _ENV_VARS = [
        "GEMINI_API_KEY",
        "GEMINI_API_KEY1",
        "GEMINI_API_KEY2",
        "GEMINI_API_KEY3",
        "GEMINI_API_KEY4",
        "GEMINI_API_KEY5",
    ]

    def __init__(self):
        self._keys: list[str] = self._discover_keys()
        if not self._keys:
            raise ValueError(
                "No Gemini API keys configured. "
                "Set GEMINI_API_KEY (and optionally GEMINI_API_KEY1 … GEMINI_API_KEY3) "
                "in your .env file."
            )
        self._usage: dict     = _load_usage()
        self._index: int      = self._find_first_active()

    # ── Key discovery ──────────────────────────────────────────────────────────

    @classmethod
    def _discover_keys(cls) -> list[str]:
        """Return all non-empty key values in order."""
        keys = []
        for var in cls._ENV_VARS:
            val = os.environ.get(var, "").strip().strip("'\"")
            if val:
                keys.append(val)
        return keys

    @classmethod
    def all_configured_keys(cls) -> list[str]:
        """Return all configured keys (for display in the UI)."""
        return cls._discover_keys()

    # ── Index management ───────────────────────────────────────────────────────

    def _find_first_active(self) -> int:
        """Return the index of the first key that hasn't hit its daily limit."""
        for i, key in enumerate(self._keys):
            if not self._is_exhausted(key):
                return i
        raise AllKeysExhaustedException(
            f"All {len(self._keys)} API key(s) have hit the daily quota "
            f"({DAILY_LIMIT} requests/day free tier). Try again tomorrow."
        )

    # ── Usage tracking ─────────────────────────────────────────────────────────

    def _key_id(self, key: str) -> str:
        """A short identifier for a key (last 6 chars) used as JSON key."""
        return f"key_{key[-6:]}"

    def _is_exhausted(self, key: str) -> bool:
        kid = self._key_id(key)
        entry = self._usage.get(kid, {})
        return entry.get("exhausted", False) or entry.get("count", 0) >= DAILY_LIMIT

    def _increment(self, key: str):
        kid = self._key_id(key)
        # Reload while holding a process-local lock so parallel requests do not
        # overwrite each other's counts. The persisted JSON is the source of
        # truth, not this instance's in-memory dictionary.
        with _USAGE_LOCK:
            self._usage = _load_usage()
            entry = self._usage.setdefault(kid, {"count": 0, "exhausted": False})
            entry["count"] = entry.get("count", 0) + 1
            _save_usage(self._usage)

    def _mark_exhausted_key(self, key: str):
        kid = self._key_id(key)
        with _USAGE_LOCK:
            self._usage = _load_usage()
            entry = self._usage.setdefault(kid, {"count": 0, "exhausted": False})
            entry["exhausted"] = True
            _save_usage(self._usage)

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def current_key(self) -> str:
        return self._keys[self._index]

    def current_key_label(self) -> str:
        k = self.current_key()
        return f"Key #{self._index + 1} (…{k[-6:]})"

    def usage_for(self, key: str) -> dict:
        """Return {"count": int, "exhausted": bool} for a key."""
        kid = self._key_id(key)
        return self._usage.get(kid, {"count": 0, "exhausted": False})

    def all_usage(self) -> list[dict]:
        """Return a list of status dicts for all keys (for the UI)."""
        return self._usage_rows(self._keys, self._usage, self._index)

    @classmethod
    def usage_snapshot(cls) -> list[dict]:
        """Return persisted status even if every configured key is exhausted."""
        keys = cls._discover_keys()
        usage = _load_usage()
        active_index = next(
            (
                i for i, key in enumerate(keys)
                if not usage.get(f"key_{key[-6:]}", {}).get("exhausted", False)
                and usage.get(f"key_{key[-6:]}", {}).get("count", 0) < DAILY_LIMIT
            ),
            None,
        )
        return cls._usage_rows(keys, usage, active_index)

    @staticmethod
    def _usage_rows(keys: list[str], usage: dict, active_index: int | None) -> list[dict]:
        result = []
        for i, key in enumerate(keys):
            u = usage.get(f"key_{key[-6:]}", {"count": 0, "exhausted": False})
            result.append({
                "index":     i + 1,
                "suffix":    f"…{key[-6:]}",
                "count":     u.get("count", 0),
                "exhausted": u.get("exhausted", False) or u.get("count", 0) >= DAILY_LIMIT,
                "active":    i == active_index,
            })
        return result

    def record_request(self, key: str | None = None):
        """Persist one Gemini request, including requests that return a quota error."""
        self._increment(key or self.current_key())

    def record_success(self):
        """Backward-compatible alias for callers that only tracked successes."""
        self.record_request()

    def mark_exhausted(self, key: str | None = None):
        """
        Mark the current key as daily-exhausted, then rotate to the next key.
        Raises AllKeysExhaustedException if none remain.
        """
        key = key or self.current_key()
        self._mark_exhausted_key(key)
        logger.warning("Key %s exhausted. Rotating…", self.current_key_label())
        self.rotate()

    def rotate(self):
        """
        Advance _index to the next non-exhausted key.
        Raises AllKeysExhaustedException if all keys are spent.
        """
        for offset in range(1, len(self._keys) + 1):
            candidate = (self._index + offset) % len(self._keys)
            if not self._is_exhausted(self._keys[candidate]):
                self._index = candidate
                logger.info("Rotated to %s", self.current_key_label())
                return
        raise AllKeysExhaustedException(
            f"All {len(self._keys)} API key(s) have hit the daily quota "
            f"({DAILY_LIMIT} requests/day free tier). Try again tomorrow."
        )

    def apply_to_env(self):
        """Set GEMINI_API_KEY env var to the current key so parser.py picks it up."""
        os.environ["GEMINI_API_KEY"] = self.current_key()
