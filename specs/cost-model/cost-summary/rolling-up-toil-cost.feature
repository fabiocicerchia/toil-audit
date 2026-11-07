@domain:cost-model @area:cost-summary @from:toilaudit/costing
Feature: Rolling up toil cost
  Breaks the euro figure down by kind of toil, by workflow, by shared workflow file and by month, so a budget owner can see where the money goes.

  Background:
    Given CI run history in which toil signals have been detected

  @id:cost-model.cost-summary.001 @rule:cost-model.cost-summary.detected-versus-charged-events @inferred @source:toilaudit/costing.py#summarize_costs
  Scenario: Each kind of toil shows the events detected and the events that cost an engineer
    Given one broken commit turned three workflows red
    And an engineer was charged for triaging it once
    When the operator runs the audit
    Then the "Failure triage" line counts 3 events detected and 1 event charged
    And its compute waste covers the runner time of all 3 red runs
    And kinds of toil are listed from the most to the least expensive

  @id:cost-model.cost-summary.002 @rule:cost-model.cost-summary.workflow-cost-per-repository @verified @source:toilaudit/costing.py#summarize_costs @test:tests/test_toilaudit.py#test_same_workflow_in_two_repos_bills_separately @test:tests/test_toilaudit.py#test_workflow_attribution_sorted_desc
  Scenario: Workflows with the same name in different repositories are costed separately
    Given a workflow named "CI" fails in repository o/a
    And a workflow named "CI" fails in repository o/b
    When the operator runs the audit
    Then the workflow ranking lists "o/a/CI" and "o/b/CI" as separate entries
    And workflows are ranked from the most to the least expensive

  @id:cost-model.cost-summary.003 @rule:cost-model.cost-summary.shared-template-summed-across-repos @verified @source:toilaudit/costing.py#summarize_costs @test:tests/test_toilaudit.py#test_shared_workflow_file_is_summed_across_repos
  Scenario: A workflow file copied into many repositories is costed as one template
    Given the workflow file .github/workflows/security.yml fails in repositories o/a and o/b
    When the operator runs the audit
    Then one template entry for .github/workflows/security.yml carries the cost from both repositories
    And that entry shows 2 repositories

  @id:cost-model.cost-summary.004 @rule:cost-model.cost-summary.cost-by-month-of-run @inferred @source:toilaudit/costing.py#summarize_costs
  Scenario: Toil is costed in the calendar month the run was created
    Given toil on runs created on 2026-06-15, 2026-07-10 and 2026-08-04
    When the operator runs the audit
    Then the monthly figures are given for 2026-06, 2026-07 and 2026-08, in that order
    And each run's full cost lands in the month it was created
