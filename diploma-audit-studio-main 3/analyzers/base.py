from dataclasses import dataclass, field
from typing import Any

@dataclass
class Finding:
    tool: str
    rule_id: str
    title: str
    severity: str
    description: str
    line_start: int | None = None
    line_end: int | None = None
    file_path: str | None = None
    recommendation: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)