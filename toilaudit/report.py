"""Render the audit as a Markdown report."""

from datetime import datetime

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


def _eur(v: float) -> str:
    return f"€{v:,.2f}"


def build_report(runs: list[Run], signals: list[Signal], summary: CostSummary,
                 hourly_rate_eur: float) -> str:
    if runs:
        period = f"{runs[0].created_at.date()} → {runs[-1].created_at.date()}"
    else:
        period = "n/a"

    lines = [
        "# Toil audit",
        "",
        f"_{len(runs)} completed CI runs, {period}. "
        f"Engineer rate {_eur(hourly_rate_eur)}/h (loaded)._",
        "",
        f"## Bottom line: **{_eur(summary.total_eur)}** of toil "
        f"({summary.total_engineer_minutes / 60:.1f} engineer-hours)",
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
        "_Charged: failure triage is billed once per broken commit, not once per"
        " red workflow — one bad push turns several workflows red and a human"
        " reads the logs once._",
    ]

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
        f"_Generated {datetime.now():%Y-%m-%d %H:%M}. Assumptions are configurable;"
        " see README for the methodology._",
    ]
    return "\n".join(lines)
