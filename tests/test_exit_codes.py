"""Each failure the CLI expects returns its own sysexits code, not a blanket 1."""

import os

from toilaudit import __main__ as cli
from toilaudit.fetch import RateLimited


def test_missing_export_file_is_noinput(tmp_path):
    assert cli.main([str(tmp_path / "nope.json")]) == os.EX_NOINPUT


def test_unparseable_export_is_dataerr(tmp_path):
    export = tmp_path / "runs.json"
    export.write_text("not json at all")
    assert cli.main([str(export)]) == os.EX_DATAERR


def test_missing_token_is_config(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert cli.main(["--repo", "o/r"]) == os.EX_CONFIG


def test_rate_limit_is_unavailable(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise RateLimited("rate limited on page 1; not waiting")

    monkeypatch.setattr(cli, "fetch_github_runs", refuse)
    assert cli.main(["--repo", "o/r"]) == os.EX_UNAVAILABLE
