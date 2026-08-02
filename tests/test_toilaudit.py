import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from toilaudit.costing import summarize_costs
from toilaudit.ingest import Run, load_runs
from toilaudit.report import build_report
from toilaudit.signals import detect_signals

T0 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def run(run_id=1, workflow="CI", event="push", conclusion="success",
        attempt=1, sha="abc1234def", created=T0, queue_min=1.0, dur_min=10.0):
    started = created + timedelta(minutes=queue_min)
    return Run(run_id, workflow, event, conclusion, attempt, sha,
               created, started, started + timedelta(minutes=dur_min))


class TestSignals(unittest.TestCase):
    def test_green_history_is_toil_free(self):
        runs = [run(run_id=i, created=T0 + timedelta(hours=i)) for i in range(5)]
        self.assertEqual(detect_signals(runs), [])

    def test_rerun_detected_with_wasted_compute(self):
        (sig,) = [s for s in detect_signals([run(attempt=2, dur_min=12)])
                  if s.kind == "RERUN"]
        self.assertEqual(sig.engineer_minutes, 10.0)
        self.assertAlmostEqual(sig.wasted_compute_seconds, 12 * 60)

    def test_flaky_recovery_same_sha(self):
        runs = [
            run(run_id=1, conclusion="failure", sha="feed01"),
            run(run_id=2, conclusion="success", sha="feed01",
                created=T0 + timedelta(minutes=30), attempt=2),
        ]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertIn("FLAKY_RECOVERY", kinds)

    def test_new_commit_fix_is_not_flaky(self):
        runs = [
            run(run_id=1, conclusion="failure", sha="feed01"),
            run(run_id=2, conclusion="success", sha="feed02",
                created=T0 + timedelta(minutes=30)),
        ]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertNotIn("FLAKY_RECOVERY", kinds)

    def test_failure_costs_triage_and_compute(self):
        (sig,) = [s for s in detect_signals([run(conclusion="failure", dur_min=20)])
                  if s.kind == "FAILED_RUN"]
        self.assertAlmostEqual(sig.wasted_compute_seconds, 20 * 60)

    def test_manual_dispatch_and_queue_stall(self):
        runs = [run(event="workflow_dispatch", queue_min=20)]
        kinds = {s.kind for s in detect_signals(runs)}
        self.assertEqual(kinds, {"MANUAL_DISPATCH", "QUEUE_STALL"})

    def test_custom_minutes_override(self):
        (sig,) = detect_signals([run(attempt=2)], minutes={"RERUN": 3.0})
        self.assertEqual(sig.engineer_minutes, 3.0)


class TestCosting(unittest.TestCase):
    def test_euro_math(self):
        # one rerun: 10 engineer-min at 60 EUR/h = 10 EUR; 12 wasted
        # compute-min at 0.10 EUR/min = 1.20 EUR
        signals = detect_signals([run(attempt=2, dur_min=12)])
        summary = summarize_costs(signals, hourly_rate_eur=60, runner_eur_per_minute=0.10)
        (line,) = summary.lines
        self.assertEqual(line.engineer_cost_eur, 10.0)
        self.assertEqual(line.compute_cost_eur, 1.20)
        self.assertEqual(summary.total_eur, 11.20)

    def test_workflow_attribution_sorted_desc(self):
        signals = detect_signals([
            run(run_id=1, workflow="Big", conclusion="failure"),
            run(run_id=2, workflow="Big", conclusion="failure",
                created=T0 + timedelta(hours=1), sha="beef01"),
            run(run_id=3, workflow="Small", conclusion="failure",
                created=T0 + timedelta(hours=2), sha="beef02"),
        ])
        summary = summarize_costs(signals)
        self.assertEqual(list(summary.by_workflow), ["Big", "Small"])


class TestIngest(unittest.TestCase):
    def _write(self, payload) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(payload)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_paginated_concatenation(self):
        page = json.dumps({"workflow_runs": [{
            "id": 1, "name": "CI", "event": "push", "status": "completed",
            "conclusion": "success", "run_attempt": 1, "head_sha": "aa",
            "created_at": "2026-06-01T09:00:00Z",
            "run_started_at": "2026-06-01T09:01:00Z",
            "updated_at": "2026-06-01T09:10:00Z"}]})
        runs = load_runs(self._write(page + "\n" + page))
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].queue_seconds, 60)
        self.assertEqual(runs[0].duration_seconds, 540)

    def test_in_progress_runs_skipped(self):
        payload = json.dumps([{
            "id": 1, "name": "CI", "event": "push", "status": "in_progress",
            "conclusion": None, "run_attempt": 1, "head_sha": "aa",
            "created_at": "2026-06-01T09:00:00Z",
            "updated_at": "2026-06-01T09:10:00Z"}])
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
