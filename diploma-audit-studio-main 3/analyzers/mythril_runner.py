import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any


def _detect_pragma_version(contract_path: str) -> str | None:
    """Extract major.minor from pragma statement."""
    try:
        with open(contract_path, encoding="utf-8") as f:
            source = f.read(4096)
        m = re.search(r"pragma\s+solidity\s+[\^~>=<]*\s*([\d]+\.[\d]+)", source)
        return m.group(1) if m else None
    except Exception:
        return None


def _resolve_solc_version(major_minor: str | None) -> str | None:
    """Return an installed solcx version string (e.g. '0.8.20') matching major.minor."""
    if not major_minor:
        return None
    try:
        from solcx import get_installed_solc_versions
        installed = get_installed_solc_versions()
        candidates = [v for v in installed if str(v).startswith(major_minor + ".")]
        if candidates:
            return str(max(candidates))
    except Exception:
        pass
    return None


def run_mythril(contract_path: str) -> dict[str, Any]:
    myth_cmd = os.getenv("MYTHRIL_BIN") or shutil.which("myth")

    pragma_mm = _detect_pragma_version(contract_path)
    solv = _resolve_solc_version(pragma_mm)

    base_cmd = [myth_cmd] if myth_cmd else [sys.executable, "-m", "mythril"]
    cmd = base_cmd + [
        "analyze",
        contract_path,
        "-o", "json",
        "--execution-timeout", "60",
        "--max-depth", "10",
        "--solver-timeout", "10000",
    ]
    if solv:
        cmd += ["--solv", solv]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "findings": [],
            "error": "Mythril превысил лимит времени выполнения.",
        }
    except Exception as exc:
        return {
            "findings": [],
            "error": f"Ошибка запуска Mythril: {exc}",
        }

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if not stdout:
        return {
            "findings": [],
            "error": (
                "Mythril не вернул JSON. "
                f"returncode={result.returncode}. "
                f"stderr={stderr[:1500]}"
            ),
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "findings": [],
            "error": (
                "Не удалось распарсить JSON от Mythril. "
                f"returncode={result.returncode}. "
                f"stdout={stdout[:400]} "
                f"stderr={stderr[:400]}"
            ),
        }

    if not data.get("success", True):
        err_msg = data.get("error", "Неизвестная ошибка Mythril")
        return {"findings": [], "error": f"Mythril: {err_msg[:400]}"}

    findings = []
    issues = data.get("issues", [])

    for item in issues:
        swc_raw = item.get("swc-id") or item.get("swcID") or "unknown"
        swc_id = f"SWC-{swc_raw}" if str(swc_raw).isdigit() else str(swc_raw)

        description = item.get("description") or {}
        extra = item.get("extra") or {}

        if isinstance(description, dict):
            description_text = (
                description.get("head", "") + " " + description.get("tail", "")
            ).strip()
        else:
            description_text = str(description)

        recommendation = None
        if isinstance(extra, dict):
            recommendation = extra.get("recommendation")

        findings.append({
            "tool": "mythril",
            "rule_id": swc_id,
            "title": item.get("title", "Issue detected"),
            "severity": _map_mythril_severity(item.get("severity")),
            "confidence": "medium",
            "category": "security",
            "description": description_text,
            "file_path": os.path.basename(item.get("filename")) if item.get("filename") else "Contract.sol",
            "line_start": item.get("lineno"),
            "line_end": item.get("lineno"),
            "snippet": item.get("code"),
            "recommendation": recommendation,
            "raw": item,
        })

    return {"findings": findings, "error": None}


def _map_mythril_severity(value: str | None) -> str:
    if not value:
        return "info"

    value = str(value).strip().lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "unknown": "info",
    }
    return mapping.get(value, "info")