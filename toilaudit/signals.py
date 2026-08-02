"""Detect toil signals in a CI run history.

Each signal is a moment where a human had to touch the pipeline (or wait on
it). The per-signal engineer-minute estimates are deliberately conservative
and configurable — the audit's credibility depends on defensible numbers.

Signals:
- RERUN            run_attempt > 1: someone pressed "re-run" and waited.
- FLAKY_RECOVERY   same head_sha fails then succeeds with no new commit:
                   the canonical flaky-test babysitting loop.
- MANUAL_DISPATCH  workflow_dispatch on a scheduled/CI workflow: a human is
                   the scheduler.
- QUEUE_STALL      run sat queued longer than the threshold; engineers
                   context-switch away and back.
- FAILED_RUN       every failure costs triage time even when the fix is real.
"""

from dataclasses import dataclass

from .ingest import Run

DEFAULT_MINUTES = {
    "RERUN": 10.0,            # notice, re-run, re-check
    "FLAKY_RECOVERY": 15.0,   # diagnose "is it me or the tests?"
    "MANUAL_DISPATCH": 5.0,   # remember + trigger + verify
    "QUEUE_STALL": 6.0,       # two context switches
    "FAILED_RUN": 8.0,        # read logs, decide
}
QUEUE_STALL_SECONDS = 900  # 15 min


@dataclass(frozen=True)
class Signal:
    kind: str
    run: Run
    detail: str
    engineer_minutes: float
    wasted_compute_seconds: float = 0.0


def detect_signals(
    runs: list[Run],
    minutes: dict[str, float] | None = None,
    queue_stall_seconds: float = QUEUE_STALL_SECONDS,
) -> list[Signal]:
    minutes = {**DEFAULT_MINUTES, **(minutes or {})}
    signals: list[Signal] = []
    seen_failures: dict[tuple[str, str], Run] = {}  # (workflow, sha) -> failed run

    for run in runs:  # runs are sorted oldest-first by load_runs()
        key = (run.workflow, run.head_sha)

        if run.run_attempt > 1:
            signals.append(Signal(
                "RERUN", run,
                f"attempt {run.run_attempt} of '{run.workflow}'",
                minutes["RERUN"],
                wasted_compute_seconds=run.duration_seconds * (run.run_attempt - 1),
            ))

        if run.conclusion == "failure":
            seen_failures[key] = run
            signals.append(Signal(
                "FAILED_RUN", run,
                f"'{run.workflow}' failed on {run.head_sha[:7]}",
                minutes["FAILED_RUN"],
                wasted_compute_seconds=run.duration_seconds,
            ))
        elif run.conclusion == "success" and key in seen_failures:
            failed = seen_failures.pop(key)
            if run.run_id != failed.run_id:
                signals.append(Signal(
                    "FLAKY_RECOVERY", run,
                    f"'{run.workflow}' red->green on same sha {run.head_sha[:7]}",
                    minutes["FLAKY_RECOVERY"],
                ))

        if run.event == "workflow_dispatch":
            signals.append(Signal(
                "MANUAL_DISPATCH", run,
                f"'{run.workflow}' triggered by hand",
                minutes["MANUAL_DISPATCH"],
            ))

        if run.queue_seconds > queue_stall_seconds:
            signals.append(Signal(
                "QUEUE_STALL", run,
                f"'{run.workflow}' queued {run.queue_seconds / 60:.0f} min",
                minutes["QUEUE_STALL"],
            ))

    return signals
