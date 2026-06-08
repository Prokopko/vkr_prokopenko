import os
import requests

API_KEY = os.getenv("ETHERSCAN_API_KEY", "1ER5XC8KC7GFBXBAS8E1RHHSS1KIB4KZHS")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"


def get_contract_name(address: str) -> str:
    params = {
        "chainid": "1",
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": API_KEY
    }

    response = requests.get(ETHERSCAN_URL, params=params, timeout=30)
    data = response.json()

    if data.get("status") != "1":
        raise ValueError(f"Etherscan error: {data.get('message')}")

    info = data["result"][0]
    return info.get("ContractName") or address