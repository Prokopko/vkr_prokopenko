from __future__ import annotations

import pandas as pd


def check_nocodb_config() -> str:
    try:
        from connectors.nocodb_client import is_configured
        if is_configured():
            return "NocoDB OK — scan_runs + findings подключены."
        return "NocoDB: не все переменные заданы в .env (NOCODB_TOKEN, NOCODB_TABLE_SCAN_RUNS, NOCODB_TABLE_FINDINGS)."
    except Exception as exc:
        return f"NocoDB ошибка: {exc}"


def get_recent_runs(limit: int = 50, analyst: str = "") -> pd.DataFrame:
    try:
        from connectors.nocodb_client import get_recent_runs as _get
        rows = _get(limit=limit, analyst=analyst)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()