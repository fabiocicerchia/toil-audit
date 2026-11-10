@domain:toil-detection @area:flaky-recoveries @from:toilaudit/signals
Feature: Detecting flaky recoveries
  Shows engineering leads each time a commit went red and then green with no new commit in between, which is the flaky-test babysitting loop.

  @id:toil-detection.flaky-recoveries.001 @rule:toil.flaky.red-then-green-same-commit @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_flaky_recovery_same_sha
  Scenario: A workflow that fails and then passes on the same commit is a flaky recovery
    Given workflow "CI" failed on commit feed01
    And workflow "CI" later passed on commit feed01 with no new commit in between
    When the operator audits the run history
    Then the audit shows a flaky recovery "'CI' red->green on same sha feed01"
    And the flaky recovery is charged 15 engineer minutes

  @id:toil-detection.flaky-recoveries.002 @rule:toil.flaky.new-commit-fix-is-not-flaky @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_new_commit_fix_is_not_flaky
  Scenario: A failure fixed by a new commit is not a flaky recovery
    Given workflow "CI" failed on commit feed01
    And workflow "CI" later passed on commit feed02
    When the operator audits the run history
    Then the audit shows no flaky recovery

  @id:toil-detection.flaky-recoveries.003 @rule:toil.flaky.no-commit-identity-never-correlated @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_failures_without_a_sha_are_not_correlated
  Scenario: Runs that name no commit are never treated as a recovery
    Given a Jenkins job without git data failed twice and then passed
    When the operator audits the run history
    Then the audit shows no flaky recovery
    And each of the two failures is charged engineer time
