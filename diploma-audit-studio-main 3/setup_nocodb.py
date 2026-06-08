"""
One-time setup script: adds missing columns to existing NocoDB tables
and seeds the tools reference table.

Run once:
    python setup_nocodb.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOCODB_TOKEN")
BASE_URL = (os.getenv("NOCODB_URL", "https://app.nocodb.com")).rstrip("/")
BASE_ID = "p74cfn7e7b1kq6b"

TABLE_IDS = {
    "scan_runs": "m9xlx7hsyd57f3o",
    "findings":  "mjetc4v2vu2ptpm",
    "tools":     "m7yihn541d8lskz",
    "contracts": "mcjg8bhnxdj28ba",
}

HEADERS = {"xc-token": TOKEN, "Content-Type": "application/json"}


# ── helpers ────────────────────────────────────────────────────────────────────

def existing_columns(table_id: str) -> set[str]:
    r = requests.get(
        f"{BASE_URL}/api/v1/db/meta/tables/{table_id}",
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return {c["title"] for c in r.json().get("columns", [])}


def add_column(table_id: str, title: str, uidt: str, extra: dict | None = None) -> None:
    payload = {"title": title, "uidt": uidt, **(extra or {})}
    r = requests.post(
        f"{BASE_URL}/api/v1/db/meta/tables/{table_id}/columns",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    if r.status_code in (200, 201):
        print(f"  + {title} ({uidt})")
    else:
        print(f"  ! {title} — {r.status_code} {r.text[:120]}")


def add_columns_if_missing(table_name: str, columns: list[tuple]) -> None:
    table_id = TABLE_IDS[table_name]
    existing = existing_columns(table_id)
    print(f"\n[{table_name}]")
    for title, uidt, *extra in columns:
        if title in existing:
            print(f"  = {title} (already exists)")
        else:
            add_column(table_id, title, uidt, extra[0] if extra else None)


def insert_row(table_id: str, payload: dict) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/v2/tables/{table_id}/records",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_rows(table_id: str, where: str = "") -> list[dict]:
    params = {"limit": 100}
    if where:
        params["where"] = where
    r = requests.get(
        f"{BASE_URL}/api/v2/tables/{table_id}/records",
        headers=HEADERS,
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("list", [])


# ── column definitions ─────────────────────────────────────────────────────────

SCAN_RUN_COLUMNS = [
    # analyst identity
    ("analyst",          "SingleLineText"),
    # contract info (denormalized for fast cache lookup)
    ("address",          "SingleLineText"),
    ("network",          "SingleLineText"),
    ("contract_name",    "SingleLineText"),
    ("compiler_version", "SingleLineText"),
    ("source_origin",    "SingleLineText"),   # etherscan | upload | manual
    # results
    ("status",           "SingleLineText"),   # success | partial_success | failed
    ("overall_verdict",  "SingleLineText"),   # trusted | warning | suspicious
    ("risk_score",       "Number"),
    ("trust_flag",       "Number"),
    ("tools_used",       "SingleLineText"),   # comma-separated
    ("summary",          "LongText"),
    ("llm_verdict",      "SingleLineText"),
    ("llm_risk_score",   "Number"),
    ("source_code",      "LongText"),
]

FINDING_COLUMNS = [
    ("run_id",           "Number"),           # FK → scan_runs.Id
    ("tool",             "SingleLineText"),   # slither | mythril | semgrep | llm
    ("rule_id",          "SingleLineText"),
    ("title",            "SingleLineText"),
    ("severity_label",   "SingleLineText"),   # critical | high | medium | low | info
    ("confidence_label", "SingleLineText"),   # low | medium | high
    ("category",         "SingleLineText"),   # security | quality | honeypot
    ("description",      "LongText"),
    ("recommendation",   "LongText"),
    ("file_path",        "SingleLineText"),
    ("line_start",       "Number"),
    ("line_end",         "Number"),
]

TOOLS_SEED = [
    {"name": "slither",  "label": "Slither",  "version": "latest"},
    {"name": "mythril",  "label": "Mythril",  "version": "latest"},
    {"name": "semgrep",  "label": "Semgrep",  "version": "latest"},
    {"name": "llm",      "label": "LLM Review (OpenRouter)", "version": "1.0"},
]


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TOKEN:
        sys.exit("NOCODB_TOKEN not set in .env")

    print("=== Adding columns to scan_runs ===")
    add_columns_if_missing("scan_runs", SCAN_RUN_COLUMNS)

    print("\n=== Adding columns to findings ===")
    add_columns_if_missing("findings", FINDING_COLUMNS)

    print("\n=== Seeding tools table ===")
    existing_tools = {row.get("name") for row in fetch_rows(TABLE_IDS["tools"])}
    for tool in TOOLS_SEED:
        if tool["name"] in existing_tools:
            print(f"  = {tool['name']} (already exists)")
        else:
            insert_row(TABLE_IDS["tools"], tool)
            print(f"  + {tool['name']}")

    print("\nDone.")
    print("\nAdd these to your .env:")
    print(f"  NOCODB_TABLE_SCAN_RUNS={TABLE_IDS['scan_runs']}")
    print(f"  NOCODB_TABLE_FINDINGS={TABLE_IDS['findings']}")
    print(f"  NOCODB_TABLE_TOOLS={TABLE_IDS['tools']}")
    print(f"  NOCODB_TABLE_CONTRACTS={TABLE_IDS['contracts']}")


if __name__ == "__main__":
    main()