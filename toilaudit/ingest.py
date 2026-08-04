"""Load CI runs from a GitHub Actions workflow-runs export.

Input is the JSON you get from:

    gh api 'repos/OWNER/REPO/actions/runs?per_page=100' --paginate > runs.json

Accepts either the raw API shape ({"workflow_runs": [...]}, possibly
concatenated pages) or a plain JSON array of run objects. Only fields the
signal detectors need are kept.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# ponytail: GitHub's per-job wall-clock ceiling. `updated_at` is bumped whenever
# the run *record* changes (log-retention cleanup, annotations), sometimes months
# after the run ended — uncapped, a single stale record reads as 400 days of
# runner time. Raise it if you legitimately run multi-hour pipelines.
MAX_RUN_SECONDS = 6 * 3600


@dataclass(frozen=True)
class Run:
    run_id: int
    workflow: str
    event: str            # push | pull_request | workflow_dispatch | schedule...
    conclusion: str       # success | failure | cancelled | ...
    run_attempt: int      # >1 means someone pressed re-run
    head_sha: str
    created_at: datetime  # queued
    started_at: datetime  # picked up by a runner
    updated_at: datetime  # finished
    repo: str = ""        # owner/name — empty for single-repo exports
    path: str = ""        # .github/workflows/x.yml — the same file gets copied
                          # into every repo, so it's the unit you actually fix
    branch: str = ""      # head_branch — the next push here is the fix
    actor: str = ""       # who triggered it; "...[bot]" is not a human
    title: str = ""       # commit/PR subject — identical across repos means
                          # one fix was pushed everywhere, not N diagnoses

    @property
    def is_human(self) -> bool:
        return bool(self.actor) and not self.actor.endswith("[bot]")

    @property
    def label(self) -> str:
        """Workflow identity for attribution: names collide across repos."""
        return f"{self.repo}/{self.workflow}" if self.repo else self.workflow

    @property
    def template(self) -> str:
        """Shared workflow file, across every repo that copied it."""
        return self.path or self.workflow

    @property
    def commit(self) -> tuple[str, str]:
        """A broken commit is triaged once, however many workflows go red."""
        return (self.repo, self.head_sha)

    @property
    def queue_seconds(self) -> float:
        return max(0.0, (self.started_at - self.created_at).total_seconds())

    @property
    def duration_seconds(self) -> float:
        elapsed = max(0.0, (self.updated_at - self.started_at).total_seconds())
        return min(elapsed, MAX_RUN_SECONDS)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_run(obj: dict) -> Run:
    return Run(
        run_id=obj["id"],
        workflow=obj.get("name") or obj.get("path", "unknown"),
        event=obj.get("event", "unknown"),
        conclusion=obj.get("conclusion") or "in_progress",
        run_attempt=obj.get("run_attempt", 1),
        head_sha=obj.get("head_sha", ""),
        created_at=_ts(obj["created_at"]),
        started_at=_ts(obj.get("run_started_at") or obj["created_at"]),
        updated_at=_ts(obj["updated_at"]),
        repo=(obj.get("repository") or {}).get("full_name", ""),
        path=obj.get("path", ""),
        branch=obj.get("head_branch") or "",
        actor=(obj.get("triggering_actor") or {}).get("login", ""),
        title=(obj.get("display_title")
               or (obj.get("head_commit") or {}).get("message", "")).split("\n")[0],
    )


def load_runs(path: str | Path) -> list[Run]:
    text = Path(path).read_text().strip()
    if text.startswith("["):
        raw = json.loads(text)
    else:
        # `gh --paginate` concatenates objects: {"workflow_runs":[...]}{"workflow_runs":[...]}
        raw = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(text):
            obj, offset = decoder.raw_decode(text, pos)
            raw.extend(obj.get("workflow_runs", []))
            pos = offset
            while pos < len(text) and text[pos] in " \r\n\t":
                pos += 1
    runs = [_to_run(o) for o in raw if o.get("status") == "completed"]
    runs.sort(key=lambda r: r.created_at)
    return runs
