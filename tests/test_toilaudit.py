import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from toilaudit.costing import summarize_costs
from toilaudit.ingest import MAX_RUN_SECONDS, Run, load_runs
from toilaudit.report import build_report, keyboard_hours
from toilaudit.signals import detect_signals

T0 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def run(
    run_id=1,
    workflow="CI",
    event="push",
    conclusion="success",
    attempt=1,
    sha="abc1234def",
    created=T0,
    queue_min=1.0,
    dur_min=10.0,
    repo="",
    path="",
    branch="main",
    actor="dev",
    title="",
):
    started = created + timedelta(minutes=queue_min)
    return Run(
        run_id,
        workflow,
        event,
        conclusion,
        attempt,
        sha,
        created,
        started,
        started + timedelta(minutes=dur_min),
        repo,
        path,
        branch,
        actor,
        title,
    )


class TestSignals(unittest.TestCase):
    def test_green_history_is_toil_free(self):
        runs = [run(run_id=i, created=T0 + timedelta(hours=i)) for i in range(5)]
        self.assertEqual(detect_signals(runs), [])

    def test_rerun_detected_with_wasted_compute(self):
        (sig,) = [
            s for s in detect_signals([run(attempt=2, dur_min=12)]) if s.kind == "RERUN"
        ]
        self.assertEqual(sig.engineer_minutes, 10.0)
        self.assertAlmostEqual(sig.wasted_compute_seconds, 12 * 60)

    def test_flaky_recovery_same_sha(self):
        runs = [
            run(run_id=1, conclusion="failure", sha="feed01"),
            run(
                run_id=2,
                conclusion="success",
                sha="feed01",
                created=T0 + timedelta(minutes=30),
                attempt=2,
            ),
        ]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertIn("FLAKY_RECOVERY", kinds)

    def test_new_commit_fix_is_not_flaky(self):
        runs = [
            run(run_id=1, conclusion="failure", sha="feed01"),
            run(
                run_id=2,
                conclusion="success",
                sha="feed02",
                created=T0 + timedelta(minutes=30),
            ),
        ]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertNotIn("FLAKY_RECOVERY", kinds)

    def test_failure_costs_triage_and_compute(self):
        (sig,) = [
            s
            for s in detect_signals([run(conclusion="failure", dur_min=20)])
            if s.kind == "FAILED_RUN"
        ]
        self.assertAlmostEqual(sig.wasted_compute_seconds, 20 * 60)

    def test_manual_dispatch_and_queue_stall(self):
        runs = [run(event="workflow_dispatch", queue_min=20)]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertEqual(kinds, {"MANUAL_DISPATCH", "QUEUE_STALL"})

    def test_one_broken_commit_is_triaged_once(self):
        # a bad push turns three workflows red; a human reads the logs once
        runs = [
            run(
                run_id=i,
                workflow=w,
                conclusion="failure",
                repo="o/r",
                sha="dead01",
                created=T0 + timedelta(minutes=i),
            )
            for i, w in enumerate(["CI", "lint", "security"])
        ]
        charged = [
            s
            for s in detect_signals(runs)
            if s.kind == "FAILED_RUN" and s.engineer_minutes
        ]
        self.assertEqual(len(charged), 1)
        # ...but every red run still burns its own runner minutes
        compute = sum(
            s.wasted_compute_seconds
            for s in detect_signals(runs)
            if s.kind == "FAILED_RUN"
        )
        self.assertAlmostEqual(compute, 3 * 10 * 60)

    def test_same_workflow_in_two_repos_bills_separately(self):
        runs = [
            run(run_id=1, conclusion="failure", repo="o/a", sha="aa"),
            run(
                run_id=2,
                conclusion="failure",
                repo="o/b",
                sha="bb",
                created=T0 + timedelta(hours=1),
            ),
        ]
        summary = summarize_costs(detect_signals(runs))
        self.assertEqual(sorted(summary.by_workflow), ["o/a/CI", "o/b/CI"])

    def test_shared_workflow_file_is_summed_across_repos(self):
        runs = [
            run(
                run_id=1,
                conclusion="failure",
                repo="o/a",
                sha="aa",
                path=".github/workflows/security.yml",
            ),
            run(
                run_id=2,
                conclusion="failure",
                repo="o/b",
                sha="bb",
                path=".github/workflows/security.yml",
                created=T0 + timedelta(hours=1),
            ),
        ]
        (top,) = summarize_costs(detect_signals(runs)).by_template
        self.assertEqual(top.path, ".github/workflows/security.yml")
        self.assertEqual(top.repos, 2)

    def test_partial_edge_months_excluded_from_run_rate(self):
        # data starts mid-June and stops mid-August: only July is a full month
        runs = [
            run(run_id=i, conclusion="failure", repo="o/r", sha=f"s{i}", created=d)
            for i, d in enumerate(
                [
                    datetime(2026, 6, 15, tzinfo=timezone.utc),
                    datetime(2026, 7, 10, tzinfo=timezone.utc),
                    datetime(2026, 8, 4, tzinfo=timezone.utc),
                ]
            )
        ]
        summary = summarize_costs(detect_signals(runs))
        report = build_report(runs, detect_signals(runs), summary, 75.0)
        self.assertIn("in 2026-07** (last full month)", report)
        self.assertIn("_(partial month)_", report)

    def _triage(self, runs):
        (sig,) = [
            s
            for s in detect_signals(runs)
            if s.kind == "FAILED_RUN" and s.engineer_minutes
        ]
        return sig.engineer_minutes

    def test_never_fixed_means_nobody_triaged_it(self):
        # red, and no commit ever follows on that branch: a glance at most
        self.assertEqual(self._triage([run(conclusion="failure")]), 1.0)

    def test_fast_fix_bills_the_observed_gap_not_the_estimate(self):
        # run ends at T0+11; next commit 3 min later — that is all it can have cost
        runs = [
            run(run_id=1, conclusion="failure", sha="bad"),
            run(run_id=2, sha="fixed", created=T0 + timedelta(minutes=14)),
        ]
        self.assertAlmostEqual(self._triage(runs), 3.0)

    def test_slow_fix_is_capped_at_the_estimate(self):
        # next commit a day later: they went to bed, that is not attention
        runs = [
            run(run_id=1, conclusion="failure", sha="bad"),
            run(run_id=2, sha="fixed", created=T0 + timedelta(days=1)),
        ]
        self.assertEqual(self._triage(runs), 8.0)

    def test_bot_pushing_over_its_own_branch_is_not_triage(self):
        # dependabot supersedes its own PR: nobody read those logs
        runs = [
            run(
                run_id=1,
                conclusion="failure",
                sha="bad",
                branch="dependabot/x",
                actor="dependabot[bot]",
            ),
            run(
                run_id=2,
                sha="next",
                branch="dependabot/x",
                actor="dependabot[bot]",
                created=T0 + timedelta(minutes=14),
            ),
        ]
        self.assertEqual(self._triage(runs), 1.0)

    def test_one_fix_pushed_to_many_repos_is_diagnosed_once(self):
        # the same commit lands in 4 repos within a minute of each other
        runs = []
        for i in range(4):
            runs += [
                run(
                    run_id=2 * i,
                    conclusion="failure",
                    repo=f"o/r{i}",
                    sha=f"bad{i}",
                    title="ci: fix pre-commit EOF on LICENSE",
                    created=T0 + timedelta(minutes=i),
                ),
                run(
                    run_id=2 * i + 1,
                    repo=f"o/r{i}",
                    sha=f"fix{i}",
                    created=T0 + timedelta(minutes=i, hours=2),
                ),
            ]
        runs.sort(key=lambda r: r.created_at)
        billed = sorted(
            s.engineer_minutes
            for s in detect_signals(runs)
            if s.kind == "FAILED_RUN" and s.engineer_minutes
        )
        self.assertEqual(billed, [1.0, 1.0, 1.0, 8.0])  # one diagnosis, three copies

    def test_unrelated_failures_are_not_fanout(self):
        runs = []
        for i in range(4):
            runs += [
                run(
                    run_id=2 * i,
                    conclusion="failure",
                    repo=f"o/r{i}",
                    sha=f"bad{i}",
                    title=f"different work {i}",
                    created=T0 + timedelta(minutes=i),
                ),
                run(
                    run_id=2 * i + 1,
                    repo=f"o/r{i}",
                    sha=f"fix{i}",
                    created=T0 + timedelta(minutes=i, hours=2),
                ),
            ]
        runs.sort(key=lambda r: r.created_at)
        billed = [
            s.engineer_minutes
            for s in detect_signals(runs)
            if s.kind == "FAILED_RUN" and s.engineer_minutes
        ]
        self.assertEqual(billed, [8.0] * 4)

    def test_approval_gate_is_toil(self):
        (sig,) = detect_signals([run(conclusion="action_required")])
        self.assertEqual(sig.kind, "ACTION_REQUIRED")
        self.assertEqual(sig.engineer_minutes, 5.0)

    def test_custom_minutes_override(self):
        (sig,) = detect_signals([run(attempt=2)], minutes={"RERUN": 3.0})
        self.assertEqual(sig.engineer_minutes, 3.0)


class TestCosting(unittest.TestCase):
    def test_euro_math(self):
        # one rerun: 10 engineer-min at 60 EUR/h = 10 EUR; 12 wasted
        # compute-min at 0.10 EUR/min = 1.20 EUR
        signals = detect_signals([run(attempt=2, dur_min=12)])
        summary = summarize_costs(
            signals, hourly_rate_eur=60, runner_eur_per_minute=0.10
        )
        (line,) = summary.lines
        self.assertEqual(line.engineer_cost_eur, 10.0)
        self.assertEqual(line.compute_cost_eur, 1.20)
        self.assertEqual(summary.total_eur, 11.20)

    def test_workflow_attribution_sorted_desc(self):
        signals = detect_signals(
            [
                run(run_id=1, workflow="Big", conclusion="failure"),
                run(
                    run_id=2,
                    workflow="Big",
                    conclusion="failure",
                    created=T0 + timedelta(hours=1),
                    sha="beef01",
                ),
                run(
                    run_id=3,
                    workflow="Small",
                    conclusion="failure",
                    created=T0 + timedelta(hours=2),
                    sha="beef02",
                ),
            ]
        )
        summary = summarize_costs(signals)
        self.assertEqual(list(summary.by_workflow), ["Big", "Small"])


class TestKeyboardCeiling(unittest.TestCase):
    def test_one_sitting_is_its_span_plus_a_lead_in(self):
        runs = [
            run(run_id=i, created=T0 + timedelta(minutes=20 * i)) for i in range(3)
        ]  # 40 min of pushes, all within the 30 min gap
        self.assertAlmostEqual(keyboard_hours(runs), 40 / 60 + 0.5)

    def test_bots_do_not_sit_at_keyboards(self):
        self.assertEqual(keyboard_hours([run(actor="dependabot[bot]")]), 0.0)

    def test_report_flags_a_bill_bigger_than_the_working_month(self):
        # 200 commits break inside one 3-hour evening, each fixed the next day:
        # 27 h of billed triage inside a sitting that cannot have held it
        runs = []
        for i in range(200):
            when = datetime(2026, 7, 15, 18, tzinfo=timezone.utc) + timedelta(minutes=i)
            runs += [
                run(
                    run_id=2 * i,
                    conclusion="failure",
                    sha=f"bad{i}",
                    repo=f"o/r{i}",
                    created=when,
                ),
                run(
                    run_id=2 * i + 1,
                    sha=f"fix{i}",
                    repo=f"o/r{i}",
                    created=when + timedelta(days=1),
                ),
            ]
        # July only counts as complete if the export brackets the whole month
        runs.append(run(run_id=998, created=datetime(2026, 7, 1, tzinfo=timezone.utc)))
        runs.append(run(run_id=999, created=datetime(2026, 8, 2, tzinfo=timezone.utc)))
        runs.sort(key=lambda r: r.created_at)
        signals = detect_signals(runs)
        report = build_report(runs, signals, summarize_costs(signals), 75.0)
        self.assertIn("Sanity check", report)
        self.assertIn("too high to defend", report)


class TestIngest(unittest.TestCase):
    def _write(self, payload) -> Path:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write(payload)
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_paginated_concatenation(self):
        page = json.dumps(
            {
                "workflow_runs": [
                    {
                        "id": 1,
                        "name": "CI",
                        "event": "push",
                        "status": "completed",
                        "conclusion": "success",
                        "run_attempt": 1,
                        "head_sha": "aa",
                        "created_at": "2026-06-01T09:00:00Z",
                        "run_started_at": "2026-06-01T09:01:00Z",
                        "updated_at": "2026-06-01T09:10:00Z",
                    }
                ]
            }
        )
        runs = load_runs(self._write(page + "\n" + page))
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].queue_seconds, 60)
        self.assertEqual(runs[0].duration_seconds, 540)

    def test_stale_updated_at_is_capped(self):
        # log-retention cleanup bumps updated_at a year later; without a cap
        # one record reads as 400 days of runner time
        payload = json.dumps(
            [
                {
                    "id": 1,
                    "name": "CodeQL",
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "failure",
                    "run_attempt": 1,
                    "head_sha": "aa",
                    "repository": {"full_name": "o/r"},
                    "created_at": "2025-06-18T21:29:55Z",
                    "run_started_at": "2025-06-18T21:29:55Z",
                    "updated_at": "2026-07-25T17:08:59Z",
                }
            ]
        )
        (r,) = load_runs(self._write(payload))
        self.assertEqual(r.duration_seconds, MAX_RUN_SECONDS)
        self.assertEqual(r.label, "o/r/CodeQL")

    def test_in_progress_runs_skipped(self):
        payload = json.dumps(
            [
                {
                    "id": 1,
                    "name": "CI",
                    "event": "push",
                    "status": "in_progress",
                    "conclusion": None,
                    "run_attempt": 1,
                    "head_sha": "aa",
                    "created_at": "2026-06-01T09:00:00Z",
                    "updated_at": "2026-06-01T09:10:00Z",
                }
            ]
        )
        self.assertEqual(load_runs(self._write(payload)), [])


class TestEndToEnd(unittest.TestCase):
    def test_sample_dataset_produces_report(self):
        sample = Path(__file__).parent.parent / "data" / "sample_runs.json"
        runs = load_runs(sample)
        signals = detect_signals(runs)
        summary = summarize_costs(signals)
        self.assertGreater(summary.total_eur, 0)
        report = build_report(runs, signals, summary, 75.0)
        self.assertIn("Bottom line", report)
        self.assertIn("Flaky red→green loops", report)
        self.assertIn("Manual dispatches", report)


if __name__ == "__main__":
    unittest.main()


# --- GitLab CI ingestion ----------------------------------------------------

GITLAB_PIPELINES = json.dumps(
    [
        # two pipelines on the same commit = someone pressed retry -> attempt 2
        {
            "id": 11,
            "project_id": 7,
            "sha": "abc",
            "ref": "main",
            "status": "failed",
            "source": "push",
            "name": "build",
            "web_url": "https://gitlab.com/acme/widgets/-/pipelines/11",
            "created_at": "2026-06-01T10:00:00Z",
            "started_at": "2026-06-01T10:00:30Z",
            "finished_at": "2026-06-01T10:05:00Z",
            "updated_at": "2026-06-01T10:05:00Z",
            "user": {"username": "fabio"},
        },
        {
            "id": 12,
            "project_id": 7,
            "sha": "abc",
            "ref": "main",
            "status": "success",
            "source": "push",
            "name": "build",
            "web_url": "https://gitlab.com/acme/widgets/-/pipelines/12",
            "created_at": "2026-06-01T10:10:00Z",
            "started_at": "2026-06-01T10:10:10Z",
            "finished_at": "2026-06-01T10:14:00Z",
            "updated_at": "2026-06-01T10:14:00Z",
            "user": {"username": "fabio"},
        },
        # started by hand from the UI -> the manual-trigger signal must see it
        {
            "id": 13,
            "project_id": 7,
            "sha": "def",
            "ref": "main",
            "status": "manual",
            "source": "web",
            "name": "deploy",
            "web_url": "https://gitlab.com/acme/widgets/-/pipelines/13",
            "created_at": "2026-06-02T09:00:00Z",
            "updated_at": "2026-06-02T09:03:00Z",
            "user": {"username": "fabio"},
        },
        # still running: no terminal status, must not be counted
        {
            "id": 14,
            "project_id": 7,
            "sha": "ghi",
            "ref": "main",
            "status": "running",
            "source": "push",
            "created_at": "2026-06-02T10:00:00Z",
            "updated_at": "2026-06-02T10:01:00Z",
        },
    ]
)


def _gitlab_file(tmp_path, text=GITLAB_PIPELINES):
    p = tmp_path / "pipelines.json"
    p.write_text(text)
    return p


def test_gitlab_derives_run_attempts_from_repeated_commits(tmp_path):
    from toilaudit.ingest import load_gitlab_runs

    runs = load_gitlab_runs(_gitlab_file(tmp_path))
    by_id = {r.run_id: r for r in runs}
    assert by_id[11].run_attempt == 1
    assert by_id[12].run_attempt == 2  # retry of the same commit
    assert by_id[13].run_attempt == 1  # different commit, back to 1
    assert 14 not in by_id  # still running, not terminal


def test_gitlab_vocabulary_maps_onto_the_detectors(tmp_path):
    from toilaudit.ingest import load_gitlab_runs

    by_id = {r.run_id: r for r in load_gitlab_runs(_gitlab_file(tmp_path))}
    assert by_id[11].conclusion == "failure"  # GitLab says "failed"
    assert by_id[13].conclusion == "action_required"  # parked on a manual job
    assert by_id[13].event == "workflow_dispatch"  # source "web" = run by hand
    assert by_id[11].repo == "acme/widgets"  # parsed out of web_url
    assert by_id[11].is_human


def test_gitlab_timings_and_missing_detail_fields(tmp_path):
    from toilaudit.ingest import load_gitlab_runs

    by_id = {r.run_id: r for r in load_gitlab_runs(_gitlab_file(tmp_path))}
    assert by_id[11].queue_seconds == 30
    assert by_id[11].duration_seconds == 270
    # list-endpoint row with no started_at/finished_at: queue is 0, not invented
    assert by_id[13].queue_seconds == 0
    assert by_id[13].duration_seconds == 180


def test_gitlab_accepts_concatenated_pages(tmp_path):
    from toilaudit.ingest import load_gitlab_runs

    page = json.loads(GITLAB_PIPELINES)
    text = json.dumps(page[:2]) + "\n" + json.dumps(page[2:])
    runs = load_gitlab_runs(_gitlab_file(tmp_path, text))
    assert {r.run_id for r in runs} == {11, 12, 13}


def test_gitlab_runs_flow_through_the_signal_detectors(tmp_path):
    from toilaudit.ingest import load_gitlab_runs
    from toilaudit.signals import detect_signals

    signals = detect_signals(load_gitlab_runs(_gitlab_file(tmp_path)))
    kinds = {s.kind for s in signals}
    assert "RERUN" in kinds  # the derived attempt 2 was picked up
