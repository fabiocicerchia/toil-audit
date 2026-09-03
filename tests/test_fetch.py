"""Tests for the API ingest path.

No network: the opener and the clock are injected, so pagination, rate-limit
resumption and caching are exercised deterministically.
"""

import io
import json
import urllib.error
from pathlib import Path

import pytest

from toilaudit import fetch
from toilaudit.ingest import load_runs, runs_from_objects


def run_obj(i, **kw):
    obj = {
        "id": i,
        "name": "ci",
        "path": ".github/workflows/ci.yml",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "head_sha": f"sha{i}",
        "created_at": "2026-07-01T10:00:00Z",
        "run_started_at": "2026-07-01T10:01:00Z",
        "updated_at": "2026-07-01T10:05:00Z",
        "head_branch": "main",
        "triggering_actor": {"login": "someone"},
        "display_title": f"commit {i}",
        "repository": {"full_name": "o/r"},
    }
    obj.update(kw)
    return obj


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def opener_for(pages, seen=None):
    """An opener yielding the given page bodies in order."""

    def _open(request):
        if seen is not None:
            seen.append(request)
        if not pages:
            raise AssertionError("more requests than pages")
        body = pages.pop(0)
        if isinstance(body, Exception):
            raise body
        return FakeResponse(json.dumps(body).encode())

    return _open


def http_error(code=403, remaining="0", reset=1000):
    return urllib.error.HTTPError(
        "https://api.github.com",
        code,
        "rate limited",
        {"X-RateLimit-Remaining": remaining, "X-RateLimit-Reset": str(reset)},
        None,
    )


def test_pagination_stops_on_a_short_page():
    full = {"workflow_runs": [run_obj(i) for i in range(fetch.PER_PAGE)]}
    tail = {"workflow_runs": [run_obj(999)]}
    seen = []
    runs = fetch.fetch_github_runs(
        "o/r", token="t", opener=opener_for([full, tail], seen)
    )
    assert len(runs) == fetch.PER_PAGE + 1
    assert [r.full_url.split("page=")[-1] for r in seen] == ["1", "2"]


def test_token_is_sent_but_never_in_the_url():
    seen = []
    fetch.fetch_github_runs(
        "o/r", token="s3cret", opener=opener_for([{"workflow_runs": []}], seen)
    )
    (request,) = seen
    assert request.headers["Authorization"] == "Bearer s3cret"
    assert "s3cret" not in request.full_url


def test_token_comes_from_the_environment_only():
    assert fetch.token_from_env({"GITHUB_TOKEN": "a"}) == "a"
    assert fetch.token_from_env({"GH_TOKEN": "b"}) == "b"
    with pytest.raises(fetch.MissingToken) as err:
        fetch.token_from_env({})
    # The message must point at the environment, not offer a flag.
    assert "GITHUB_TOKEN" in str(err.value)
    assert "--token" not in str(err.value)


def test_rate_limit_waits_and_resumes_on_the_same_page():
    pages = [http_error(reset=500), {"workflow_runs": [run_obj(1)]}]
    slept = []
    runs = fetch.fetch_github_runs(
        "o/r",
        token="t",
        opener=opener_for(pages),
        sleep=slept.append,
        now=lambda: 440.0,
    )
    # Waited until the reset (+1s of slack), then got the page it was denied.
    assert slept == [61.0]
    assert len(runs) == 1


def test_rate_limit_gives_up_rather_than_looping_for_ever():
    pages = [http_error() for _ in range(5)]
    with pytest.raises(fetch.RateLimited):
        fetch.fetch_github_runs(
            "o/r",
            token="t",
            opener=opener_for(pages),
            sleep=lambda _: None,
            now=lambda: 0.0,
            max_waits=2,
        )


def test_a_403_that_is_not_a_rate_limit_is_not_retried():
    pages = [http_error(remaining="4999")]
    with pytest.raises(fetch.RateLimited):
        fetch.fetch_github_runs("o/r", token="t", opener=opener_for(pages))


def test_other_http_errors_propagate():
    pages = [urllib.error.HTTPError("u", 404, "no such repo", {}, None)]
    with pytest.raises(urllib.error.HTTPError):
        fetch.fetch_github_runs("o/r", token="t", opener=opener_for(pages))


def test_cache_means_the_second_run_makes_no_requests(tmp_path):
    body = {"workflow_runs": [run_obj(1)]}
    first = fetch.fetch_github_runs(
        "o/r", token="t", cache_dir=tmp_path, opener=opener_for([body])
    )
    # An opener with no pages left raises if it is called at all.
    second = fetch.fetch_github_runs(
        "o/r", token="t", cache_dir=tmp_path, opener=opener_for([])
    )
    assert first == second
    assert list(tmp_path.glob("*.json"))


def test_the_cache_never_contains_the_token(tmp_path):
    body = {"workflow_runs": [run_obj(1)]}
    fetch.fetch_github_runs(
        "o/r", token="hunter2", cache_dir=tmp_path, opener=opener_for([body])
    )
    for path in tmp_path.glob("*.json"):
        assert "hunter2" not in path.read_text()


def test_since_becomes_an_api_filter_not_a_local_trim():
    seen = []
    fetch.fetch_github_runs(
        "o/r",
        token="t",
        created=">=2026-07-01",
        opener=opener_for([{"workflow_runs": []}], seen),
    )
    assert "created=%3E%3D2026-07-01" in seen[0].full_url


def test_api_and_export_agree_over_the_same_period(tmp_path):
    """The acceptance criterion: same runs in, same Runs out, either way."""
    objs = [run_obj(i) for i in range(3)] + [run_obj(9, status="in_progress")]

    export = tmp_path / "runs.json"
    export.write_text(json.dumps({"workflow_runs": objs}))
    from_export = load_runs(export)

    raw = fetch.fetch_github_runs(
        "o/r", token="t", opener=opener_for([{"workflow_runs": objs}])
    )
    from_api = runs_from_objects(raw)

    assert from_api == from_export
    # And the incomplete run is dropped by both, not just one.
    assert [r.run_id for r in from_api] == [0, 1, 2]


def test_fetch_github_runs_returns_raw_objects_for_the_shared_loader():
    body = {"workflow_runs": [run_obj(1)]}
    raw = fetch.fetch_github_runs("o/r", token="t", opener=opener_for([body]))
    assert isinstance(raw[0], dict)
    assert runs_from_objects(raw)[0].run_id == 1


def test_cache_key_is_per_page_not_per_repo(tmp_path):
    full = {"workflow_runs": [run_obj(i) for i in range(fetch.PER_PAGE)]}
    tail = {"workflow_runs": [run_obj(999)]}
    fetch.fetch_github_runs(
        "o/r", token="t", cache_dir=tmp_path, opener=opener_for([full, tail])
    )
    # Two pages fetched, two cache entries: a second page must not overwrite
    # the first, which would make the cached re-run shorter than the fetch.
    assert len(list(Path(tmp_path).glob("*.json"))) == 2
