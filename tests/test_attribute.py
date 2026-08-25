"""Attributing flaky-recovery cost to the test that caused it."""

import io
import zipfile

from toilaudit.attribute import (
    Attribution,
    attribute,
    failing_tests,
    file_of,
    logs_from_zip,
    summarise,
)

PYTEST_LOG = """
2026-08-15T10:00:00Z ============================= test session starts ==============================
2026-08-15T10:00:01Z collected 412 items
2026-08-15T10:00:30Z FAILED tests/test_orders.py::test_split_by_region - AssertionError: 3 != 4
2026-08-15T10:00:30Z ERROR tests/test_billing.py::test_invoice_totals
2026-08-15T10:00:31Z ===================== 1 failed, 411 passed in 30.12s ==========================
"""

GO_LOG = """
=== RUN   TestSplit
    orders_test.go:42: want 4, got 3
--- FAIL: TestSplit (0.00s)
FAIL
"""

JEST_LOG = """
  ● tests/orders.test.js › splits by region

    expect(received).toBe(expected)

      at tests/orders.test.js:12:34
"""

RSPEC_LOG = """
Failures:
  1) Orders splits by region
rspec ./spec/orders_spec.rb:12 # Orders splits by region
"""

JUNIT_LOG = """
<testsuite>
<testcase classname="tests.orders" name="test_split"><failure message="nope"/></testcase>
<testcase classname="tests.billing" name="test_ok"/>
</testsuite>
"""


class TestParsing:
    def test_pytest_failed_and_error_lines(self):
        got = failing_tests(PYTEST_LOG)
        assert "tests/test_orders.py::test_split_by_region" in got
        assert "tests/test_billing.py::test_invoice_totals" in got
        assert len(got) == 2

    def test_go(self):
        assert any(g.startswith("orders_test.go") for g in failing_tests(GO_LOG))

    def test_jest(self):
        got = failing_tests(JEST_LOG)
        assert any(g.startswith("tests/orders.test.js") for g in got)

    def test_rspec(self):
        assert failing_tests(RSPEC_LOG) == ["spec/orders_spec.rb"]

    def test_junit_only_counts_the_failing_case(self):
        got = failing_tests(JUNIT_LOG)
        assert got == ["tests.orders::test_split"]

    def test_a_passing_log_names_nothing(self):
        assert failing_tests("all 412 tests passed in 30s\nerror: none\n") == []

    def test_dependency_and_absolute_paths_are_ignored(self):
        # A failing test inside a dependency is not this repo's flaky test.
        noise = (
            "FAILED /usr/lib/python3/site-packages/pkg/tests/test_x.py::test_y - boom\n"
            "FAILED ../other-repo/tests/test_z.py::test_w - boom\n"
            "FAILED node_modules/lib/x.test.js › nope\n"
        )
        assert failing_tests(noise) == []

    def test_results_are_deduplicated_and_sorted(self):
        doubled = PYTEST_LOG + PYTEST_LOG
        assert failing_tests(doubled) == sorted(set(failing_tests(doubled)))

    def test_no_log_line_is_ever_returned(self):
        # The failure message here contains a secret. Only the identity may
        # survive, because the report is shared and logs echo credentials.
        log = "FAILED tests/test_auth.py::test_login - AssertionError: token=ghp_SECRETVALUE\n"
        got = failing_tests(log)
        assert got == ["tests/test_auth.py::test_login"]
        assert "ghp_SECRETVALUE" not in "".join(got)


class FakeSignal:
    def __init__(self, run_id, kind="FLAKY_RECOVERY"):
        self.run_id = run_id
        self.kind = kind


class TestAttribution:
    def logs_for(self, mapping):
        return lambda s: mapping.get(s.run_id, "")

    def test_cost_partitions_the_total_exactly(self):
        signals = [FakeSignal(1), FakeSignal(2), FakeSignal(3)]
        logs = {1: PYTEST_LOG, 2: RSPEC_LOG}  # 3 has no usable log
        a = attribute(signals, self.logs_for(logs), lambda s: 30.0)

        # Three recoveries at 30 each: the attributed and unattributed parts
        # must add back up to 90, never more.
        assert a.total_eur == 90.0
        assert a.unattributed == 1
        assert a.unattributed_eur == 30.0
        assert a.attributed == 2

    def test_a_run_with_several_failures_splits_evenly(self):
        # Two failing tests in one recovery: the metadata says one recovery
        # happened, not which failure cost the time, so 50/50 is the only
        # split that invents nothing.
        a = attribute([FakeSignal(1)], self.logs_for({1: PYTEST_LOG}), lambda s: 30.0)
        assert a.by_file["tests/test_orders.py"] == 15.0
        assert a.by_file["tests/test_billing.py"] == 15.0
        assert sum(a.by_file.values()) == 30.0

    def test_unattributed_is_never_spread_across_the_others(self):
        a = attribute(
            [FakeSignal(1), FakeSignal(2)],
            self.logs_for({1: RSPEC_LOG}),
            lambda s: 10.0,
        )
        assert a.by_file == {"spec/orders_spec.rb": 10.0}
        assert a.unattributed_eur == 10.0

    def test_ranking_is_by_cost(self):
        signals = [FakeSignal(1), FakeSignal(2), FakeSignal(3)]
        logs = {1: RSPEC_LOG, 2: RSPEC_LOG, 3: JEST_LOG}
        a = attribute(signals, self.logs_for(logs), lambda s: 10.0)
        ranked = a.ranked()
        assert ranked[0][0] == "spec/orders_spec.rb"
        assert ranked[0][1] == 20.0

    def test_a_fetch_failure_is_an_unattributed_recovery_not_a_crash(self):
        def boom(_):
            raise RuntimeError("403 from the logs endpoint")

        a = attribute([FakeSignal(1)], boom, lambda s: 12.0)
        assert a.unattributed == 1
        assert a.unattributed_eur == 12.0

    def test_no_recoveries_is_an_empty_attribution(self):
        a = attribute([], lambda s: "", lambda s: 0.0)
        assert a.total_eur == 0.0
        assert a.ranked() == []


class TestZip:
    def test_reads_every_step_log(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("1_build.txt", "all good\n")
            z.writestr("2_test.txt", PYTEST_LOG)
        assert "tests/test_orders.py::test_split_by_region" in failing_tests(
            logs_from_zip(buf.getvalue())
        )

    def test_a_corrupt_archive_is_empty_not_fatal(self):
        assert logs_from_zip(b"not a zip") == ""


class TestReport:
    def test_summary_ranks_and_declares_the_unattributed_share(self):
        a = Attribution(
            by_file={"tests/test_orders.py": 120.0, "spec/x_spec.rb": 30.0},
            unattributed=2,
            unattributed_eur=45.0,
        )
        text = "\n".join(summarise(a))
        assert text.index("test_orders.py") < text.index("x_spec.rb")  # ranked
        assert "EUR 45.00" in text
        assert "could not be attributed" in text

    def test_no_recoveries_says_so(self):
        assert "No flaky recoveries" in "\n".join(summarise(Attribution()))


def test_identity_strips_the_case_name():
    assert file_of("tests/test_orders.py::test_split") == "tests/test_orders.py"
    assert file_of("spec/x_spec.rb") == "spec/x_spec.rb"
