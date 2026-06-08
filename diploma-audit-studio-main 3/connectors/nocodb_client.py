"""
NocoDB client — works with the normalized schema:
  scan_runs  → one row per analysis run
  findings   → one row per finding, linked by run_id
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE_URL  = os.getenv("NOCODB_URL", "https://app.nocodb.com").rstrip("/")
_TOKEN     = os.getenv("NOCODB_TOKEN", "")

TABLE_SCAN_RUNS = os.getenv("NOCODB_TABLE_SCAN_RUNS", "")
TABLE_FINDINGS  = os.getenv("NOCODB_TABLE_FINDINGS",  "")
TABLE_TOOLS     = os.getenv("NOCODB_TABLE_TOOLS",     "")
TABLE_CONTRACTS = os.getenv("NOCODB_TABLE_CONTRACTS", "")


def _headers() -> dict[str, str]:
    return {"xc-token": _TOKEN, "Content-Type": "application/json"}


def _post(table_id: str, payload: dict) -> dict:
    r = requests.post(
        f"{_BASE_URL}/api/v2/tables/{table_id}/records",
        headers=_headers(),
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _get(table_id: str, params: dict | None = None) -> list[dict]:
    r = requests.get(
        f"{_BASE_URL}/api/v2/tables/{table_id}/records",
        headers=_headers(),
        params=params or {},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("list", [])


# ── public API ─────────────────────────────────────────────────────────────────

def insert_scan_run(data: dict[str, Any]) -> int:
    """Insert a row into scan_runs. Returns the new row Id."""
    row = _post(TABLE_SCAN_RUNS, data)
    return row.get("Id") or row.get("id")


def insert_findings(findings: list[dict[str, Any]]) -> None:
    """Batch-insert findings. Each item must have run_id set."""
    for finding in findings:
        try:
            _post(TABLE_FINDINGS, finding)
        except Exception:
            pass   # one bad finding shouldn't abort the rest


def find_cached_run(address: str, network: str) -> dict | None:
    """Return the most recent scan_run for this address+network, or None."""
    if not address:
        return None
    where = f"(address,eq,{address})~and(network,eq,{network})"
    rows = _get(
        TABLE_SCAN_RUNS,
        {"where": where, "limit": 1, "sort": "-CreatedAt"},
    )
    return rows[0] if rows else None


def get_recent_runs(limit: int = 50, analyst: str = "") -> list[dict]:
    """Return recent scan_runs, optionally filtered by analyst name."""
    params: dict[str, Any] = {
        "limit": limit,
        "sort": "-CreatedAt",
        "fields": "Id,address,network,contract_name,analyst,overall_verdict,risk_score,trust_flag,tools_used,status,CreatedAt",
    }
    if analyst:
        params["where"] = f"(analyst,eq,{analyst})"
    return _get(TABLE_SCAN_RUNS, params)


def get_findings_for_run(run_id: int) -> list[dict]:
    """Return all findings for a given scan run."""
    return _get(
        TABLE_FINDINGS,
        {"where": f"(run_id,eq,{run_id})", "limit": 500},
    )


def get_all_findings(limit: int = 1000) -> list[dict]:
    """Return all findings across all runs (for dashboard)."""
    return _get(
        TABLE_FINDINGS,
        {
            "limit": limit,
            "fields": "Id,run_id,tool,rule_id,title,severity_label,category",
            "sort": "-Id",
        },
    )


def get_all_runs(limit: int = 500) -> list[dict]:
    """Return all scan runs with fields needed for dashboard."""
    return _get(
        TABLE_SCAN_RUNS,
        {
            "limit": limit,
            "sort": "-CreatedAt",
            "fields": "Id,address,network,contract_name,analyst,overall_verdict,risk_score,trust_flag,tools_used,status,CreatedAt",
        },
    )


def is_configured() -> bool:
    return bool(_TOKEN and TABLE_SCAN_RUNS and TABLE_FINDINGS)