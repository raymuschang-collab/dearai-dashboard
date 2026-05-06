"""Tiny shared helper that wraps a gspread call with 429-aware retry.

Render's regen subprocesses each do a fresh gspread.open_by_key() — when
multiple buttons fire close together, the per-user 60/min Sheets read
quota gets blown and the job dies on the very first call. Wrap that call
in `with_429_retry(...)` and we self-recover instead of failing the job.

Usage:
    from sheets_retry import with_429_retry
    sh = with_429_retry(lambda: gc.open_by_key(sheet_id))
"""
from __future__ import annotations

import time


def _is_quota_error(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg and ("Quota exceeded" in msg or "quota" in msg.lower())


def with_429_retry(fn, *, attempts: int = 4, base_delay: float = 30.0):
    """Run `fn`. On Sheets-API 429, sleep base_delay × attempt# and retry.
    Default total wait budget: 30+60+90 = 3 minutes across 4 attempts.

    Anything other than a 429 propagates immediately so real errors aren't
    masked by retries."""
    last_err: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            if not _is_quota_error(e):
                raise
            last_err = e
            if attempt == attempts - 1:
                break
            sleep_for = base_delay * (attempt + 1)
            print(f"  [429] Sheets quota hit (attempt {attempt+1}/{attempts}); "
                  f"sleeping {sleep_for:.0f}s before retry…", flush=True)
            time.sleep(sleep_for)
    # Out of attempts — re-raise with a clearer message
    raise RuntimeError(
        f"Sheets API 429 quota exceeded after {attempts} attempts "
        f"(total wait {sum(base_delay*(i+1) for i in range(attempts-1)):.0f}s). "
        f"Original: {last_err}"
    )
