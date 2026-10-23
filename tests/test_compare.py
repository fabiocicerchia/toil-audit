"""Before/after a named change: what a fix was worth, or cost."""

import json
from calendar import monthrange
from datetime import datetime, timezone

import pytest

from toilaudit import __main__ as cli
from toilaudit.compare import compare, resolve_boundary
from toilaudit.ingest import Run

RATE = 75.0
UTC = timezone.utc


def _run(day: str, sha: str = "a" * 40) -> Run:
    t = datetime.fromisoformat(day).replace(tzinfo=UTC)
    return Run(1, "ci", "push", "success", 1, sha, t, t, t)


def test_a_saving_and_its_roi():
    complete = [
        ("2026-01", 400.0),
        ("2026-02", 400.0),
        ("2026-04", 100.0),
        ("2026-05", 100.0),
    ]
    cmp = compare(
        complete, datetime(2026, 3, 10, tzinfo=UTC), fix_hours=8, hourly_rate_eur=RATE
    )
    assert cmp.before_eur == 400 and cmp.after_eur == 100
    assert cmp.saving_eur == 300
    assert cmp.fix_cost_eur == 600  # 8 h at the --rate, never assumed
    assert cmp.payback_months == 2
    assert cmp.returned_eur == 600  # two months after, at 300 each


def test_toil_that_went_up_is_reported_as_a_loss():
    complete = [("2026-01", 100.0), ("2026-03", 250.0)]
    cmp = compare(
        complete, datetime(2026, 2, 1, tzinfo=UTC), fix_hours=4, hourly_rate_eur=RATE
    )
    assert cmp.saving_eur == -150
    assert cmp.payback_months is None  # it never pays for itself


def test_the_month_of_the_change_is_in_neither_window():
    complete = [("2026-01", 1.0), ("2026-02", 2.0), ("2026-03", 3.0)]
    cmp = compare(complete, datetime(2026, 2, 15, tzinfo=UTC), None, RATE)
    assert [m for m, _ in cmp.before] == ["2026-01"]
    assert [m for m, _ in cmp.after] == ["2026-03"]


def test_no_fix_hours_means_no_roi():
    cmp = compare(
        [("2026-01", 2.0), ("2026-03", 1.0)],
        datetime(2026, 2, 1, tzinfo=UTC),
        None,
        RATE,
    )
    assert cmp.fix_cost_eur is None and cmp.payback_months is None


def test_a_boundary_with_nothing_complete_on_one_side_is_not_comparable():
    cmp = compare([("2026-01", 2.0)], datetime(2026, 2, 1, tzinfo=UTC), None, RATE)
    assert not cmp.comparable


def test_boundary_by_date_or_by_the_commit_a_fix_landed_in():
    runs = [
        _run("2026-03-04T09:00:00", "f" * 40),
        _run("2026-03-02T09:00:00", "f" * 40),
    ]
    assert resolve_boundary("2026-03-10", runs) == datetime(2026, 3, 10, tzinfo=UTC)
    # The fix's first run is the boundary, not a later rebuild of it.
    assert resolve_boundary("fffffff", runs) == datetime(2026, 3, 2, 9, tzinfo=UTC)
    with pytest.raises(ValueError, match="no run"):
        resolve_boundary("1234567", runs)
    with pytest.raises(ValueError, match="neither"):
        resolve_boundary("last tuesday", runs)


def test_a_month_with_no_toil_counts_as_zero_not_as_missing():
    from toilaudit.compare import month_series

    runs = [_run("2026-01-05T00:00:00"), _run("2026-03-31T00:00:00")]
    assert month_series({"2026-01": 5.0, "2026-03": 1.0}, runs) == {
        "2026-01": 5.0,
        "2026-02": 0.0,
        "2026-03": 1.0,
    }


def test_a_clean_month_after_the_fix_lowers_the_after_average(tmp_path, capsys):
    path = _export(
        tmp_path, {"2026-01": 4, "2026-02": 4, "2026-03": 4, "2026-04": 0, "2026-05": 4}
    )
    assert cli.main([str(path), "--change", "2026-03-15"]) == 0
    out = capsys.readouterr().out
    # April had runs and no toil: two months after, not one.
    assert "| After | 2026-04 → 2026-05, 2 months |" in out


# --- end to end --------------------------------------------------------------


def _export(tmp_path, failures_per_month: dict[str, int]):
    """A GitHub export with that many manual re-runs in each month, every day 1..28."""
    runs, n = [], 0
    for month, count in failures_per_month.items():
        for day in range(1, 29):
            n += 1
            stamp = f"{month}-{day:02d}T10:00:00Z"
            runs.append(
                {
                    "id": n,
                    "name": "ci",
                    "status": "completed",
                    "conclusion": "success",
                    "event": "push",
                    "run_attempt": 2 if day <= count else 1,
                    "head_sha": f"{n:040x}",
                    "created_at": stamp,
                    "run_started_at": stamp,
                    "updated_at": stamp,
                }
            )
    # A run on the last day of the last month, so that month counts as complete.
    last = list(failures_per_month)[-1]
    days = monthrange(int(last[:4]), int(last[5:]))[1]
    end = f"{last}-{days}T23:00:00Z"
    runs[-1]["created_at"] = runs[-1]["run_started_at"] = runs[-1]["updated_at"] = end
    p = tmp_path / "runs.json"
    p.write_text(json.dumps({"workflow_runs": runs}))
    return p


def test_the_report_states_an_increase(tmp_path, capsys):
    path = _export(
        tmp_path, {"2026-01": 2, "2026-02": 2, "2026-03": 2, "2026-04": 6, "2026-06": 6}
    )
    assert cli.main([str(path), "--change", "2026-04-15", "--fix-hours", "4"]) == 0
    out = capsys.readouterr().out
    assert "## Before and after 2026-04-15" in out
    assert "a month more** toil after the change" in out
    assert "has not paid for itself" in out


def test_the_report_states_a_saving_and_its_roi(tmp_path, capsys):
    path = _export(
        tmp_path, {"2026-01": 6, "2026-02": 6, "2026-03": 1, "2026-04": 1, "2026-05": 1}
    )
    assert cli.main([str(path), "--change", "2026-02-20", "--fix-hours", "1"]) == 0
    out = capsys.readouterr().out
    assert "a month less** toil after the change" in out
    assert "pays for itself in" in out


def test_without_fix_hours_the_roi_is_left_out_and_says_so(tmp_path, capsys):
    path = _export(tmp_path, {"2026-01": 6, "2026-02": 6, "2026-03": 1, "2026-04": 1})
    assert cli.main([str(path), "--change", "2026-02-20"]) == 0
    assert "No ROI: pass `--fix-hours`" in capsys.readouterr().out


def test_fix_hours_without_a_change_is_refused(tmp_path):
    path = _export(tmp_path, {"2026-01": 1})
    with pytest.raises(SystemExit):
        cli.main([str(path), "--fix-hours", "3"])


def test_an_unknown_commit_is_refused_rather_than_guessed(tmp_path):
    path = _export(tmp_path, {"2026-01": 1})
    with pytest.raises(SystemExit):
        cli.main([str(path), "--change", "deadbee"])
