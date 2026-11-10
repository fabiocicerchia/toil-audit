@domain:toil-detection @area:reruns @from:toilaudit/signals
Feature: Counting reruns
  Shows engineering leads every time someone re-ran a pipeline by hand, priced in engineer time and in the runner time the earlier attempts burned.

  Background:
    Given the loaded engineer rate and the runner rate are the audit defaults

  @id:toil-detection.reruns.001 @rule:toil.reruns.charged-with-wasted-compute @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_rerun_detected_with_wasted_compute @test:tests/test_toilaudit.py#test_euro_math
  Scenario: A re-run is charged engineer time and the compute of every earlier attempt
    Given the run history holds a run of "CI" on its attempt 2, lasting 12 minutes
    When the operator audits the run history
    Then the audit shows one rerun incident "attempt 2 of 'CI'"
    And the rerun is charged 10 engineer minutes
    And the rerun is charged 12 minutes of wasted runner time

  @id:toil-detection.reruns.002 @rule:toil.signals.clean-history-is-toil-free @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_green_history_is_toil_free
  Scenario: A history of green first-attempt runs shows no toil
    Given the run history holds five pushed runs of "CI" that all passed on their first attempt, each queued for 1 minute
    When the operator audits the run history
    Then the audit finds no toil incidents
