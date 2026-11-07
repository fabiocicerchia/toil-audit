@domain:audit-report @area:cost-breakdown @from:toilaudit/report
Feature: Breaking down where the toil cost comes from
  Shows the lead the inputs behind the headline and where the cost comes from, so every euro can be traced to a signal, a workflow file and an assumption.

  Background:
    Given a CI run history has been audited at a loaded engineer rate

  @id:audit-report.cost-breakdown.001 @rule:audit-report.cost-breakdown.header-states-scope-and-rate @inferred @source:toilaudit/report.py#build_report
  Scenario: The report opens with the runs, repositories, period and engineer rate it priced
    Given the history holds 1,240 completed runs across 6 repositories from 2026-01-05 to 2026-06-30
    And the engineer rate is €75.00 an hour
    When the operator runs the audit
    Then the report opens with "1240 completed CI runs across 6 repos, 2026-01-05 → 2026-06-30. Engineer rate €75.00/h (loaded)."

  @id:audit-report.cost-breakdown.002 @rule:audit-report.cost-breakdown.per-signal-table @verified @source:toilaudit/report.py#_cost_table @test:tests/test_toilaudit.py#test_sample_dataset_produces_report
  Scenario: Each toil source is tabulated with its events, minutes and euros
    Given the history has 12 failed runs from 5 broken commits and 3 manual re-runs
    When the operator runs the audit
    Then the table has a "Failure triage" line with 12 events and 5 charged
    And the "Manual re-runs" line shows "—" as charged because every event is billed
    And each line shows engineer minutes, engineer €, compute waste minutes and compute €
    And a note explains that failure triage is billed once per broken commit

  @id:audit-report.cost-breakdown.003 @rule:audit-report.cost-breakdown.shared-workflow-files-listed @inferred @source:toilaudit/report.py#build_report
  Scenario: Only workflow files shared by several repositories are ranked as fix-once targets
    Given ".github/workflows/security.yml" causes toil in 4 repositories, costing €900.00
    And ".github/workflows/release.yml" causes toil in 1 repository
    When the operator runs the audit
    Then "Costliest workflow files" lists security.yml with 4 repos and €900.00
    And release.yml is not listed there
    And at most 8 files are listed
