#!/usr/bin/env python3
"""Fetch current VIX index value and determine if threshold exceeded.
Outputs a JSON object to stdout:
{
  "timestamp": ISO8601 string,
  "vix": float value,
  "threshold": float,
  "exceeded": bool,
  "source": provider string
}
If running inside GitHub Actions, also emits outputs via GITHUB_OUTPUT.
Robust fetching order:
1. yfinance intraday (1m)
2. yfinance daily (5d)
3. Yahoo Finance quote API
4. CBOE official index quote API
Retries applied for transient HTTP errors.
"""
from __future__ import annotations
import json
import os
import sys
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Callable

import math

THRESHOLD = float(os.getenv("VIX_THRESHOLD", "35"))  # allow override via env
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 2

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("vix_alert")

Fetcher = Callable[[], Optional[Tuple[float, str]]]


def _retry(fetch_fn: Fetcher, name: str) -> Optional[Tuple[float, str]]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = fetch_fn()
            if result is not None:
                return result
            logger.warning("%s attempt %d returned no data", name, attempt)
        except Exception as exc:  # pragma: no cover
            logger.warning("%s attempt %d failed: %s", name, attempt, exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SLEEP_SECONDS)
    return None


def _yf_intraday() -> Optional[Tuple[float, str]]:
    try:
        import yfinance as yf  # noqa: WPS433
        data = yf.download("^VIX", period="1d", interval="1m", progress=False)
        if data is not None and not data.empty:
            value = float(data["Close"].dropna().iloc[-1])
            return round(value, 2), "yfinance-intraday"
    except Exception as exc:  # pragma: no cover
        logger.debug("yfinance intraday error: %s", exc)
    return None


def _yf_daily() -> Optional[Tuple[float, str]]:
    try:
        import yfinance as yf  # noqa: WPS433
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="5d")
        if hist is not None and not hist.empty:
            value = float(hist["Close"].dropna().iloc[-1])
            return round(value, 2), "yfinance-daily"
    except Exception as exc:  # pragma: no cover
        logger.debug("yfinance daily error: %s", exc)
    return None


def _yahoo_direct() -> Optional[Tuple[float, str]]:
    import requests
    url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EVIX"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
        result = data.get("quoteResponse", {}).get("result", [])
        if result:
            price = result[0].get("regularMarketPrice")
            if price is not None and not math.isnan(price):
                return round(float(price), 2), "yahoo-direct"
    except Exception as exc:  # pragma: no cover
        logger.debug("Yahoo direct parse error: %s", exc)
    return None


def _cboe_api() -> Optional[Tuple[float, str]]:
    import requests
    url = "https://cdn.cboe.com/api/global/us_indices/quotes/VIX.json"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
        entries = data.get("data") or []
        if entries:
            last_sale = entries[0].get("lastSale")
            if last_sale is not None:
                return round(float(last_sale), 2), "cboe"
    except Exception as exc:  # pragma: no cover
        logger.debug("CBOE parse error: %s", exc)
    return None


FETCH_CHAIN: Tuple[Tuple[str, Fetcher], ...] = (
    ("yfinance-intraday", _yf_intraday),
    ("yfinance-daily", _yf_daily),
    ("yahoo-direct", _yahoo_direct),
    ("cboe", _cboe_api),
)


def fetch_vix() -> Tuple[float, str]:
    """Try multiple providers to obtain the VIX value.
    Returns (value, source) or raises RuntimeError if all fail.
    """
    for name, fn in FETCH_CHAIN:
        logger.info("Trying provider: %s", name)
        result = _retry(fn, name)
        if result is not None:
            value, source = result
            logger.info("Fetched VIX %.2f from %s", value, source)
            return value, source
    raise RuntimeError("All VIX data sources failed")


def build_payload(vix_value: float, source: str) -> Dict[str, Any]:
    exceeded = vix_value >= THRESHOLD
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vix": vix_value,
        "threshold": THRESHOLD,
        "exceeded": exceeded,
        "source": source,
    }


def emit_github_outputs(payload: Dict[str, Any]) -> None:
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return
    try:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"vix_value={payload['vix']}\n")
            fh.write(f"vix_exceeded={'true' if payload['exceeded'] else 'false'}\n")
            fh.write(f"vix_source={payload['source']}\n")
            fh.write("vix_payload<<EOF\n")
            fh.write(json.dumps(payload) + "\n")
            fh.write("EOF\n")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to write GitHub output: %s", exc)


def main() -> int:
    try:
        vix_value, source = fetch_vix()
    except Exception as exc:
        logger.error("Error fetching VIX: %s", exc)
        payload = build_payload(float('nan'), "error")
        payload["error"] = str(exc)
        print(json.dumps(payload))
        return 2

    payload = build_payload(vix_value, source)
    print(json.dumps(payload))
    emit_github_outputs(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
