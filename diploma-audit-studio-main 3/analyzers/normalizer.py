from collections import Counter
from typing import Any


IGNORED_SLITHER_RULES = {
    "naming-convention",
}

QUALITY_SLITHER_RULES = {
    "constable-states",
    "external-function",
}


def map_severity(value: str | None) -> str:
    if not value:
        return "info"

    value = str(value).strip().lower()

    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "informational": "info",
        "info": "info",
        "optimization": "low",
        "warning": "medium",
        "error": "high",
        "unknown": "info",
    }
    return mapping.get(value, "info")


def classify_slither_rule(rule_id: str) -> str:
    if rule_id in QUALITY_SLITHER_RULES:
        return "quality"
    return "security"


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []

    for item in findings:
        key = (
            item.get("tool"),
            item.get("rule_id"),
            item.get("line_start"),
            item.get("description"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


def aggregate_summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    severities = Counter(item.get("severity", "info") for item in findings)

    security_findings = [
        item for item in findings
        if item.get("category") != "quality"
    ]
    security_severities = Counter(item.get("severity", "info") for item in security_findings)

    score = (
        security_severities.get("critical", 0) * 40
        + security_severities.get("high", 0) * 20
        + security_severities.get("medium", 0) * 10
        + security_severities.get("low", 0) * 3
    )
    score = min(score, 100)

    trust_flag = 1 if score < 20 else 0

    return {
        "total_findings": len(findings),
        "severity_counts": dict(severities),
        "security_severity_counts": dict(security_severities),
        "risk_score": score,
        "trust_flag": trust_flag,
    }