"""Pull run history straight from the GitHub API, instead of a hand-made export.

The export path works and is not going anywhere — it is the right thing for a
one-off audit, and for a repo whose history someone has already pulled. It is
also the manual step that stops this running on a schedule, which is what this
module removes.

Three things this has to get right, none of them the HTTP call:

**The token never appears anywhere but the request.** It is read from the
environment, never accepted as a flag (flags land in shell history, `ps` output
and CI logs), never logged, and never written into the cache — the cache holds
response bodies, which GitHub does not echo credentials into.

**A rate limit is a pause, not a failure.** Six months of history across an org
will hit the limit; hitting it must cost a wait, not the pages already fetched.
The fetch resumes from the page it stopped on.

**Fetching twice must not cost twice.** Pages are cached by URL, so re-running
the analysis over the same window is free and offline.

Stdlib only — urllib is enough for paginated JSON, and this repo has no runtime
dependencies to add to.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"

# GitHub's maximum; fewer pages is fewer round trips and fewer chances to be
# throttled halfway.
PER_PAGE = 100

# The listing endpoint stops at 1000 results however you paginate it. Left as a
# named constant because "the audit silently covered only the last 1000 runs"
# is exactly the kind of quiet truncation this tool exists to report on.
MAX_RESULTS = 1000

TOKEN_ENV = ("GITHUB_TOKEN", "GH_TOKEN")


class RateLimited(Exception):
    """Raised when the limit is hit and waiting is not allowed."""


def token_from_env(env=None) -> str:
    """The API token, from the environment only.

    Deliberately not a CLI flag: a flag is visible in shell history, in `ps`,
    and in the command line CI prints into its own logs.
    """
    env = os.environ if env is None else env
    for name in TOKEN_ENV:
        if env.get(name):
            return env[name]
    raise SystemExit(
        "toil-audit: no API token. Set GITHUB_TOKEN (or GH_TOKEN) — it is read "
        "from the environment only, never passed as a flag."
    )


def _cache_path(cache_dir: Path, url: str) -> Path:
    # The URL is the whole cache key: same repo, same page, same window. Hashed
    # rather than sanitised so a query string cannot escape the directory.
    return cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")


def _sleep_until(reset_epoch: float, sleep=time.sleep, now=time.time) -> None:
    # +1s so a clock a hair behind GitHub's does not wake us into a second 403.
    delay = max(0.0, reset_epoch - now()) + 1
    sleep(delay)


def fetch_pages(
    url: str,
    token: str,
    *,
    cache_dir: Path | None = None,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    now=time.time,
    wait_for_reset: bool = True,
    max_waits: int = 3,
):
    """Yield decoded JSON pages, following `page=N` until one comes back short.

    `opener` and `sleep` are injected so the retry and pagination logic can be
    tested without a network or a real wait.
    """
    page, fetched, waits = 1, 0, 0
    while fetched < MAX_RESULTS:
        page_url = f"{url}{'&' if '?' in url else '?'}per_page={PER_PAGE}&page={page}"

        cached = _cache_path(cache_dir, page_url) if cache_dir else None
        if cached and cached.exists():
            body = json.loads(cached.read_text())
        else:
            try:
                with opener(_request(page_url, token)) as resp:
                    body = json.loads(resp.read().decode())
            except urllib.error.HTTPError as err:
                if err.code not in (403, 429):
                    raise
                remaining = (
                    err.headers.get("X-RateLimit-Remaining") if err.headers else None
                )
                reset = err.headers.get("X-RateLimit-Reset") if err.headers else None
                if (
                    remaining not in ("0", None)
                    or not wait_for_reset
                    or waits >= max_waits
                ):
                    raise RateLimited(
                        f"rate limited on page {page}; "
                        f"{'waited ' + str(waits) + ' times already' if waits else 'not waiting'}"
                    ) from err
                waits += 1
                # Resume from the SAME page: the pages already yielded stay
                # yielded, and nothing is skipped over the pause.
                _sleep_until(float(reset or 0), sleep=sleep, now=now)
                continue

            if cached:
                cached.parent.mkdir(parents=True, exist_ok=True)
                # Only the response body is written. The token is not in it,
                # and it is not written next to it.
                cached.write_text(json.dumps(body))

        items = body.get("workflow_runs", body) if isinstance(body, dict) else body
        if not items:
            return
        yield body
        fetched += len(items)
        if len(items) < PER_PAGE:
            return
        page += 1


def _request(url: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "toil-audit",
        },
    )


def fetch_github_runs(
    repo: str,
    *,
    token: str | None = None,
    created: str = "",
    cache_dir: str | Path | None = None,
    **kw,
) -> list[dict]:
    """Every completed workflow run for `repo`, as the raw API objects.

    Returns the same dicts the export contains, so the existing loader parses
    them unchanged — one normalisation path, not two.

    `created` is passed through to the API's own filter (e.g. `>=2026-07-01`),
    so a window costs fewer requests rather than being trimmed after the fact.
    """
    token = token or token_from_env()
    url = f"{API}/repos/{repo}/actions/runs"
    if created:
        url += f"?created={urllib.parse.quote(created)}"
    cache = Path(cache_dir) if cache_dir else None

    runs: list[dict] = []
    for body in fetch_pages(url, token, cache_dir=cache, **kw):
        runs.extend(body.get("workflow_runs", []) if isinstance(body, dict) else body)
    return runs
