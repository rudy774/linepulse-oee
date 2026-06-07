from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


VALID_STATES = {"running", "downtime", "planned_stop", "idle", "changeover"}


@dataclass(frozen=True)
class Event:
    asset: str
    start: datetime
    end: datetime
    state: str
    reason: str = ""
    good_count: int = 0
    scrap_count: int = 0
    ideal_cycle_seconds: float | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    @property
    def total_count(self) -> int:
        return self.good_count + self.scrap_count


@dataclass
class AssetMetrics:
    asset: str
    planned_seconds: float = 0.0
    runtime_seconds: float = 0.0
    downtime_seconds: float = 0.0
    speed_loss_seconds: float = 0.0
    quality_loss_seconds: float = 0.0
    good_count: int = 0
    scrap_count: int = 0
    downtime_by_reason: dict[str, float] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        return self.good_count + self.scrap_count

    @property
    def availability(self) -> float:
        return safe_ratio(self.runtime_seconds, self.planned_seconds)

    @property
    def performance(self) -> float:
        productive_seconds = max(0.0, self.runtime_seconds - self.speed_loss_seconds)
        return safe_ratio(productive_seconds, self.runtime_seconds)

    @property
    def quality(self) -> float:
        return safe_ratio(self.good_count, self.total_count)

    @property
    def oee(self) -> float:
        return self.availability * self.performance * self.quality

    @property
    def lost_seconds(self) -> float:
        return self.downtime_seconds + self.speed_loss_seconds + self.quality_loss_seconds

    def as_dict(self) -> dict[str, object]:
        return {
            "asset": self.asset,
            "planned_seconds": round(self.planned_seconds, 3),
            "runtime_seconds": round(self.runtime_seconds, 3),
            "downtime_seconds": round(self.downtime_seconds, 3),
            "speed_loss_seconds": round(self.speed_loss_seconds, 3),
            "quality_loss_seconds": round(self.quality_loss_seconds, 3),
            "lost_seconds": round(self.lost_seconds, 3),
            "good_count": self.good_count,
            "scrap_count": self.scrap_count,
            "total_count": self.total_count,
            "availability": round(self.availability, 6),
            "performance": round(self.performance, 6),
            "quality": round(self.quality, 6),
            "oee": round(self.oee, 6),
            "downtime_by_reason": {
                reason: round(seconds, 3)
                for reason, seconds in sorted(
                    self.downtime_by_reason.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            },
        }


@dataclass
class PlantReport:
    assets: list[AssetMetrics]
    warnings: list[str] = field(default_factory=list)

    @property
    def bottlenecks(self) -> list[AssetMetrics]:
        return sorted(self.assets, key=lambda asset: asset.lost_seconds, reverse=True)

    def as_dict(self) -> dict[str, object]:
        return {
            "assets": [asset.as_dict() for asset in self.assets],
            "bottlenecks": [
                {"asset": asset.asset, "lost_seconds": round(asset.lost_seconds, 3)}
                for asset in self.bottlenecks
            ],
            "warnings": self.warnings,
        }


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator

