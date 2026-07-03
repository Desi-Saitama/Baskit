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
import time
import logging
from pathlib import Path
from datetime import date

logger = logging.getLogger(__name__)

DAILY_LIMIT          = 20              # Gemini free-tier daily cap
USAGE_FILE           = Path(__file__).parent / "data" / "key_usage.json"
TODAY_STR            = str(date.today())   # recalculated at import; fine for a day's run


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
    if data.get("date") != TODAY_STR:
        return {}
    return data


def _save_usage(data: dict):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["date"] = TODAY_STR
    USAGE_FILE.write_text(json.dumps(data, indent=2))


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
        entry = self._usage.setdefault(kid, {"count": 0, "exhausted": False})
        entry["count"] = entry.get("count", 0) + 1
        _save_usage(self._usage)

    def _mark_exhausted_key(self, key: str):
        kid = self._key_id(key)
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
        result = []
        for i, key in enumerate(self._keys):
            u = self.usage_for(key)
            result.append({
                "index":     i + 1,
                "suffix":    f"…{key[-6:]}",
                "count":     u.get("count", 0),
                "exhausted": self._is_exhausted(key),
                "active":    i == self._index,
            })
        return result

    def record_success(self):
        """Call after each successful API call to track usage."""
        self._increment(self.current_key())

    def mark_exhausted(self):
        """
        Mark the current key as daily-exhausted, then rotate to the next key.
        Raises AllKeysExhaustedException if none remain.
        """
        key = self.current_key()
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
