"""Load CI runs from a GitHub Actions or GitLab CI export.

    gh   api 'repos/OWNER/REPO/actions/runs?per_page=100' --paginate > runs.json
    glab api 'projects/:id/pipelines?per_page=100'        --paginate > pipelines.json

Both normalise onto one `Run` shape, so `signals` and `costing` never learn
which CI system produced a row. Where the two systems genuinely differ — GitLab
has no run-attempt counter, and its list endpoint omits start/finish times —
the difference is resolved here and documented at the point it is resolved,
rather than leaking a second vocabulary into the detectors.
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
    event: str  # push | pull_request | workflow_dispatch | schedule...
    conclusion: str  # success | failure | cancelled | ...
    run_attempt: int  # >1 means someone pressed re-run
    head_sha: str
    created_at: datetime  # queued
    started_at: datetime  # picked up by a runner
    updated_at: datetime  # finished
    repo: str = ""  # owner/name — empty for single-repo exports
    path: str = ""  # .github/workflows/x.yml — the same file gets copied
    # into every repo, so it's the unit you actually fix
    branch: str = ""  # head_branch — the next push here is the fix
    actor: str = ""  # who triggered it; "...[bot]" is not a human
    title: str = ""  # commit/PR subject — identical across repos means
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
        title=(
            obj.get("display_title")
            or (obj.get("head_commit") or {}).get("message", "")
        ).split("\n")[0],
    )


# GitLab status -> the GitHub vocabulary the signal detectors speak.
# `manual` is deliberately `action_required`: a pipeline parked on a manual job
# is precisely "waiting for a human to press something", which is the toil the
# GitHub side calls action_required.
_GITLAB_STATUS = {
    "success": "success",
    "failed": "failure",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "manual": "action_required",
    "skipped": "skipped",
}

# GitLab pipeline `source` -> GitHub `event`. `web` is a pipeline started by
# hand from the UI, which is what workflow_dispatch means on the GitHub side,
# so the manual-trigger signal fires for both.
_GITLAB_SOURCE = {
    "push": "push",
    "merge_request_event": "pull_request",
    "schedule": "schedule",
    "web": "workflow_dispatch",
    "api": "workflow_dispatch",
    "trigger": "workflow_dispatch",
}


def _gitlab_repo(obj: dict) -> str:
    """`https://gitlab.com/group/sub/project/-/pipelines/61` -> `group/sub/project`."""
    url = obj.get("web_url") or ""
    if "/-/pipelines" in url:
        path = url.split("://", 1)[-1].split("/-/pipelines", 1)[0]
        return path.split("/", 1)[1] if "/" in path else ""
    project = obj.get("project_id")
    return f"project-{project}" if project else ""


def _to_gitlab_run(obj: dict, attempt: int) -> Run:
    created = _ts(obj["created_at"])
    started = _ts(obj["started_at"]) if obj.get("started_at") else created
    finished = (
        _ts(obj["finished_at"]) if obj.get("finished_at") else _ts(obj["updated_at"])
    )
    user = obj.get("user") or {}
    return Run(
        run_id=obj["id"],
        workflow=obj.get("name") or ".gitlab-ci.yml",
        event=_GITLAB_SOURCE.get(obj.get("source", ""), obj.get("source", "unknown")),
        conclusion=_GITLAB_STATUS.get(
            obj.get("status", ""), obj.get("status", "unknown")
        ),
        run_attempt=attempt,
        head_sha=obj.get("sha", ""),
        created_at=created,
        started_at=started,
        updated_at=finished,
        repo=_gitlab_repo(obj),
        path=".gitlab-ci.yml",  # one pipeline definition per project, by design
        branch=obj.get("ref") or "",
        actor=user.get("username", ""),
        title=(obj.get("name") or "").split("\n")[0],
    )


def load_gitlab_runs(path: str | Path) -> list[Run]:
    """Load GitLab CI pipelines and normalise them onto the same `Run` shape.

    Input is the JSON from:

        glab api 'projects/:id/pipelines?per_page=100' --paginate > pipelines.json

    Accepts a JSON array, concatenated pages, or an object with a `pipelines`
    key. The **detail** endpoint (`/pipelines/:id`) additionally carries
    `started_at`, `finished_at` and `user`; when those are absent the list
    shape's `created_at`/`updated_at` are used, which makes queue time zero
    rather than invented.

    **Attempts are derived, not read.** GitLab has no `run_attempt`: pressing
    "retry" produces a *new pipeline on the same commit*. Pipelines are grouped
    by (repo, sha, ref) and numbered in creation order, so the second pipeline
    on a commit is attempt 2 — which is what the re-run signal is counting.
    """
    raw = _load_json_pages(path, "pipelines")
    ordered = sorted(
        (o for o in raw if o.get("status") in _GITLAB_STATUS),
        key=lambda o: o["created_at"],
    )
    attempts: dict[tuple, int] = {}
    runs = []
    for obj in ordered:
        key = (_gitlab_repo(obj), obj.get("sha", ""), obj.get("ref", ""))
        attempts[key] = attempts.get(key, 0) + 1
        runs.append(_to_gitlab_run(obj, attempts[key]))
    runs.sort(key=lambda r: r.created_at)
    return runs


def _load_json_pages(path: str | Path, key: str) -> list[dict]:
    """A JSON array, concatenated `--paginate` pages, or {"<key>": [...]}.

    One decoder loop covers all three: `--paginate` concatenates whole documents
    with nothing between them, so `json.loads` on the whole file fails on the
    second one. Reading document by document is the only shape that works for
    every export at once.
    """
    text = Path(path).read_text().strip()
    out: list[dict] = []
    decoder, pos = json.JSONDecoder(), 0
    while pos < len(text):
        obj, offset = decoder.raw_decode(text, pos)
        if isinstance(obj, list):
            out.extend(obj)
        elif isinstance(obj, dict):
            out.extend(obj.get(key, []))
        pos = offset
        while pos < len(text) and text[pos] in " \r\n\t":
            pos += 1
    return out


def runs_from_objects(raw: list[dict]) -> list[Run]:
    """Normalise raw API objects into `Run`s.

    The API path and the export path both end here, so a run fetched over HTTP
    and the same run read from a file cannot be interpreted differently.
    """
    runs = [_to_run(o) for o in raw if o.get("status") == "completed"]
    runs.sort(key=lambda r: r.created_at)
    return runs


def load_runs(path: str | Path) -> list[Run]:
    """Load a GitHub Actions export: an array, or concatenated `--paginate` pages."""
    return runs_from_objects(_load_json_pages(path, "workflow_runs"))


LOADERS = {"github": load_runs, "gitlab": load_gitlab_runs}
