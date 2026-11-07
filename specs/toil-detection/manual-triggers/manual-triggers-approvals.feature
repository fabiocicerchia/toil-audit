@domain:toil-detection @area:manual-triggers @from:toilaudit/signals
Feature: Flagging manual triggers and approval gates
  Shows engineering leads the runs a person had to start by hand or approve before they could run.

  @id:toil-detection.manual-triggers.001 @rule:toil.manual.hand-dispatched-run @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_manual_dispatch_and_queue_stall @questionable
  Scenario: A run started by hand is charged as a manual trigger
    Given workflow "CI" ran because someone dispatched it by hand
    When the operator audits the run history
    Then the audit shows "'CI' triggered by hand"
    And the manual trigger is charged 5 engineer minutes

  @id:toil-detection.manual-triggers.002 @rule:toil.manual.parked-for-approval @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_approval_gate_is_toil
  Scenario: A run parked waiting for approval is charged as toil
    Given workflow "CI" is parked until someone approves it
    When the operator audits the run history
    Then the audit shows "'CI' parked waiting for approval"
    And the approval is charged 5 engineer minutes
