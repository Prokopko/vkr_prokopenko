from __future__ import annotations

from typing import Any

from analyzers.orchestrator import run_contract_analysis


def find_cached_result(address: str, network: str) -> dict | None:
    """Public helper — check NocoDB for an existing run before fetching source."""
    return _find_cached(address, network)


def run_scan(
    address: str,
    network: str,
    options: dict[str, Any],
    save_to_nocodb: bool = False,
    analyst: str = "",
) -> dict[str, Any]:
    source_code = options.get("source_code") or options.get("contract_code")

    if not source_code:
        return {
            "status": "failed",
            "mode": "local-analyzer",
            "address": address,
            "network": network,
            "summary": "Исходный код контракта не передан.",
            "findings": [],
            "tools_used": [],
            "error": "No source code provided",
        }

    # ── run analysis ───────────────────────────────────────────────────────────
    scan_result = run_contract_analysis(
        address=address,
        network=network,
        source_code=source_code,
        options=options,
    )
    scan_result["from_cache"] = False

    # ── persist ────────────────────────────────────────────────────────────────
    if save_to_nocodb:
        scan_result["nocodb"] = _save(
            scan_result=scan_result,
            address=address,
            network=network,
            options=options,
            analyst=analyst,
        )

    return scan_result


# ── internal ───────────────────────────────────────────────────────────────────

def _find_cached(address: str, network: str) -> dict | None:
    try:
        from connectors.nocodb_client import find_cached_run, get_findings_for_run
        row = find_cached_run(address, network)
        if not row:
            return None

        run_id = row.get("Id")
        findings_rows = get_findings_for_run(run_id) if run_id else []

        findings = [
            {
                "tool":           r.get("tool", ""),
                "rule_id":        r.get("rule_id", ""),
                "title":          r.get("title", ""),
                "severity":       r.get("severity_label", "info"),
                "confidence":     r.get("confidence_label", "medium"),
                "category":       r.get("category", "security"),
                "description":    r.get("description", ""),
                "recommendation": r.get("recommendation", ""),
                "file_path":      r.get("file_path", ""),
                "line_start":     r.get("line_start"),
                "line_end":       r.get("line_end"),
            }
            for r in findings_rows
        ]

        return {
            "status":         row.get("status", "success"),
            "mode":           "cache",
            "address":        row.get("address", address),
            "network":        row.get("network", network),
            "summary":        row.get("summary", ""),
            "overall_verdict": row.get("overall_verdict", ""),
            "risk_score":     row.get("risk_score", 0),
            "trust_flag":     row.get("trust_flag", 0),
            "tools_used":     (row.get("tools_used") or "").split(","),
            "findings":       findings,
            "severity_counts": _count_severity(findings),
            "llm_summary": {
                "overall_verdict": row.get("llm_verdict"),
                "risk_score":      row.get("llm_risk_score"),
            } if row.get("llm_verdict") else None,
            "cached_at": row.get("CreatedAt", ""),
        }
    except Exception:
        return None


def _save(
    scan_result: dict[str, Any],
    address: str,
    network: str,
    options: dict[str, Any],
    analyst: str,
) -> dict[str, Any]:
    try:
        from connectors.nocodb_client import insert_scan_run, insert_findings

        llm_summary = scan_result.get("llm_summary") or {}
        etherscan_meta = options.get("etherscan_metadata") or {}

        run_row = {
            "analyst":          analyst or "anonymous",
            "address":          address,
            "network":          network,
            "contract_name":    options.get("contract_name") or address,
            "compiler_version": etherscan_meta.get("compiler_version", ""),
            "source_origin":    _detect_origin(options),
            "status":           scan_result.get("status", "unknown"),
            "overall_verdict":  llm_summary.get("overall_verdict", ""),
            "risk_score":       scan_result.get("risk_score", 0),
            "trust_flag":       scan_result.get("trust_flag", 0),
            "tools_used":       ",".join(scan_result.get("tools_used", [])),
            "summary":          scan_result.get("summary", ""),
            "llm_verdict":      llm_summary.get("overall_verdict", ""),
            "llm_risk_score":   llm_summary.get("risk_score") or 0,
            "source_code":      (options.get("source_code") or "")[:50_000],
        }

        run_id = insert_scan_run(run_row)

        if run_id:
            finding_rows = [
                {
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
                }
                for f in scan_result.get("findings", [])
            ]
            insert_findings(finding_rows)

        return {"saved": True, "message": f"Сохранено в NocoDB (run_id={run_id}).", "run_id": run_id}

    except Exception as exc:
        return {"saved": False, "message": f"Ошибка сохранения: {exc}"}


def _detect_origin(options: dict) -> str:
    if options.get("etherscan_metadata", {}).get("ok"):
        return "etherscan"
    if options.get("uploaded_file"):
        return "upload"
    return "manual"


def _count_severity(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "info")
        counts[s] = counts.get(s, 0) + 1
    return counts