@domain:cost-model @area:signal-minutes @from:toilaudit/signals
Feature: Default engineer minutes per toil signal
  Tells budget holders how many engineer minutes the audit charges for each kind of toil, so the euro figure can be defended.

  @id:cost-model.signal-minutes.001 @rule:cost.signal-minutes.defaults @verified @source:toilaudit/signals.py#DEFAULT_MINUTES @test:tests/test_toilaudit.py#test_rerun_detected_with_wasted_compute @test:tests/test_toilaudit.py#test_approval_gate_is_toil @test:tests/test_toilaudit.py#test_slow_fix_is_capped_at_the_estimate @questionable
  Scenario Outline: Each kind of toil is charged its published default minutes
    Given the run history holds one <signal> incident
    When the operator audits the run history
    Then the incident is charged <minutes> engineer minutes

    Examples:
      | signal                                     | minutes |
      | RERUN                                      | 10      |
      | FLAKY_RECOVERY                             | 15      |
      | MANUAL_DISPATCH                            | 5       |
      | QUEUE_STALL                                | 6       |
      | ACTION_REQUIRED                            | 5       |
      | FAILED_RUN (fixed by a person a day later) | 8       |
