@domain:toil-detection @area:queue-stalls @from:toilaudit/signals
Feature: Flagging queue stalls
  Shows engineering leads the runs that sat in the queue long enough to pull engineers away from their work.

  @id:toil-detection.queue-stalls.001 @rule:toil.queue.stall-over-threshold @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_manual_dispatch_and_queue_stall @questionable
  Scenario Outline: A run queued longer than 15 minutes is a queue stall
    Given workflow "CI" waited <queued> minutes for a runner
    When the operator audits the run history
    Then the audit <outcome>

    Examples:
      | queued | outcome                                               |
      | 20     | shows "'CI' queued 20 min" charged 6 engineer minutes |
      | 15     | shows no queue stall                                  |
      | 1      | shows no queue stall                                  |
