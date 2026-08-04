"""Turn toil signals into euros.

Two cost components, reported separately because they land in different
budgets:

- engineer cost  = engineer-minutes x loaded hourly rate / 60
- compute waste  = wasted runner-minutes x per-minute runner price
                   (default: GitHub-hosted ubuntu 2-core, EUR)
"""

from collections import defaultdict
from dataclasses import dataclass

from .signals import Signal

DEFAULT_HOURLY_RATE_EUR = 75.0
DEFAULT_RUNNER_EUR_PER_MINUTE = 0.0074  # $0.008 converted, rounded


@dataclass(frozen=True)
class CostLine:
    kind: str
    count: int            # events detected
    charged_count: int    # events that cost a human — see FAILED_RUN dedup
    engineer_minutes: float
    engineer_cost_eur: float
    compute_minutes: float
    compute_cost_eur: float

    @property
    def total_eur(self) -> float:
        return self.engineer_cost_eur + self.compute_cost_eur


@dataclass(frozen=True)
class CostSummary:
    lines: list[CostLine]              # per signal kind, largest first
    by_workflow: dict[str, float]      # workflow -> total EUR
    total_engineer_minutes: float
    total_eur: float


def summarize_costs(
    signals: list[Signal],
    hourly_rate_eur: float = DEFAULT_HOURLY_RATE_EUR,
    runner_eur_per_minute: float = DEFAULT_RUNNER_EUR_PER_MINUTE,
) -> CostSummary:
    per_kind: dict[str, list[Signal]] = defaultdict(list)
    by_workflow: dict[str, float] = defaultdict(float)

    for s in signals:
        per_kind[s.kind].append(s)

    lines = []
    for kind, items in per_kind.items():
        eng_min = sum(s.engineer_minutes for s in items)
        comp_min = sum(s.wasted_compute_seconds for s in items) / 60
        line = CostLine(
            kind=kind,
            count=len(items),
            charged_count=sum(1 for s in items if s.engineer_minutes),
            engineer_minutes=round(eng_min, 1),
            engineer_cost_eur=round(eng_min / 60 * hourly_rate_eur, 2),
            compute_minutes=round(comp_min, 1),
            compute_cost_eur=round(comp_min * runner_eur_per_minute, 2),
        )
        lines.append(line)

    for s in signals:
        by_workflow[s.run.workflow] += (
            s.engineer_minutes / 60 * hourly_rate_eur
            + s.wasted_compute_seconds / 60 * runner_eur_per_minute
        )

    lines.sort(key=lambda l: l.total_eur, reverse=True)
    return CostSummary(
        lines=lines,
        by_workflow={k: round(v, 2) for k, v in
                     sorted(by_workflow.items(), key=lambda kv: kv[1], reverse=True)},
        total_engineer_minutes=round(sum(l.engineer_minutes for l in lines), 1),
        total_eur=round(sum(l.total_eur for l in lines), 2),
    )
