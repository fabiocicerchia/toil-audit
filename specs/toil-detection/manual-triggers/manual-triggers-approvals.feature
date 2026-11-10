@domain:toil-detection @area:manual-triggers @from:toilaudit/signals
Feature: Flagging manual triggers and approval gates
  Shows engineering leads the runs a person had to start by hand or approve before they could run.

  @id:toil-detection.manual-triggers.001 @rule:toil.manual.hand-dispatched-run @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_manual_dispatch_and_queue_stall @test:tests/test_toilaudit.py#test_approval_gate_is_toil @questionable
  Scenario Outline: A run a person had to start or approve is charged as manual toil
    Given workflow "CI" <situation>
    When the operator audits the run history
    Then the audit shows "<incident>"
    And it is charged 5 engineer minutes

    Examples:
      | situation                                 | incident                         |
      | ran because someone dispatched it by hand | 'CI' triggered by hand           |
      | is parked until someone approves it       | 'CI' parked waiting for approval |
