from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def lowest(cls, *values: Confidence | None) -> Confidence:
        order = {cls.HIGH: 0, cls.MEDIUM: 1, cls.LOW: 2}
        present = [value for value in values if value is not None]
        if not present:
            return cls.LOW
        return max(present, key=lambda value: order[value])


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    severity: str = "warning"  # info | warning | risk


@dataclass(frozen=True, slots=True)
class RangeEstimate:
    """A min/likely/max range. Units are documented by the caller.

    Exact values use min == likely == max. We do not fabricate spread.
    """

    min: float
    likely: float
    max: float

    def __post_init__(self) -> None:
        if self.min > self.likely or self.likely > self.max:
            raise ValueError("range must satisfy min <= likely <= max")
