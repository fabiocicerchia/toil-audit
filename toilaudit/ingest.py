"""Load CI runs from a GitHub Actions, GitLab CI or Jenkins export.

    gh   api 'repos/OWNER/REPO/actions/runs?per_page=100' --paginate > runs.json
    glab api 'projects/:id/pipelines?per_page=100'        --paginate > pipelines.json
    curl -sG --data-urlencode "tree=$JENKINS_TREE" "$JENKINS_URL/job/NAME/api/json" > builds.json

All three normalise onto one `Run` shape, so `signals` and `costing` never learn
which CI system produced a row. Where the systems genuinely differ — neither
GitLab nor Jenkins has a run-attempt counter, and GitLab's list endpoint omits
start/finish times — the difference is resolved here and documented at the
point it is resolved, rather than leaking a second vocabulary into the
detectors.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

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


# Jenkins `result` -> the GitHub vocabulary. UNSTABLE is a build whose tests
# failed after it compiled: red to whoever has to look at it, so `failure`.
# A build still running has a null result and is not terminal, so it is left
# out exactly as GitLab's `running` is.
_JENKINS_RESULT = {
    "SUCCESS": "success",
    "FAILURE": "failure",
    "UNSTABLE": "failure",
    "ABORTED": "cancelled",
    "NOT_BUILT": "skipped",
}

# Cause class -> GitHub `event`. Matched on the class name's tail, because the
# package prefix differs across plugin versions. A user-started build is
# workflow_dispatch whatever else is listed with it: "someone pressed Build"
# is the manual-trigger signal, and Replay/Rebuild always carry a UserIdCause.
_JENKINS_CAUSE = (
    ("UserIdCause", "workflow_dispatch"),
    ("ReplayCause", "workflow_dispatch"),
    ("RebuildCause", "workflow_dispatch"),
    ("TimerTriggerCause", "schedule"),
    ("UpstreamCause", "workflow_run"),
    ("SCMTriggerCause", "push"),
    ("BranchEventCause", "push"),
    ("BranchIndexingCause", "push"),
    ("GitHubPushCause", "push"),
    ("GitLabWebHookCause", "push"),
)

# What `api/json` has to be asked for. Jenkins returns almost nothing without a
# `tree`, and asking for everything costs the controller a full serialisation
# of every build. `allBuilds` rather than `builds`: the latter stops at 100.
JENKINS_TREE = (
    "allBuilds[number,queueId,result,timestamp,duration,url,"
    "actions[causes[_class,userId],lastBuiltRevision[SHA1,branch[name]],"
    "remoteUrls,queuingDurationMillis],changeSets[items[msg]]]"
)


def _jenkins_actions(obj: dict) -> list[dict]:
    return [a for a in obj.get("actions") or [] if isinstance(a, dict)]


def _jenkins_job_path(obj: dict) -> list[str]:
    """`https://ci/job/acme/job/widgets/job/main/42/` -> ["acme", "widgets", "main"].

    Each segment is URL-decoded once, which gives the job's own name: `My%20Folder`
    is `My Folder`. A multibranch job is named after its branch with the slash
    encoded, so `feature/x` is the job `feature%2Fx` (`feature%252Fx` in the URL).
    """
    parts = (obj.get("url") or "").split("/")
    return [unquote(parts[i + 1]) for i, p in enumerate(parts[:-1]) if p == "job"]


def _git_repo(url: str) -> str:
    """The path after the host: `https://github.com/acme/widgets.git` or
    `git@github.com:acme/widgets` -> `acme/widgets`; GitLab subgroups are kept."""
    url = url.strip()
    if "://" in url:
        rest = url.split("://", 1)[1].partition("/")[2]
    elif "@" in url.split(":", 1)[0] and ":" in url:  # scp-style git@host:path
        rest = url.split(":", 1)[1]
    else:
        return ""
    rest = rest.strip("/").removesuffix(".git")
    return rest if "/" in rest else ""


def _jenkins_checkouts(obj: dict) -> list[dict]:
    """The build's git BuildData, if they all describe one checkout.

    A Pipeline that loads a shared library, or checks out a second repository,
    records one BuildData per checkout, and the export does not say which is
    the build's own. Taking the first would pin retries and signals on the
    library's commit, so more than one distinct revision or remote reads as no
    git data at all — the same as a freestyle job without the plugin.
    """
    actions = [
        a
        for a in _jenkins_actions(obj)
        if a.get("lastBuiltRevision") or a.get("remoteUrls")
    ]
    shas = {(a.get("lastBuiltRevision") or {}).get("SHA1") for a in actions} - {None}
    remotes = {
        r for a in actions for u in a.get("remoteUrls") or [] if (r := _git_repo(u))
    }
    return actions if len(shas) <= 1 and len(remotes) <= 1 else []


def _jenkins_revision(obj: dict) -> tuple[str, str]:
    """(sha, branch) from the git plugin's BuildData, or empty strings."""
    for action in _jenkins_checkouts(obj):
        revision = action.get("lastBuiltRevision") or {}
        if revision.get("SHA1"):
            branches = revision.get("branch") or [{}]
            name = (branches[0] or {}).get("name", "")
            for prefix in ("refs/remotes/origin/", "refs/heads/", "origin/"):
                if name.startswith(prefix):
                    name = name[len(prefix) :]
                    break
            return revision["SHA1"], name
    return "", ""


def _jenkins_repo(obj: dict, job: list[str]) -> str:
    """The git remote's owner/name, else the job's folder path.

    The remote is the right identity: several Jenkins jobs commonly build one
    repository. Without the git plugin's data the folder path is the closest
    thing — the job's own name is left to `workflow`.
    """
    for action in _jenkins_checkouts(obj):
        for url in action.get("remoteUrls") or []:
            if repo := _git_repo(url):
                return repo
    return "/".join(job[:-1])


def _jenkins_event(obj: dict, job: list[str]) -> tuple[str, str]:
    """(event, actor) from the build's causes."""
    classes, actor = [], ""
    for action in _jenkins_actions(obj):
        for cause in action.get("causes") or []:
            classes.append(cause.get("_class", ""))
            actor = actor or cause.get("userId") or ""
    for tail, event in _JENKINS_CAUSE:
        if any(c.endswith(tail) for c in classes):
            # Branch-source plugins name a pull request's job `PR-<n>`; that
            # is the only place a PR build says what it is.
            if event == "push" and job and job[-1].startswith("PR-"):
                return "pull_request", actor
            return event, actor
    return "unknown", actor


def _jenkins_workflow(job: list[str], branch: str) -> str:
    """The pipeline a build belongs to, across branches.

    A multibranch pipeline gives every branch its own job, named after the
    branch (`widgets/main`, `widgets/PR-7`). GitHub's equivalent is one
    workflow running on many branches, so the parent is the workflow and the
    branch stays in `branch`; otherwise a fix to one Jenkinsfile reads as a
    dozen separate workflows. A plain job is its own name.
    """
    # Decoded again: a branch job's name still has its slash encoded once,
    # as _jenkins_job_path explains.
    if len(job) >= 2 and branch and unquote(job[-1]) == branch:
        return job[-2]
    return job[-1] if job else "jenkins"


def _to_jenkins_run(obj: dict, attempt: int) -> Run:
    job = _jenkins_job_path(obj)
    sha, branch = _jenkins_revision(obj)
    event, actor = _jenkins_event(obj, job)
    started = datetime.fromtimestamp(obj["timestamp"] / 1000, tz=timezone.utc)
    queued_ms = next(
        (
            a["queuingDurationMillis"]
            for a in _jenkins_actions(obj)
            if isinstance(a.get("queuingDurationMillis"), int | float)
        ),
        0,
    )
    messages = [
        item.get("msg", "")
        for change in obj.get("changeSets") or []
        for item in change.get("items") or []
    ]
    return Run(
        # queueId is unique across the controller; `number` is only unique
        # within one job, and two jobs' build #12 would otherwise collide.
        run_id=obj.get("queueId") or obj["number"],
        workflow=_jenkins_workflow(job, branch),
        event=event,
        conclusion=_JENKINS_RESULT[obj["result"]],
        run_attempt=attempt,
        head_sha=sha,
        created_at=started - timedelta(milliseconds=queued_ms),
        started_at=started,
        updated_at=started + timedelta(milliseconds=obj.get("duration") or 0),
        repo=_jenkins_repo(obj, job),
        branch=branch,
        actor=actor,
        title=(messages[0] if messages else "").split("\n")[0],
    )


def load_jenkins_runs(path: str | Path) -> list[Run]:
    """Load Jenkins builds and normalise them onto the same `Run` shape.

    Input is a job's `api/json` with `tree=JENKINS_TREE` — an object with an
    `allBuilds` (or `builds`) array — and several jobs' documents concatenated
    into one file are read as one export.

    **Attempts are derived, not read**, as for GitLab: Replay, Rebuild and a
    second "Build Now" all produce a new build number. Builds are grouped by
    (job, sha, branch) in start order, so the second build of one commit in one
    job is attempt 2. A build with no git revision is never grouped — there is
    nothing to say it retried anything.

    Queue time comes from the Metrics plugin's `queuingDurationMillis`; without
    it queue time is zero rather than invented.
    """
    raw = _load_json_pages(path, ("allBuilds", "builds"))
    ordered = sorted(
        (o for o in raw if o.get("result") in _JENKINS_RESULT and "timestamp" in o),
        key=lambda o: o["timestamp"],
    )
    attempts: dict[tuple, int] = {}
    runs = []
    for obj in ordered:
        sha, branch = _jenkins_revision(obj)
        job = tuple(_jenkins_job_path(obj))
        key = (
            (job, sha, branch) if sha else (job, obj.get("number"), obj.get("queueId"))
        )
        attempts[key] = attempts.get(key, 0) + 1
        runs.append(_to_jenkins_run(obj, attempts[key]))
    runs.sort(key=lambda r: r.created_at)
    return runs


def _load_json_pages(path: str | Path, key: str | tuple[str, ...]) -> list[dict]:
    """A JSON array, concatenated `--paginate` pages, or {"<key>": [...]}.

    `key` may name alternatives, first present wins per document — Jenkins
    calls the same array `allBuilds` or `builds` depending on what was asked.

    One decoder loop covers all three: `--paginate` concatenates whole documents
    with nothing between them, so `json.loads` on the whole file fails on the
    second one. Reading document by document is the only shape that works for
    every export at once.
    """
    keys = (key,) if isinstance(key, str) else key
    text = Path(path).read_text().strip()
    out: list[dict] = []
    decoder, pos = json.JSONDecoder(), 0
    while pos < len(text):
        obj, offset = decoder.raw_decode(text, pos)
        if isinstance(obj, list):
            out.extend(obj)
        elif isinstance(obj, dict):
            out.extend(next((obj[k] for k in keys if k in obj), []))
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


LOADERS = {
    "github": load_runs,
    "gitlab": load_gitlab_runs,
    "jenkins": load_jenkins_runs,
}
