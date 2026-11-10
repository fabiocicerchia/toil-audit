@domain:change-impact @area:fix-roi @from:toilaudit/compare
Feature: Pricing a fix and its payback
  Turns the hours a fix took into euros at the configured rate and states whether, and when, the measured saving pays it back, so the fix can be justified in a budget conversation.

  Background:
    Given an export of CI run history
    And the operator names the change with --change

  @id:change-impact.before-after.007 @rule:change-impact.fix-roi.payback-statement @verified @source:toilaudit/report.py#_before_after @test:tests/test_compare.py#test_without_fix_hours_the_roi_is_left_out_and_says_so @test:tests/test_compare.py#test_the_report_states_a_saving_and_its_roi @test:tests/test_compare.py#test_the_report_states_an_increase
  Scenario Outline: The fix's cost is priced at the engineer rate and its payback stated from the measured saving
    Given toil fell from <before> to <after> per month over 3 complete months after the change
    And the engineer rate is €75.00 an hour
    When the operator runs the audit with <fix_hours> fix hours
    Then the report states <roi>

    Examples:
      | before  | after   | fix_hours  | roi                                                                                                                                                              |
      | €300.00 | €100.00 | none given | No ROI: pass `--fix-hours` with the engineer-hours the fix took.                                                                                                 |
      | €300.00 | €100.00 | 0          | The fix cost nothing, so there is nothing for it to repay.                                                                                                       |
      | €300.00 | €100.00 | 8          | The fix cost €600.00. At this saving it pays for itself in 3.0 months; over the 3 measured after it, it has returned €600.00, €0.00 net.                         |
      | €300.00 | €100.00 | 4          | The fix cost €300.00. At this saving it pays for itself in 1.5 months; over the 3 measured after it, it has returned €600.00, €300.00 net.                       |
      | €300.00 | €250.00 | 8          | The fix cost €600.00. At this saving it pays for itself in 12.0 months; over the 3 measured after it, it has returned €150.00, €450.00 short of its cost so far. |
      | €100.00 | €250.00 | 4          | The fix cost €300.00 and has not paid for itself: toil did not fall, so there is no saving to repay it from.                                                     |
