"""
bulk_processor.py — SDK for batch-processing a folder of invoices / screenshots.

Usage (standalone / scripting):
    from bulk_processor import BulkProcessor

    sdk = BulkProcessor(folder_path="/path/to/invoices", app_name="zepto")
    for result in sdk.process_all():
        print(result)

Rate-limit compliance
---------------------
Google Gemini free-tier limits:
  • 4 requests / minute  — handled by sliding-window RateLimiter (short pauses)
  • 20 requests / day    — handled by ApiKeyPool key rotation

When a key hits its daily cap the pool silently rotates to the next key.
If ALL keys are exhausted, processing stops with AllKeysExhaustedException.

Processed-file tracking
-----------------------
Successfully imported file stems are written to data/processed_files.json.
On re-run, the SDK checks this file without sending any API request, so you
only pay quota for files that genuinely haven't been processed yet.
The file stem (not basename) is used because the same invoice ID can appear
across two PDF pages (e.g. _1 and _2 suffixes with different items).
"""

from __future__ import annotations

import json
import time
import logging
import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Generator, Optional, Callable

from key_pool import ApiKeyPool, AllKeysExhaustedException

logger = logging.getLogger(__name__)

# ── Supported extensions ───────────────────────────────────────────────────────
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PDF_EXTS   = {".pdf"}
ALL_EXTS   = IMAGE_EXTS | PDF_EXTS

# ── Rate-limit config ──────────────────────────────────────────────────────────
MAX_REQUESTS_PER_MINUTE: int = 4
WINDOW_SECONDS: float        = 60.0
PER_MINUTE_COOLDOWN: float   = 75.0    # wait after per-minute 429
PER_MINUTE_MAX_RETRIES: int  = 3

# ── Persistence paths ──────────────────────────────────────────────────────────
DATA_DIR           = Path(__file__).parent / "data"
PROCESSED_FILE     = DATA_DIR / "processed_files.json"
LOGS_DIR           = DATA_DIR / "logs"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class FileResult:
    """Result for a single file processed by the SDK."""
    file_path:    Path
    app_name:     str
    success:      bool
    data:         Optional[dict] = None
    error:        Optional[str]  = None
    elapsed_sec:  float          = 0.0
    skipped:      bool           = False    # True = already imported (no API call)
    key_used:     Optional[str]  = None     # which key suffix processed it


@dataclass
class BulkSummary:
    """Aggregate summary returned after processing a folder."""
    total:    int = 0
    success:  int = 0
    failed:   int = 0
    skipped:  int = 0
    errors:   list[str] = field(default_factory=list)


# ── Processed-file tracker ─────────────────────────────────────────────────────

class ProcessedFileTracker:
    """
    Persists a set of successfully imported file stems to disk.

    The stem is the full filename minus extension, e.g.:
      zepto_invoice_019de6f3-a246-7c25-80aa-bf93e0fe5b56_1780204501855_1

    This is more reliable than order_id because the same order can span
    multiple PDF pages (suffix _1, _2) which have identical order_ids but
    different items — both should be processed.
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()
        self._seed_from_db()

    def _seed_from_db(self):
        """
        On first use (or if the JSON is missing entries), pull all bulk-imported
        file stems from the database so that files already in the DB are never
        re-sent to the API.
        """
        try:
            from database import get_bulk_imported_stems
            db_stems = get_bulk_imported_stems()
            changed  = False
            for stem in db_stems:
                if stem not in self._data:
                    self._data[stem] = {
                        "file":         stem,
                        "processed_at": "(from database)",
                        "source":       "db_seed",
                    }
                    changed = True
            if changed:
                self._save()
        except Exception:
            pass  # DB may not exist yet on very first run

    def _load(self) -> dict:
        if PROCESSED_FILE.exists():
            try:
                return json.loads(PROCESSED_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        PROCESSED_FILE.write_text(json.dumps(self._data, indent=2))

    def is_done(self, file_path: Path) -> bool:
        return file_path.stem in self._data

    def mark_done(self, file_path: Path, meta: dict | None = None):
        self._data[file_path.stem] = {
            "file": file_path.name,
            "processed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            **(meta or {}),
        }
        self._save()

    def all_done_stems(self) -> set[str]:
        return set(self._data.keys())

    def stats(self) -> dict:
        return {
            "total_processed": len(self._data),
            "last_updated": max(
                (v.get("processed_at", "") for v in self._data.values()),
                default="never",
            ),
        }


# ── Daily run logger ───────────────────────────────────────────────────────────

class RunLogger:
    """
    Writes a plain-text log for each bulk-import run to data/logs/.
    Files are named  YYYY-MM-DD_HH-MM-SS.log  for easy browsing.
    """

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._path = LOGS_DIR / f"{ts}.log"
        self._lines: list[str] = []
        self._write(f"=== Bulk Import Run — {ts} ===\n")

    def _write(self, line: str):
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._lines.append(line)
        self._write(line)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def lines(self) -> list[str]:
        return list(self._lines)

    @staticmethod
    def list_logs() -> list[Path]:
        """Return log files sorted newest-first."""
        if not LOGS_DIR.exists():
            return []
        return sorted(LOGS_DIR.glob("*.log"), reverse=True)


# ── Rate limiter (per-minute sliding window) ───────────────────────────────────

class RateLimiter:
    """
    Sliding-window rate limiter.
    Tracks the timestamps of the last N calls and sleeps if another
    call would exceed the per-minute cap.
    """

    def __init__(self, max_calls: int = MAX_REQUESTS_PER_MINUTE,
                 window: float = WINDOW_SECONDS):
        self.max_calls   = max_calls
        self.window      = window
        self._call_times: list[float] = []

    def acquire(self, progress_cb: Optional[Callable[[str], None]] = None):
        now = time.monotonic()
        self._call_times = [t for t in self._call_times if now - t < self.window]

        if len(self._call_times) >= self.max_calls:
            oldest     = self._call_times[0]
            sleep_for  = (oldest + self.window) - now

            if sleep_for > 0:
                msg = (
                    f"⏳ Rate limit: {self.max_calls} requests reached. "
                    f"Waiting {sleep_for:.1f}s…"
                )
                logger.info(msg)
                if progress_cb:
                    progress_cb(msg)

                elapsed = 0.0
                while elapsed < sleep_for:
                    slept = min(1.0, sleep_for - elapsed)
                    time.sleep(slept)
                    elapsed += slept
                    if progress_cb and elapsed < sleep_for:
                        progress_cb(
                            f"⏳ Rate limit cooldown — {sleep_for - elapsed:.0f}s remaining…"
                        )

        self._call_times.append(time.monotonic())

    def reset(self):
        self._call_times = []


# ── Main SDK class ─────────────────────────────────────────────────────────────

class BulkProcessor:
    """
    Scan a folder of PDF / screenshot files and process them one-by-one
    through the Gemini parser, rotating API keys on daily-quota exhaustion.

    Parameters
    ----------
    folder_path : str | Path
    app_name    : str | None  e.g. "zepto", "swiggy"; None = auto-detect per file
    recursive   : bool
    skip_hidden : bool
    on_progress : Callable[[str], None] | None
    """

    def __init__(
        self,
        folder_path: str | Path,
        app_name:    str | None = None,
        recursive:   bool = False,
        skip_hidden: bool = True,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        self.folder_path  = Path(folder_path)
        self.app_name     = app_name.lower() if app_name else None
        self.recursive    = recursive
        self.skip_hidden  = skip_hidden
        self.on_progress  = on_progress
        self._limiter     = RateLimiter()
        self._tracker     = ProcessedFileTracker()
        self._run_log     = RunLogger()
        self._pool        = ApiKeyPool()   # raises if no keys configured

    # ── File discovery ─────────────────────────────────────────────────────────

    def discover_files(self) -> list[Path]:
        folder = self.folder_path
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder}")
        glob_fn = folder.rglob if self.recursive else folder.glob
        files: list[Path] = []
        for p in glob_fn("*"):
            if not p.is_file():
                continue
            if self.skip_hidden and (
                p.name.startswith(".") or any(pt.startswith(".") for pt in p.parts)
            ):
                continue
            if p.suffix.lower() in ALL_EXTS:
                files.append(p)
        return sorted(files)

    def scan_folder(self, folder: Path | None = None) -> dict:
        """
        Scan folder WITHOUT making any API calls.
        Returns {"done": [...], "pending": [...]} based on processed_files.json.
        """
        target = folder or self.folder_path
        all_files = self.discover_files() if folder is None else [
            p for p in (target.rglob("*") if self.recursive else target.glob("*"))
            if p.is_file() and p.suffix.lower() in ALL_EXTS
        ]
        done    = [p for p in sorted(all_files) if self._tracker.is_done(p)]
        pending = [p for p in sorted(all_files) if not self._tracker.is_done(p)]
        return {"done": done, "pending": pending, "total": len(all_files)}

    # ── Error classification ───────────────────────────────────────────────────

    @staticmethod
    def _is_daily_quota_error(exc: Exception) -> bool:
        msg = str(exc)
        return (
            "PerDay" in msg
            or "per_day" in msg.lower()
            or "free_tier_requests" in msg.lower()
            or "GenerateRequestsPerDay" in msg
            or "'quotaValue': '20'" in msg
            or '"quotaValue": "20"' in msg
        )

    @staticmethod
    def _is_per_minute_quota_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return ("resource_exhausted" in msg or "429" in msg) and not \
               BulkProcessor._is_daily_quota_error(exc)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _emit(self, msg: str):
        """Send a message to the progress callback AND the run log."""
        logger.info(msg)
        self._run_log.log(msg)
        if self.on_progress:
            self.on_progress(msg)

    def _cooldown(self, seconds: float, label: str = "Cooldown"):
        for remaining in range(int(seconds), 0, -1):
            mins, secs = divmod(remaining, 60)
            time_str   = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
            self._emit(f"⏳ {label} — {time_str} remaining…")
            time.sleep(1)

    # ── Core processing ────────────────────────────────────────────────────────

    def _process_file(self, file_path: Path) -> FileResult:
        """
        Process a single file.

        • Daily-quota errors → rotate key, retry on the new key.
          If all keys exhausted → raise AllKeysExhaustedException.
        • Per-minute errors  → short cooldown + retry (same key).
        • Other errors       → return failed FileResult immediately.
        """
        from parser import parse_images, parse_pdf

        ext = file_path.suffix.lower()
        t0  = time.monotonic()

        for attempt in range(1, PER_MINUTE_MAX_RETRIES + 1):
            # Apply current key to env so parser.py picks it up
            self._pool.apply_to_env()
            self._limiter.acquire(self.on_progress)

            try:
                raw = file_path.read_bytes()
                data = (
                    parse_pdf(raw, self.app_name, file_path.name)
                    if ext in PDF_EXTS
                    else parse_images([raw], self.app_name, file_path.name)
                )
                # Resolve the per-file app when auto-detecting
                resolved_app = self.app_name or data.get("_detected_app")
                self._pool.record_success()
                return FileResult(
                    file_path=file_path,
                    app_name=resolved_app or "unknown",
                    success=True,
                    data=data,
                    elapsed_sec=time.monotonic() - t0,
                    key_used=self._pool.current_key_label(),
                )

            except Exception as exc:
                # ── Daily quota → rotate key ──────────────────────────────
                if self._is_daily_quota_error(exc):
                    self._emit(
                        f"🔑 {self._pool.current_key_label()} daily quota exhausted. "
                        "Rotating to next key…"
                    )
                    self._pool.mark_exhausted()   # raises AllKeysExhaustedException if none left
                    self._limiter.reset()
                    # Retry immediately on new key (don't consume an attempt slot)
                    continue

                # ── Per-minute → short wait + retry ──────────────────────
                if self._is_per_minute_quota_error(exc) and attempt < PER_MINUTE_MAX_RETRIES:
                    self._emit(
                        f"⚠️  Per-minute limit on {self._pool.current_key_label()} "
                        f"(attempt {attempt}/{PER_MINUTE_MAX_RETRIES}). "
                        f"Waiting {int(PER_MINUTE_COOLDOWN)}s…"
                    )
                    self._limiter.reset()
                    self._cooldown(PER_MINUTE_COOLDOWN, "Per-minute cooldown")
                    continue

                # ── Any other error ────────────────────────────────────────
                logger.exception("Failed: %s (attempt %d)", file_path.name, attempt)
                return FileResult(
                    file_path=file_path,
                    app_name=self.app_name,
                    success=False,
                    error=str(exc),
                    elapsed_sec=time.monotonic() - t0,
                    key_used=self._pool.current_key_label(),
                )

        return FileResult(
            file_path=file_path,
            app_name=self.app_name,
            success=False,
            error="Per-minute rate limit: max retries exceeded",
            elapsed_sec=time.monotonic() - t0,
        )

    # ── Public: process_all ────────────────────────────────────────────────────

    def process_all(
        self,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> Generator[FileResult, None, None]:
        """
        Generator — yields a FileResult for each file.

        Files already in processed_files.json are skipped without any API call.
        On AllKeysExhaustedException the generator stops and logs a message.
        """
        files = self.discover_files()
        self._limiter.reset()

        key_info = ", ".join(f"Key #{i+1}" for i in range(self._pool.key_count))
        self._emit(
            f"🔑 Using {self._pool.key_count} API key(s): {key_info}. "
            f"Starting {len(files)} file(s)…"
        )

        for file_path in files:
            if stop_flag and stop_flag():
                self._emit("🛑 Processing cancelled.")
                break

            # ── Already done? Skip without API call ───────────────────────
            if self._tracker.is_done(file_path):
                yield FileResult(
                    file_path=file_path,
                    app_name=self.app_name or "auto",
                    success=True,
                    skipped=True,
                )
                continue

            self._emit(f"Processing {file_path.name}…")

            try:
                result = self._process_file(file_path)
            except AllKeysExhaustedException as e:
                self._emit(f"🚫 {e}")
                return

            if result.success:
                self._tracker.mark_done(file_path, {"app": result.app_name})
                self._emit(f"✅ Parsed: {file_path.name}"
                           + (f" ({result.app_name})" if not self.app_name else ""))
            else:
                self._emit(f"❌ Failed: {file_path.name} — {result.error}")

            yield result

    # ── Utility ────────────────────────────────────────────────────────────────

    def summarise(self, results: list[FileResult]) -> BulkSummary:
        summary = BulkSummary(total=len(results))
        for r in results:
            if r.skipped:
                summary.skipped += 1
            elif r.success:
                summary.success += 1
            else:
                summary.failed += 1
                summary.errors.append(f"{r.file_path.name}: {r.error}")
        return summary

    @property
    def run_log(self) -> RunLogger:
        return self._run_log

    @property
    def tracker(self) -> ProcessedFileTracker:
        return self._tracker

    @property
    def key_pool(self) -> ApiKeyPool:
        return self._pool
