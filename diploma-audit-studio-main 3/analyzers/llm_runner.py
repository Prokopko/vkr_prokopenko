import json
import os
from typing import Any

import requests

from analyzers.normalizer import map_severity

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Smart Contract Audit Studio")


def run_llm_review(
    contract_path: str,
    source_code: str,
    address: str | None = None,
    network: str | None = None,
) -> dict[str, Any]:
    if not OPENROUTER_API_KEY:
        return {
            "findings": [],
            "error": "OPENROUTER_API_KEY не задан.",
            "llm_summary": None,
        }

    prompt = f"""
Ты — детектор honeypot и rug-pull в смарт-контрактах Solidity.

Проанализируй контракт ниже и верни ТОЛЬКО валидный JSON — без пояснений и markdown снаружи.

## Что искать

Проверь каждый из следующих паттернов. Сообщай о КАЖДОМ найденном:

1. Скрытая комиссия при продаже — fee только на sell, или owner может поднять до 100%.
2. Blacklist/whitelist блокирующий продавцов — owner может заблокировать адрес и он не сможет передать токены.
3. Ограничения maxTx / maxWallet — лимиты, мешающие продажам, но не покупкам.
4. Pausable transfers — owner может заморозить все переводы.
5. Неограниченный mint — нет кепки или owner может чеканить после деплоя.
6. Liquidity rug — owner может вывести LP-токены или весь баланс контракта.
7. Proxy-backdoor / selfdestruct — скрытая точка входа для злоумышленника.
8. Hijack approve/transferFrom — привилегированный адрес может тратить чужие токены.
9. Fake burn — токены "сжигаются", но уходят на скрытый кошелёк.
10. Anti-bot kill switch — блокировки на основе номера блока, ловушки для ранних покупателей.

Игнорируй стилистические замечания (gas, naming), если они не влияют на риск.

## Контекст
- адрес: {address or "неизвестен"}
- сеть: {network or "неизвестна"}

## Схема ответа (только JSON)
{{
  "summary": "2-3 предложения — общий вывод на русском языке",
  "overall_verdict": "trusted|warning|suspicious",
  "risk_score": 0,
  "findings": [
    {{
      "rule_id": "honeypot-sell-tax",
      "title": "Краткий заголовок на русском (до 10 слов)",
      "severity": "critical|high|medium|low|info",
      "category": "honeypot|security|quality",
      "description": "Описание паттерна и почему он опасен — на русском языке",
      "recommendation": "Что проверить или исправить — на русском языке",
      "confidence": "low|medium|high"
    }}
  ]
}}

## Исходный код контракта
```solidity
{source_code}
```
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_NAME:
        headers["X-Title"] = OPENROUTER_APP_NAME

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ты — точный детектор honeypot в смарт-контрактах. Возвращай только валидный JSON. Никакого текста или markdown снаружи JSON-объекта.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        return {
            "findings": [],
            "error": f"Ошибка запроса к OpenRouter: {exc}",
            "llm_summary": None,
        }

    if not text.strip():
        return {
            "findings": [],
            "error": "LLM не вернул текстовый ответ.",
            "llm_summary": None,
        }

    text = _strip_code_fences(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            "findings": [],
            "error": f"LLM вернул невалидный JSON: {text[:1000]}",
            "llm_summary": None,
        }

    raw_findings = data.get("findings", [])
    findings: list[dict[str, Any]] = []

    for item in raw_findings:
        findings.append({
            "tool": "llm",
            "rule_id": item.get("rule_id", "llm-review"),
            "title": item.get("title", "LLM review finding"),
            "severity": map_severity(item.get("severity")),
            "confidence": item.get("confidence", "medium"),
            "category": item.get("category", "honeypot"),
            "description": item.get("description", ""),
            "file_path": "Contract.sol",
            "line_start": None,
            "line_end": None,
            "snippet": None,
            "recommendation": item.get("recommendation"),
            "raw": item,
        })

    llm_summary = {
        "summary": data.get("summary"),
        "overall_verdict": data.get("overall_verdict"),
        "risk_score": data.get("risk_score"),
    }

    return {
        "findings": findings,
        "error": None,
        "llm_summary": llm_summary,
    }


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()