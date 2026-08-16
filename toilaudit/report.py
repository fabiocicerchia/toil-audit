"""Render the audit as a Markdown report."""

from calendar import monthrange
from datetime import datetime, timezone
from itertools import pairwise

from .attribute import summarise
from .costing import CostSummary
from .ingest import Run
from .signals import Signal

_KIND_LABELS = {
    "RERUN": "Manual re-runs",
    "FLAKY_RECOVERY": "Flaky red→green loops",
    "MANUAL_DISPATCH": "Manual dispatches",
    "QUEUE_STALL": "Queue stalls (>15 min)",
    "FAILED_RUN": "Failure triage",
    "ACTION_REQUIRED": "Runs parked for approval",
}


HOURS_PER_ENGINEER_MONTH = 130.0  # ~1560 productive h/year

# Push timing bounds how long a human can possibly have been at the keyboard:
# consecutive pushes closer than the gap are one sitting, and each sitting gets
# a lead-in for the work that happened before its first push. Deliberately
# generous — it is a ceiling to check the bill against, not an estimate of work.
SESSION_GAP_MINUTES = 30.0
SESSION_LEAD_IN_MINUTES = 30.0


def _eur(v: float) -> str:
    return f"€{v:,.2f}"


def keyboard_hours(runs: list[Run]) -> float:
    """Upper bound on human time at the keyboard, from push timing alone.

    Every hour this report bills has to fit inside this. If it doesn't, the
    per-signal estimates are wrong — say so instead of handing over the bill.
    """
    stamps = sorted({r.created_at for r in runs if r.is_human})
    if not stamps:
        return 0.0
    total, start, prev = 0.0, stamps[0], stamps[0]
    for t in stamps[1:]:
        if (t - prev).total_seconds() > SESSION_GAP_MINUTES * 60:
            total += (prev - start).total_seconds() / 3600
            start = t
        prev = t
    total += (prev - start).total_seconds() / 3600
    sittings = 1 + sum(
        1
        for a, b in pairwise(stamps)
        if (b - a).total_seconds() > SESSION_GAP_MINUTES * 60
    )
    return total + sittings * SESSION_LEAD_IN_MINUTES / 60


def _complete_months(
    by_month: dict[str, float], runs: list[Run]
) -> list[tuple[str, float]]:
    """Months the export covers end to end — the partial edges aren't rates."""
    keys = list(by_month)
    if not runs or not keys:
        return []
    first, last = runs[0].created_at, runs[-1].created_at
    if first.day > 1 and keys[0] == f"{first:%Y-%m}":
        keys = keys[1:]
    if (
        keys
        and last.day < monthrange(last.year, last.month)[1]
        and keys[-1] == f"{last:%Y-%m}"
    ):
        keys = keys[:-1]
    return [(k, by_month[k]) for k in keys]


def build_report(
    runs: list[Run],
    signals: list[Signal],
    summary: CostSummary,
    hourly_rate_eur: float,
    attribution=None,
) -> str:
    if runs:
        period = f"{runs[0].created_at.date()} → {runs[-1].created_at.date()}"
        days = max(1.0, (runs[-1].created_at - runs[0].created_at).days)
    else:
        period, days = "n/a", 1.0
    months = days / 30.44
    repos = {r.repo for r in runs if r.repo}

    scope = f"{len(runs)} completed CI runs"
    if repos:
        scope += f" across {len(repos)} repos"

    # A 14-month average hides a burst. Headline the last *complete* calendar
    # month — the partial current month would read as a collapse in toil.
    complete = _complete_months(summary.by_month, runs)
    sanity: list[str] = []
    if complete:
        recent_month, recent_eur = complete[-1]
        in_month = [s for s in signals if f"{s.run.created_at:%Y-%m}" == recent_month]
        billed_h = sum(s.engineer_minutes for s in in_month) / 60
        ceiling_h = keyboard_hours(
            [r for r in runs if f"{r.created_at:%Y-%m}" == recent_month]
        )
        headline = (
            f"## Bottom line: **{_eur(recent_eur)} in {recent_month}** "
            f"(last full month)"
        )
        context = (
            f"{_eur(summary.total_eur)} total across {months:.1f} months, "
            f"but the load is not flat — see the trend. At {recent_month}'s "
            f"rate that is {billed_h:.0f} engineer-hours a month, "
            f"{billed_h / HOURS_PER_ENGINEER_MONTH:.0%} of one engineer."
        )
        if ceiling_h:
            share = billed_h / ceiling_h
            sanity = [
                "",
                f"> **Sanity check** — push timing puts at most **{ceiling_h:.0f} h** "
                f"of human keyboard time in {recent_month} (all work, not just CI). "
                f"This report bills {billed_h:.0f} h of toil against it: "
                f"**{share:.0%}** of everything done that month."
                + (
                    ""
                    if share <= 0.5
                    else " That is too high to defend in a room — lower the per-signal"
                    " minutes before you present it."
                ),
            ]
    else:
        headline = (
            f"## Bottom line: **{_eur(summary.total_eur / months)} per month** of toil"
        )
        context = (
            f"{_eur(summary.total_eur)} total over {months:.1f} months "
            f"({summary.total_engineer_minutes / 60:.1f} engineer-hours)."
        )

    lines = [
        "# Toil audit",
        "",
        f"_{scope}, {period}. Engineer rate {_eur(hourly_rate_eur)}/h (loaded)._",
        "",
        headline,
        "",
        context,
        *sanity,
        "",
        "| Toil source | Events | Charged | Engineer time | Engineer € | Compute waste | Compute € |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for line in summary.lines:
        charged = "—" if line.charged_count == line.count else f"{line.charged_count}"
        lines.append(
            f"| {_KIND_LABELS.get(line.kind, line.kind)} | {line.count} | {charged} "
            f"| {line.engineer_minutes:.0f} min | {_eur(line.engineer_cost_eur)} "
            f"| {line.compute_minutes:.0f} min | {_eur(line.compute_cost_eur)} |"
        )
    lines += [
        "",
        (
            "_Charged: failure triage is billed once per broken commit, not once per"
            " red workflow — one bad push turns several workflows red and a human"
            " reads the logs once._"
        ),
    ]

    if summary.by_month:
        peak = max(summary.by_month.values()) or 1.0
        full = {m for m, _ in complete}
        lines += ["", "## Monthly trend", ""]
        for month, eur in summary.by_month.items():
            bar = "█" * max(1, round(28 * eur / peak))
            tail = "" if month in full else "  _(partial month)_"
            lines.append(f"- `{month}` {bar} {_eur(eur)}{tail}")

    shared = [t for t in summary.by_template if t.repos > 1][:8]
    if shared:
        lines += [
            "",
            "## Costliest workflow files",
            "",
            "_The same file copied into every repo: fix it once, fix it everywhere._",
            "",
            "| Workflow file | Repos | Total € |",
            "|---|---:|---:|",
        ]
        for t in shared:
            lines.append(f"| `{t.path}` | {t.repos} | {_eur(t.total_eur)} |")

    if attribution is not None:
        # Placed before the workflow rankings: a named test file is the most
        # actionable line in the report, and it partitions a cost already
        # counted above rather than adding to it.
        lines += [""] + summarise(attribution)

    lines += ["", "## Costliest workflows", ""]
    for wf, eur in list(summary.by_workflow.items())[:8]:
        lines.append(f"- **{wf}** — {_eur(eur)}")

    worst = sorted(signals, key=lambda s: s.engineer_minutes, reverse=True)[:10]
    if worst:
        lines += ["", "## Sample incidents", ""]
        for s in worst:
            when = s.run.created_at.strftime("%Y-%m-%d")
            lines.append(f"- `{when}` [{s.kind}] {s.detail}")

    lines += [
        "",
        "---",
        (
            f"_Generated {datetime.now(tz=timezone.utc):%Y-%m-%d %H:%M} UTC."
            " Assumptions are configurable; see README for the methodology._"
        ),
    ]
    return "\n".join(lines)
