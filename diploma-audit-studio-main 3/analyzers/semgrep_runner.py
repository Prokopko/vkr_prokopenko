import json
import os
import shutil
import subprocess
from typing import Any

from analyzers.normalizer import map_severity


def run_semgrep(contract_path: str) -> dict[str, Any]:
    if shutil.which("semgrep") is None:
        return {
            "findings": [],
            "error": "Команда 'semgrep' не найдена в PATH.",
        }

    rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "semgrep_rules.yml")

    cmd = [
        "semgrep",
        "--config",
        rules_path,
        "--json",
        contract_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        return {"findings": [], "error": f"Ошибка запуска Semgrep: {exc}"}

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if not stdout:
        return {
            "findings": [],
            "error": f"Semgrep не вернул JSON. stderr: {stderr}",
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "findings": [],
            "error": f"Не удалось распарсить JSON от Semgrep. stderr: {stderr[:1000]}",
        }

    findings = []
    results = data.get("results", [])

    for item in results:
        extra = item.get("extra", {})
        findings.append({
            "tool": "semgrep",
            "rule_id": item.get("check_id", "unknown"),
            "title": extra.get("message", "Issue detected"),
            "severity": map_severity(extra.get("severity")),
            "confidence": "medium",
            "category": "security",
            "description": extra.get("message", ""),
            "file_path": os.path.basename(item.get("path")) if item.get("path") else None,
            "line_start": item.get("start", {}).get("line"),
            "line_end": item.get("end", {}).get("line"),
            "snippet": None,
            "recommendation": None,
            "raw": item,
        })

    return {"findings": findings, "error": None}