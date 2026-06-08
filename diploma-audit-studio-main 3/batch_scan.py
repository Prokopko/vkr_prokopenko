"""
Batch scan — прогоняет список контрактов через Slither + Mythril + LLM
и сохраняет результаты в NocoDB.

Запуск:
    python batch_scan.py           # пропускает уже проанализированные
    python batch_scan.py --force   # перезапускает все
"""

import argparse
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_KEY  = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_BASE = os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api")
DELAY_SEC      = 20   # пауза между контрактами (rate limit LLM)

# ── список контрактов ──────────────────────────────────────────────────────────
# (address, network, ground_truth_label, описание)
# ground_truth: "trusted" | "warning" | "suspicious"
CONTRACTS = [
    # Blue chip — ожидаем trusted
    ("0x514910771AF9Ca656af840dff83E8264EcF986CA", "ethereum", "trusted",  "Chainlink (LINK)"),
    ("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "ethereum", "trusted",  "Uniswap (UNI)"),
    # Централизованные стейблкоины — ожидаем warning (централизация, но легитимны)
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "ethereum", "warning",  "USDC (Circle)"),
    ("0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0", "ethereum", "warning",  "Polygon (MATIC)"),
    ("0x6B175474E89094C44Da98b954EedeAC495271d0F", "ethereum", "warning",  "DAI (MakerDAO)"),
    # Мем-токены
    ("0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", "ethereum", "warning",  "Shiba Inu (SHIB)"),
    ("0x6982508145454Ce325dDbE47a25d4ec3d2311933", "ethereum", "warning",  "PEPE"),
    # Высокий риск централизации
    ("0x2b591e99afe9f32eaa6214f7b7629768c40eeb39", "ethereum", "warning",  "HEX"),
    ("0xd26114cd6EE289AccF82350c8d8487fedB8A0C07", "ethereum", "warning",  "OmiseGO (OMG)"),
]


# ── helpers ────────────────────────────────────────────────────────────────────

def fetch_source(address: str, network: str = "ethereum") -> dict | None:
    chain_map = {"ethereum": "1", "bsc": "56", "base": "8453", "arbitrum": "42161"}
    chain_id  = chain_map.get(network, "1")
    try:
        r = requests.get(
            ETHERSCAN_BASE,
            params={"chainid": chain_id, "module": "contract",
                    "action": "getsourcecode", "address": address, "apikey": ETHERSCAN_KEY},
            timeout=15,
        )
        result = r.json().get("result", [{}])[0]
        src = result.get("SourceCode", "")
        if not src.strip():
            return None
        return {
            "source_code":      src,
            "contract_name":    result.get("ContractName", address[:10]),
            "compiler_version": result.get("CompilerVersion", ""),
        }
    except Exception as exc:
        print(f"    Etherscan error: {exc}")
        return None


def run_full_analysis(source_code: str, address: str, network: str) -> dict | None:
    from analyzers.orchestrator import run_contract_analysis
    result = run_contract_analysis(
        address=address,
        network=network,
        source_code=source_code,
        options={"slither": True, "mythril": True, "llm": True, "semgrep": False},
    )
    if result.get("tool_errors"):
        for e in result["tool_errors"]:
            print(f"    [{e['tool']}] ошибка: {e['error'][:120]}")
    return result


def save_to_db(address, network, contract_name, compiler_version,
               analyst, result) -> int | None:
    from connectors.nocodb_client import insert_scan_run, insert_findings

    llm_sum   = result.get("llm_summary") or {}
    findings  = result.get("findings", [])
    tools     = result.get("tools_used", [])

    run_id = insert_scan_run({
        "analyst":          analyst,
        "address":          address,
        "network":          network,
        "contract_name":    contract_name,
        "compiler_version": compiler_version,
        "source_origin":    "etherscan",
        "status":           result.get("status", "success"),
        "overall_verdict":  llm_sum.get("overall_verdict") or result.get("trust_flag", ""),
        "risk_score":       result.get("risk_score", 0),
        "trust_flag":       result.get("trust_flag", 0),
        "tools_used":       ",".join(tools),
        "summary":          llm_sum.get("summary", ""),
        "llm_verdict":      llm_sum.get("overall_verdict", ""),
        "llm_risk_score":   llm_sum.get("risk_score") or 0,
    })

    if run_id and findings:
        insert_findings([{
            "run_id":           run_id,
            "tool":             f.get("tool", ""),
            "rule_id":          f.get("rule_id", ""),
            "title":            f.get("title", ""),
            "severity_label":   f.get("severity", "info"),
            "confidence_label": f.get("confidence", "medium"),
            "category":         f.get("category", "security"),
            "description":      f.get("description", ""),
            "recommendation":   f.get("recommendation") or "",
            "file_path":        f.get("file_path") or "",
            "line_start":       f.get("line_start"),
            "line_end":         f.get("line_end"),
        } for f in findings])

    return run_id


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="перезапустить даже уже проанализированные контракты")
    args = parser.parse_args()

    from connectors.nocodb_client import find_cached_run

    print(f"Контрактов в очереди: {len(CONTRACTS)}")
    print(f"Инструменты: Slither + Mythril + LLM")
    print(f"Режим: {'--force (перезапуск всех)' if args.force else 'cache-first'}\n")

    ok = skip = fail = 0

    for i, (address, network, ground_truth, label) in enumerate(CONTRACTS, 1):
        print(f"[{i}/{len(CONTRACTS)}] {label}  ({address[:12]}…)  gt={ground_truth}")

        if not args.force:
            cached = find_cached_run(address, network)
            if cached:
                print(f"    → уже в кеше (Id={cached.get('Id')}), пропускаем\n")
                skip += 1
                continue

        # Etherscan
        eth = fetch_source(address, network)
        if not eth:
            print(f"    → нет верифицированного кода, пропускаем\n")
            fail += 1
            continue
        print(f"    контракт: {eth['contract_name']}, {len(eth['source_code'])} симв.")

        # Анализ
        result = run_full_analysis(eth["source_code"], address, network)
        if not result:
            fail += 1
            time.sleep(DELAY_SEC * 2)
            continue

        llm_sum = result.get("llm_summary") or {}
        print(f"    вердикт: {llm_sum.get('overall_verdict', '—')}  "
              f"risk: {result.get('risk_score', 0)}  "
              f"findings: {len(result.get('findings', []))}  "
              f"(gt: {ground_truth})")

        run_id = save_to_db(
            address, network,
            eth["contract_name"], eth["compiler_version"],
            "batch", result,
        )
        print(f"    сохранено → run_id={run_id}\n")
        ok += 1

        if i < len(CONTRACTS):
            print(f"    пауза {DELAY_SEC} сек…")
            time.sleep(DELAY_SEC)

    print(f"\n{'='*40}")
    print(f"Готово: {ok} успешно, {skip} в кеше, {fail} ошибок")


if __name__ == "__main__":
    main()
