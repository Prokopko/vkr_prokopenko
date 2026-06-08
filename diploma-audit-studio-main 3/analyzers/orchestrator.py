import os
import tempfile
from typing import Any

from analyzers.llm_runner import run_llm_review
from analyzers.mythril_runner import run_mythril
from analyzers.normalizer import aggregate_summary, deduplicate_findings
from analyzers.semgrep_runner import run_semgrep
from analyzers.slither_runner import run_slither


def run_contract_analysis(
    address: str,
    network: str,
    source_code: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tools_used: list[str] = []
    tool_errors: list[dict[str, str]] = []
    llm_summary = None

    with tempfile.TemporaryDirectory() as tmpdir:
        contract_path = os.path.join(tmpdir, "Contract.sol")
        with open(contract_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        if options.get("slither"):
            result = run_slither(contract_path)
            tools_used.append("slither")
            findings.extend(result.get("findings", []))
            if result.get("error"):
                tool_errors.append({"tool": "slither", "error": result["error"]})

        if options.get("mythril"):
            result = run_mythril(contract_path)
            tools_used.append("mythril")
            findings.extend(result.get("findings", []))
            if result.get("error"):
                tool_errors.append({"tool": "mythril", "error": result["error"]})

        if options.get("semgrep"):
            result = run_semgrep(contract_path)
            tools_used.append("semgrep")
            findings.extend(result.get("findings", []))
            if result.get("error"):
                tool_errors.append({"tool": "semgrep", "error": result["error"]})

        if options.get("llm"):
            result = run_llm_review(
                contract_path=contract_path,
                source_code=source_code,
                address=address,
                network=network,
            )
            tools_used.append("llm")
            findings.extend(result.get("findings", []))
            llm_summary = result.get("llm_summary")
            if result.get("error"):
                tool_errors.append({"tool": "llm", "error": result["error"]})

    findings = deduplicate_findings(findings)
    summary = aggregate_summary(findings)

    return {
        "status": "success" if not tool_errors else "partial_success",
        "mode": "local-analyzer",
        "llm_summary": llm_summary,
        "address": address,
        "network": network,
        "summary": (
            f"Найдено {summary['total_findings']} проблем. "
            f"Risk score: {summary['risk_score']}. "
            f"Trust flag: {summary['trust_flag']}."
        ),
        "tools_used": tools_used,
        "findings": findings,
        "severity_counts": summary["severity_counts"],
        "risk_score": summary["risk_score"],
        "trust_flag": summary["trust_flag"],
        "tool_errors": tool_errors,
    }