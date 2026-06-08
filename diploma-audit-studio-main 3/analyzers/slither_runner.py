import json
import os
import re
import shutil
import subprocess
from typing import Any

from analyzers.normalizer import IGNORED_SLITHER_RULES, classify_slither_rule, map_severity


def _cleanup_slither_text(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\.\./\.\./\.\./\.\./var/folders/[^ )]+/Contract\.sol', 'Contract.sol', text)
    text = re.sub(r'/var/folders/[^ )]+/Contract\.sol', 'Contract.sol', text)
    return text


def _detect_pragma(contract_path: str) -> str | None:
    """Extract the first pragma version from the source file."""
    try:
        with open(contract_path, encoding="utf-8") as f:
            source = f.read(4096)
        m = re.search(r"pragma\s+solidity\s+[\^~>=<]*\s*([\d]+\.[\d]+)", source)
        return m.group(1) if m else None
    except Exception:
        return None


def _pick_solc(pragma_version: str | None) -> str | None:
    """Return the best available solc binary for the detected pragma version.

    Priority when pragma_version is known:
      1. py-solc-x — version-matched binary in ~/.solcx/
      2. SOLC_BIN env override (version-agnostic fallback)
      3. Homebrew / PATH

    When pragma_version is unknown:
      1. SOLC_BIN env override
      2. Homebrew / PATH
    """
    # 1. Try py-solc-x for precise version matching (highest priority when
    #    we know the required version)
    if pragma_version:
        try:
            from solcx import get_installed_solc_versions, install_solc, get_solcx_install_folder

            major_minor = ".".join(pragma_version.split(".")[:2])
            installed = get_installed_solc_versions()

            # find best installed version with same major.minor
            candidates = [
                v for v in installed
                if str(v).startswith(major_minor + ".")
            ]
            if not candidates:
                # install the latest patch for this major.minor
                try:
                    install_solc(pragma_version)
                    candidates = [v for v in get_installed_solc_versions()
                                  if str(v).startswith(major_minor + ".")]
                except Exception:
                    pass

            if candidates:
                best = max(candidates)
                solcx_dir = get_solcx_install_folder()
                solc_path = os.path.join(solcx_dir, f"solc-v{best}")
                if os.path.isfile(solc_path):
                    return solc_path
        except ImportError:
            pass

    # 2. Explicit override from .env (used when solcx has no matching version)
    env_bin = os.getenv("SOLC_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin

    # 3. Fallback: Homebrew / PATH
    for candidate in ["/opt/homebrew/bin/solc", shutil.which("solc")]:
        if candidate and os.path.isfile(candidate):
            return candidate

    return None


def run_slither(contract_path: str) -> dict[str, Any]:
    if shutil.which("slither") is None:
        return {"findings": [], "error": "Команда 'slither' не найдена в PATH."}

    pragma = _detect_pragma(contract_path)
    solc_bin = _pick_solc(pragma)

    cmd = ["slither", contract_path, "--json", "-"]
    if solc_bin:
        cmd += ["--solc", solc_bin]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except Exception as exc:
        return {"findings": [], "error": f"Ошибка запуска Slither: {exc}"}

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if not stdout:
        return {
            "findings": [],
            "error": (
                f"Slither не вернул JSON. pragma={pragma} solc={solc_bin} "
                f"rc={result.returncode} stderr={stderr[:400]}"
            ),
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "findings": [],
            "error": f"Не удалось распарсить JSON от Slither. stdout={stdout[:400]}",
        }

    findings = []
    for item in data.get("results", {}).get("detectors", []):
        rule_id = item.get("check", "unknown")
        if rule_id in IGNORED_SLITHER_RULES:
            continue

        elements = item.get("elements", [])
        line_start = line_end = file_path = snippet = None
        if elements:
            sm = elements[0].get("source_mapping", {})
            lines = sm.get("lines") or []
            if lines:
                line_start, line_end = min(lines), max(lines)
            fp = sm.get("filename_relative") or sm.get("filename_absolute")
            file_path = os.path.basename(fp) if fp else None
            snippet = elements[0].get("name")

        findings.append({
            "tool":        "slither",
            "rule_id":     rule_id,
            "title":       rule_id,
            "severity":    map_severity(item.get("impact")),
            "confidence":  (item.get("confidence") or "medium").lower(),
            "category":    classify_slither_rule(rule_id),
            "description": _cleanup_slither_text(item.get("description", "")),
            "file_path":   file_path,
            "line_start":  line_start,
            "line_end":    line_end,
            "snippet":     snippet,
            "recommendation": item.get("recommendation"),
            "raw":         item,
        })

    return {"findings": findings, "error": None}
