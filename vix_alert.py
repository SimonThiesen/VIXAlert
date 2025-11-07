#!/usr/bin/env python3
"""Fetch current VIX index value and determine if threshold exceeded.
Outputs a JSON object to stdout:
{
  "timestamp": ISO8601 string,
  "vix": float value,
  "threshold": float,
  "exceeded": bool
}
If running inside GitHub Actions, also emits outputs via GITHUB_OUTPUT.
"""
from __future__ import annotations
import json
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict

THRESHOLD = 35.0

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("vix_alert")


def fetch_vix() -> float:
    """Return the most recent VIX close value using yfinance.
    Falls back to a daily close if 1m data unavailable.
    Raises RuntimeError if data cannot be retrieved.
    """
    try:
        import yfinance as yf  # noqa: WPS433 (runtime import intentional)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to import yfinance: {exc}") from exc

    # Try high-resolution (1m) intraday data first.
    try:
        data = yf.download("^VIX", period="1d", interval="1m", progress=False)
        if data is not None and not data.empty:
            value = data["Close"].dropna().iloc[-1]
            return round(float(value), 2)
        logger.warning("1m intraday VIX data empty; falling back to daily history.")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to fetch 1m data: %s", exc)

    # Fallback: daily history
    ticker = yf.Ticker("^VIX")
    hist = ticker.history(period="5d")
    if hist is None or hist.empty:
        raise RuntimeError("No VIX data available from yfinance.")
    value = hist["Close"].dropna().iloc[-1]
    return round(float(value), 2)


def build_payload(vix_value: float) -> Dict[str, Any]:
    exceeded = vix_value >= THRESHOLD
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vix": vix_value,
        "threshold": THRESHOLD,
        "exceeded": exceeded,
    }


def emit_github_outputs(payload: Dict[str, Any]) -> None:
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return
    try:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"vix_value={payload['vix']}\n")
            fh.write(f"vix_exceeded={'true' if payload['exceeded'] else 'false'}\n")
            # Provide full JSON for downstream parsing.
            fh.write("vix_payload<<EOF\n")
            fh.write(json.dumps(payload) + "\n")
            fh.write("EOF\n")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to write GitHub output: %s", exc)


def main() -> int:
    try:
        vix_value = fetch_vix()
    except Exception as exc:
        logger.error("Error fetching VIX: %s", exc)
        payload = build_payload(float('nan'))
        payload["error"] = str(exc)
        print(json.dumps(payload))
        # Non-zero exit so workflow can catch operational failures separately.
        return 2

    payload = build_payload(vix_value)
    print(json.dumps(payload))
    emit_github_outputs(payload)

    # Always exit 0; email trigger will use output variable, not failure condition.
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
