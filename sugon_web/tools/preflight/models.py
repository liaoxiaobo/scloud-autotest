from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Requirement:
    """A normalized resource requirement."""

    name: str
    value: float
    unit: str = ""
    scale_with_workers: bool = True
    note: str = ""

    def scaled(self, workers: int, safety: float) -> "Requirement":
        factor = workers if self.scale_with_workers else 1
        scaled_value = self.value * factor * safety
        if self.unit in {"count", "cores", "GiB"}:
            scaled_value = math.ceil(scaled_value)
        return Requirement(
            name=self.name,
            value=scaled_value,
            unit=self.unit,
            scale_with_workers=self.scale_with_workers,
            note=self.note,
        )


@dataclass
class EnvironmentResult:
    """Result of checking one environment against requirements."""

    name: str
    passed: bool
    missing: list[str]
