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


@dataclass(frozen=True)
class DowntimeParetoItem:
    reason: str
    seconds: float
    cumulative_seconds: float
    percent_of_downtime: float
    cumulative_percent: float
    assets: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "seconds": round(self.seconds, 3),
            "cumulative_seconds": round(self.cumulative_seconds, 3),
            "percent_of_downtime": round(self.percent_of_downtime, 6),
            "cumulative_percent": round(self.cumulative_percent, 6),
            "assets": list(self.assets),
        }


@dataclass(frozen=True)
class ReportRecommendation:
    priority: str
    category: str
    title: str
    message: str
    evidence: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "priority": self.priority,
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "evidence": list(self.evidence),
            "next_steps": list(self.next_steps),
        }


@dataclass
class PlantReport:
    assets: list[AssetMetrics]
    warnings: list[str] = field(default_factory=list)

    @property
    def bottlenecks(self) -> list[AssetMetrics]:
        return sorted(self.assets, key=lambda asset: asset.lost_seconds, reverse=True)

    @property
    def downtime_pareto(self) -> list[DowntimeParetoItem]:
        totals: dict[str, float] = {}
        assets_by_reason: dict[str, set[str]] = {}
        for asset in self.assets:
            for reason, seconds in asset.downtime_by_reason.items():
                totals[reason] = totals.get(reason, 0.0) + seconds
                assets_by_reason.setdefault(reason, set()).add(asset.asset)

        total_downtime = sum(totals.values())
        cumulative = 0.0
        items: list[DowntimeParetoItem] = []
        for reason, seconds in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
            cumulative += seconds
            items.append(
                DowntimeParetoItem(
                    reason=reason,
                    seconds=seconds,
                    cumulative_seconds=cumulative,
                    percent_of_downtime=safe_ratio(seconds, total_downtime),
                    cumulative_percent=safe_ratio(cumulative, total_downtime),
                    assets=tuple(sorted(assets_by_reason[reason])),
                )
            )
        return items

    @property
    def recommendations(self) -> list[ReportRecommendation]:
        return build_recommendations(self)

    def as_dict(self) -> dict[str, object]:
        return {
            "assets": [asset.as_dict() for asset in self.assets],
            "downtime_pareto": [item.as_dict() for item in self.downtime_pareto],
            "bottlenecks": [
                {"asset": asset.asset, "lost_seconds": round(asset.lost_seconds, 3)}
                for asset in self.bottlenecks
            ],
            "recommendations": [
                recommendation.as_dict() for recommendation in self.recommendations
            ],
            "warnings": self.warnings,
        }


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def build_recommendations(report: PlantReport) -> list[ReportRecommendation]:
    recommendations: list[ReportRecommendation] = []

    if report.warnings:
        recommendations.append(
            ReportRecommendation(
                priority="high",
                category="data-quality",
                title="Review data quality before acting",
                message=(
                    f"The report has {len(report.warnings)} warning(s). Resolve obvious "
                    "event-history, reason-code, or coverage issues before comparing assets."
                ),
                evidence=tuple(report.warnings[:3]),
                next_steps=(
                    "Run `linepulse validate` on the source CSV.",
                    "Fix missing reasons, overlapping intervals, and count/state mismatches first.",
                    "Re-run the report after the source data is corrected.",
                ),
            )
        )

    lost_assets = [asset for asset in report.bottlenecks if asset.lost_seconds > 0]
    total_lost_seconds = sum(asset.lost_seconds for asset in report.assets)
    if lost_assets:
        top_asset = lost_assets[0]
        top_asset_share = safe_ratio(top_asset.lost_seconds, total_lost_seconds)
        top_reason, top_reason_seconds = _largest_reason(top_asset.downtime_by_reason)
        evidence = [
            (
                f"{top_asset.asset} has {_hours(top_asset.lost_seconds)} lost hours "
                f"({_percent(top_asset_share)} of plant loss)."
            ),
            (
                f"OEE {_percent(top_asset.oee)}, availability {_percent(top_asset.availability)}, "
                f"performance {_percent(top_asset.performance)}, quality {_percent(top_asset.quality)}."
            ),
        ]
        if top_reason:
            evidence.append(
                f"Top downtime on this asset is {top_reason!r} at {_minutes(top_reason_seconds)} minutes."
            )

        recommendations.append(
            ReportRecommendation(
                priority="high" if top_asset_share >= 0.5 else "medium",
                category="constraint",
                title=f"Start with {top_asset.asset}",
                message=(
                    f"{top_asset.asset} is the top constraint in this report by lost production time."
                ),
                evidence=tuple(evidence),
                next_steps=(
                    "Review the raw event rows for this asset over the report window.",
                    "Confirm the shift, run, product, and planned-stop boundary used for this comparison.",
                    "Ask what action would reduce the largest loss bucket on this asset this week.",
                ),
            )
        )

        loss_component, loss_seconds = _dominant_loss_component(top_asset)
        if loss_component == "performance" and loss_seconds > 0:
            recommendations.append(
                ReportRecommendation(
                    priority="medium",
                    category="performance",
                    title=f"Validate rate and minor-stop assumptions on {top_asset.asset}",
                    message=(
                        "Performance loss is the largest calculated loss component on the top asset."
                    ),
                    evidence=(
                        f"Estimated speed loss is {_hours(loss_seconds)} lost hours.",
                        f"Runtime is {_hours(top_asset.runtime_seconds)} hours.",
                    ),
                    next_steps=(
                        "Confirm the ideal cycle time is governed and current for the product being run.",
                        "Look for minor stops or slow-cycle intervals that are hidden inside running time.",
                        "Split future reports by product or run if different rates share the same asset.",
                    ),
                )
            )
        elif loss_component == "quality" and loss_seconds > 0:
            recommendations.append(
                ReportRecommendation(
                    priority="medium",
                    category="quality",
                    title=f"Classify scrap on {top_asset.asset}",
                    message=(
                        "Quality loss is the largest calculated loss component on the top asset."
                    ),
                    evidence=(
                        f"Estimated quality loss is {_hours(loss_seconds)} lost hours.",
                        f"Scrap count is {top_asset.scrap_count} of {top_asset.total_count} total units.",
                    ),
                    next_steps=(
                        "Add governed defect or scrap reasons when the source system can provide them.",
                        "Compare scrap by run, product, shift, material, and inspection point.",
                        "Do not treat the quality percentage as root cause without classification evidence.",
                    ),
                )
            )

    if report.downtime_pareto:
        item = report.downtime_pareto[0]
        if item.reason == "unclassified calendar gap":
            recommendations.append(
                ReportRecommendation(
                    priority="high",
                    category="coverage",
                    title="Close event coverage gaps",
                    message=(
                        "Calendar-planned time is not fully covered by event rows, so lost time is "
                        "being attributed to an unclassified gap."
                    ),
                    evidence=(
                        f"Unclassified gap contributes {_hours(item.seconds)} lost hours.",
                        f"That is {_percent(item.percent_of_downtime)} of downtime.",
                    ),
                    next_steps=(
                        "Check whether source exports omit idle, no-order, or communication-loss intervals.",
                        "Add explicit event rows or adjust the calendar boundary for the intended report window.",
                    ),
                )
            )
        else:
            priority = "high" if item.percent_of_downtime >= 0.4 else "medium"
            recommendations.append(
                ReportRecommendation(
                    priority=priority,
                    category="downtime",
                    title=f"Attack {item.reason} first",
                    message=(
                        f"{item.reason!r} is the largest named downtime bucket across "
                        f"{len(item.assets)} affected asset(s)."
                    ),
                    evidence=(
                        f"{_hours(item.seconds)} lost hours.",
                        f"{_percent(item.percent_of_downtime)} of total downtime.",
                        f"Affected assets: {', '.join(item.assets)}.",
                    ),
                    next_steps=(
                        "Confirm reason-code aliases are normalized before comparing teams or assets.",
                        "Separate planned, unplanned, operator-selected, and machine-generated causes if needed.",
                        "Pair the Pareto result with maintenance notes, operator comments, or process history.",
                    ),
                )
            )

    assets_missing_counts = [
        asset.asset for asset in report.assets if asset.runtime_seconds > 0 and asset.total_count == 0
    ]
    if assets_missing_counts:
        recommendations.append(
            ReportRecommendation(
                priority="medium",
                category="counting",
                title="Add production counts to running intervals",
                message=(
                    "Some assets have running time but no good or scrap counts, which limits "
                    "quality and performance interpretation."
                ),
                evidence=(f"Assets missing counts: {', '.join(assets_missing_counts)}.",),
                next_steps=(
                    "Add good and scrap interval totals when available.",
                    "If the source has absolute counters, convert them to interval deltas before analysis.",
                    "Flag counter resets or rollovers instead of treating them as negative production.",
                ),
            )
        )

    if not recommendations:
        recommendations.append(
            ReportRecommendation(
                priority="low",
                category="next-data",
                title="Add more operating context",
                message=(
                    "This report does not show a clear loss driver yet. Add richer production "
                    "context before using it for improvement prioritization."
                ),
                evidence=("No downtime, speed loss, quality loss, or data-quality warning was calculated.",),
                next_steps=(
                    "Add a shift calendar when the report needs scheduled-time boundaries.",
                    "Add reason maps before comparing downtime categories across sources.",
                    "Add run, product, or work-order context when the source system can provide it.",
                ),
            )
        )

    return recommendations


def _largest_reason(reasons: dict[str, float]) -> tuple[str, float]:
    if not reasons:
        return "", 0.0
    return max(reasons.items(), key=lambda item: (item[1], item[0]))


def _dominant_loss_component(asset: AssetMetrics) -> tuple[str, float]:
    components = [
        ("downtime", asset.downtime_seconds),
        ("performance", asset.speed_loss_seconds),
        ("quality", asset.quality_loss_seconds),
    ]
    return max(components, key=lambda item: (item[1], item[0]))


def _hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f}"


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.0f}"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"
