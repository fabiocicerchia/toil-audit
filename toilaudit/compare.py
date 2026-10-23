"""What a fix was worth: toil per month before a named change, and after it.

The boundary is always named by the caller — a date, or the commit the fix
landed in. Inferring it from a step in the series would attribute the drop to
whatever happened to be nearby, which is the one claim this tool should not
make on its own.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from .ingest import Run


@dataclass(frozen=True)
class Comparison:
    boundary: datetime
    boundary_month: str  # split by the change, so in neither window
    before: list[tuple[str, float]]  # complete months, chronological
    after: list[tuple[str, float]]
    fix_cost_eur: float | None  # None: no cost given, so no ROI

    @property
    def comparable(self) -> bool:
        return bool(self.before) and bool(self.after)

    @property
    def before_eur(self) -> float:
        return sum(v for _, v in self.before) / len(self.before)

    @property
    def after_eur(self) -> float:
        return sum(v for _, v in self.after) / len(self.after)

    @property
    def saving_eur(self) -> float:
        """Per month. Negative when toil went up after the change."""
        return self.before_eur - self.after_eur

    @property
    def returned_eur(self) -> float:
        """What the change has returned so far, across the months measured after it."""
        return self.saving_eur * len(self.after)

    @property
    def payback_months(self) -> float | None:
        """Months of the measured saving it takes to cover the fix; None if it never does."""
        if self.fix_cost_eur is None or self.saving_eur <= 0:
            return None
        return self.fix_cost_eur / self.saving_eur


def month_series(by_month: dict[str, float], runs: list[Run]) -> dict[str, float]:
    """Every calendar month the export spans, with zero where nothing was toil.

    `CostSummary.by_month` only has months a signal landed in. A clean month
    after a fix is the result the comparison exists to show, and leaving it
    out of the average would hide exactly that.
    """
    if not runs:
        return {}
    first, last = runs[0].created_at, runs[-1].created_at
    out, year, month = {}, first.year, first.month
    while (year, month) <= (last.year, last.month):
        key = f"{year:04d}-{month:02d}"
        out[key] = by_month.get(key, 0.0)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def resolve_boundary(spec: str, runs: list[Run]) -> datetime:
    """`YYYY-MM-DD`, or a commit sha (or prefix) to the first run built from it.

    Raises ValueError rather than guessing: a sha that matches no run is a
    typo or the wrong export, and a comparison across the wrong boundary
    reads exactly like a real one.
    """
    try:
        return datetime.strptime(spec, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    sha = spec.lower()
    if len(sha) < 7 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError(f"{spec!r} is neither a YYYY-MM-DD date nor a commit sha")
    matches = [r.created_at for r in runs if r.head_sha.lower().startswith(sha)]
    if not matches:
        raise ValueError(f"no run in this export was built from commit {spec}")
    return min(matches)


def compare(
    complete: list[tuple[str, float]],
    boundary: datetime,
    fix_hours: float | None,
    hourly_rate_eur: float,
) -> Comparison:
    """Split the complete months either side of the boundary.

    Takes `report.complete_months` output, not the raw series: a truncated final
    month reads as a saving that did not happen. The month the change landed
    in is split between the two states, so it is in neither window.
    """
    month = f"{boundary:%Y-%m}"
    return Comparison(
        boundary=boundary,
        boundary_month=month,
        before=[(m, v) for m, v in complete if m < month],
        after=[(m, v) for m, v in complete if m > month],
        fix_cost_eur=None if fix_hours is None else fix_hours * hourly_rate_eur,
    )
