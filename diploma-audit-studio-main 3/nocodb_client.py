import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

NOCODB_URL = os.getenv("NOCODB_URL", "https://app.nocodb.com").rstrip("/")
NOCODB_TOKEN = os.getenv("NOCODB_TOKEN")
TABLE_ID ="mm3y3zb93p9sga1" #os.getenv("TABLE_ID")

if not NOCODB_TOKEN:
    raise ValueError("NOCODB_TOKEN is not set")

if not TABLE_ID:
    raise ValueError("TABLE_ID is not set")


def fetch_records(limit: int = 100, where: str = "") -> list[dict]:
    url = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records"
    headers = {"xc-token": NOCODB_TOKEN}
    params = {"limit": limit}
    if where:
        params["where"] = where

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("list", [])


def fetch_dataframe(limit: int = 100, where: str = "") -> pd.DataFrame:
    records = fetch_records(limit=limit, where=where)
    return pd.DataFrame(records)


def insert_record(result: str, trust_flag: int) -> dict:
    url = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records"
    headers = {
        "xc-token": NOCODB_TOKEN,
        "Content-Type": "application/json",
    }
    payload = {
        "result": result,
        "trust_flag": trust_flag,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()