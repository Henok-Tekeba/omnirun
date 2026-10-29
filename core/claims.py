from __future__ import annotations

from enum import StrEnum


class ClaimStatus(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Verdict(StrEnum):
    GO = "GO"
    OPTIMIZE = "OPTIMIZE"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class SpeedClass(StrEnum):
    INTERACTIVE = "interactive"
    USABLE = "usable"
    SLOW = "slow"
    UNKNOWN = "unknown"
