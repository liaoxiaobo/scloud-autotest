from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthFinding:
    check: str
    status: str
    actual: Any = None
    expected: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass
class EnvironmentHealthResult:
    env_name: str
    findings: list[HealthFinding] = field(default_factory=list)

    @property
    def failed(self) -> list[HealthFinding]:
        return [finding for finding in self.findings if finding.status == "FAIL"]

    @property
    def warnings(self) -> list[HealthFinding]:
        return [finding for finding in self.findings if finding.status == "WARN"]

    @property
    def unknown(self) -> list[HealthFinding]:
        return [finding for finding in self.findings if finding.status == "UNKNOWN"]

    @property
    def passed(self) -> bool:
        return not self.failed and not self.unknown
