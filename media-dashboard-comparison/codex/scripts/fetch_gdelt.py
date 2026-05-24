from __future__ import annotations

import time
from datetime import datetime
import os
from typing import Any

import requests


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTFetchError(RuntimeError):
    pass


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


def fetch_gdelt_window(query: str, start: datetime, end: datetime, max_records: int = 250, retries: int | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "startdatetime": _format_dt(start),
        "enddatetime": _format_dt(end),
        "maxrecords": str(max_records),
        "sort": "datedesc",
    }
    warnings: list[str] = []
    timeout = float(os.getenv("GDELT_REQUEST_TIMEOUT", "12"))
    retries = retries or int(os.getenv("GDELT_RETRIES", "2"))
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(GDELT_ENDPOINT, params=params, timeout=timeout)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise GDELTFetchError(f"GDELT transient HTTP {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            return payload.get("articles", []) or [], warnings
        except Exception as exc:  # noqa: BLE001 - capture network/json failures for retry notes
            if attempt == retries:
                warnings.append(f"GDELT window failed for {start.date()} to {end.date()}: {exc}")
                return [], warnings
            time.sleep(2 ** (attempt - 1))
    return [], warnings
