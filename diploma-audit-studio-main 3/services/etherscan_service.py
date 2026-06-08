import os
import requests
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_BASE_URL = os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api")


CHAIN_ID_MAP = {
    "ethereum": "1",
    "base": "8453",
    "bsc": "56",
    "arbitrum": "42161",
}


def get_contract_metadata(address: str, network: str = "ethereum") -> dict:
    if not ETHERSCAN_API_KEY:
        return {
            "ok": False,
            "error": "ETHERSCAN_API_KEY is not set",
        }

    chain_id = CHAIN_ID_MAP.get(network.lower())
    if not chain_id:
        return {
            "ok": False,
            "error": f"Unsupported network: {network}",
        }

    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "chainid": chain_id,
        "apikey": ETHERSCAN_API_KEY,
    }

    try:
        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Etherscan request failed: {exc}",
        }

    result = data.get("result")
    if not isinstance(result, list) or not result:
        return {
            "ok": False,
            "error": f"Unexpected Etherscan response: {data}",
        }

    item = result[0]
    source_code = item.get("SourceCode") or ""

    if not source_code.strip():
        return {
            "ok": False,
            "error": "Contract source code is empty or contract is not verified.",
            "contract_name": item.get("ContractName"),
            "metadata": item,
        }

    return {
        "ok": True,
        "contract_name": item.get("ContractName"),
        "source_code": source_code,
        "abi": item.get("ABI"),
        "compiler_version": item.get("CompilerVersion"),
        "optimization_used": item.get("OptimizationUsed"),
        "runs": item.get("Runs"),
        "proxy": item.get("Proxy"),
        "implementation": item.get("Implementation"),
        "license_type": item.get("LicenseType"),
        "metadata": item,
    }