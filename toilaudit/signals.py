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
- FAILED_RUN       charged once per broken commit — one bad push turns six
                   workflows red, but a human reads the logs once — and priced
                   from evidence, not from a constant: the interval between the
                   red run and the next push on that branch is how long someone
                   was actually on it. No next push means nobody looked.
                   Repeat failures on the same commit still bill runner time.
"""

from bisect import bisect_right
from dataclasses import dataclass

from .ingest import Run

DEFAULT_MINUTES = {
    "RERUN": 10.0,            # notice, re-run, re-check
    "FLAKY_RECOVERY": 15.0,   # diagnose "is it me or the tests?"
    "MANUAL_DISPATCH": 5.0,   # remember + trigger + verify
    "QUEUE_STALL": 6.0,       # ponytail: two context switches, flat estimate.
                              # Give it the FAILED_RUN treatment if it ever
                              # grows past a rounding error in the total.
    "FAILED_RUN": 8.0,        # read logs, decide — now a *ceiling*, see below
}
QUEUE_STALL_SECONDS = 900  # 15 min

# A red run that is never followed by a push was never triaged — someone saw a
# red badge at most. A fix that lands in seconds was an obvious error, not a
# diagnosis. Both are billed at what the timeline shows, floored here so that
# "you glanced at it" is not free.
GLANCE_MINUTES = 1.0

# One person fixes a shared workflow template once and pushes the same commit
# into every repo that copied it. That is one diagnosis and N applications, not
# N diagnoses — the followers are billed the application only.
FANOUT_REPOS = 3
FANOUT_WINDOW_MINUTES = 30.0
APPLY_MINUTES = 1.0


def _triage_minutes(next_push_minutes: float | None, fixed_by_human: bool,
                    ceiling: float) -> float:
    """What the timeline says this failure cost, capped at the estimate.

    Past the ceiling the interval stops being attention — they went to bed. A
    bot failure that a bot pushed over is nobody's afternoon either: dependabot
    superseding its own branch is not evidence a person read the logs.
    """
    if next_push_minutes is None or not fixed_by_human:
        return GLANCE_MINUTES
    return min(max(next_push_minutes, GLANCE_MINUTES), ceiling)


def _next_push_index(runs: list[Run]) -> dict[tuple[str, str], list[tuple]]:
    """Per (repo, branch): push time, sha and whether a human pushed it."""
    index: dict[tuple[str, str], list[tuple]] = {}
    for run in runs:
        index.setdefault((run.repo, run.branch), []).append(
            (run.created_at.timestamp(), run.head_sha, run.is_human))
    for pushes in index.values():
        pushes.sort()
    return index


def _fanout_followers(runs: list[Run]) -> set[tuple[str, str]]:
    """Broken commits that are the same fix landing in yet another repo.

    Groups failures by commit subject, splits each group where the pushes stop
    being one sitting, and keeps every cluster that hit several repos at once.
    The first commit of such a cluster is the diagnosis; the rest are copies.
    """
    by_title: dict[str, list[Run]] = {}
    seen: set[tuple[str, str]] = set()
    for run in runs:
        if run.conclusion != "failure" or not run.title or run.commit in seen:
            continue
        seen.add(run.commit)
        by_title.setdefault(run.title, []).append(run)

    def followers_of(cluster: list[Run]) -> set[tuple[str, str]]:
        if len({r.repo for r in cluster}) < FANOUT_REPOS:
            return set()
        return {r.commit for r in cluster[1:]}

    followers: set[tuple[str, str]] = set()
    for group in by_title.values():
        group.sort(key=lambda r: r.created_at)
        cluster = [group[0]]
        for run in group[1:]:
            gap = (run.created_at - cluster[-1].created_at).total_seconds() / 60
            if gap > FANOUT_WINDOW_MINUTES:
                followers |= followers_of(cluster)
                cluster = []
            cluster.append(run)
        followers |= followers_of(cluster)
    return followers


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
    triaged: set[tuple[str, str]] = set()           # broken commits already read
    pushes = _next_push_index(runs)
    followers = _fanout_followers(runs)

    def next_push(run: Run) -> tuple[float | None, bool]:
        """Gap to the next *different* commit here, and who pushed it."""
        branch = pushes.get((run.repo, run.branch), [])
        i = bisect_right(branch, (run.created_at.timestamp(), run.head_sha))
        for when, sha, by_human in branch[i:]:
            if sha != run.head_sha:
                return max(0.0, when - run.updated_at.timestamp()) / 60, by_human
        return None, False

    for run in runs:  # runs are sorted oldest-first by load_runs()
        key = (run.label, run.head_sha)

        if run.run_attempt > 1:
            signals.append(Signal(
                "RERUN", run,
                f"attempt {run.run_attempt} of '{run.label}'",
                minutes["RERUN"],
                wasted_compute_seconds=run.duration_seconds * (run.run_attempt - 1),
            ))

        if run.conclusion == "failure":
            seen_failures[key] = run
            first_red = run.commit not in triaged
            triaged.add(run.commit)
            if first_red:
                gap, by_human = next_push(run)
                cost = _triage_minutes(gap, by_human, minutes["FAILED_RUN"])
                why = (" — never fixed, nobody looked" if gap is None
                       else f" — not a human, {run.actor} pushed over it"
                       if not by_human else f" — next push {gap:.0f} min later")
                if run.commit in followers:
                    cost = min(cost, APPLY_MINUTES)
                    why = " — same fix pushed to several repos, diagnosed once"
                detail = f"'{run.label}' failed on {run.head_sha[:7]}{why}"
            else:
                cost, detail = 0.0, (f"'{run.label}' failed on {run.head_sha[:7]}"
                                     " (same commit, already triaged)")
            signals.append(Signal(
                "FAILED_RUN", run, detail, cost,
                wasted_compute_seconds=run.duration_seconds,
            ))
        elif run.conclusion == "success" and key in seen_failures:
            failed = seen_failures.pop(key)
            if run.run_id != failed.run_id:
                signals.append(Signal(
                    "FLAKY_RECOVERY", run,
                    f"'{run.label}' red->green on same sha {run.head_sha[:7]}",
                    minutes["FLAKY_RECOVERY"],
                ))

        if run.event == "workflow_dispatch":
            signals.append(Signal(
                "MANUAL_DISPATCH", run,
                f"'{run.label}' triggered by hand",
                minutes["MANUAL_DISPATCH"],
            ))

        if run.queue_seconds > queue_stall_seconds:
            signals.append(Signal(
                "QUEUE_STALL", run,
                f"'{run.label}' queued {run.queue_seconds / 60:.0f} min",
                minutes["QUEUE_STALL"],
            ))

    return signals
