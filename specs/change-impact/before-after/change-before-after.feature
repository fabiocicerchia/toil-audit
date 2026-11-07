@domain:change-impact @area:before-after @from:toilaudit/report
Feature: Reporting what a change did to toil and whether it paid back
  Lets a lead show whether a named CI fix reduced the monthly toil bill and how quickly the engineer-hours it cost were repaid.

  Background:
    Given the operator named a change dated 2026-04-15

  @id:change-impact.before-after.005 @rule:change-impact.before-after.monthly-verdict @verified @source:toilaudit/report.py#_before_after @test:tests/test_compare.py#test_the_report_states_an_increase @test:tests/test_compare.py#test_the_report_states_a_saving_and_its_roi
  Scenario Outline: The report states how much toil per month changed after the change
    Given complete months before the change averaged <before> of toil
    And complete months after the change averaged <after> of toil
    When the operator runs the audit
    Then a "Before and after 2026-04-15" section lists both windows with their complete months and toil per month
    And the verdict reads <verdict>
    And the report says 2026-04 is left out because the change split it

    Examples:
      | before  | after   | verdict                                    |
      | €300.00 | €100.00 | €200.00 a month less toil after the change |
      | €100.00 | €250.00 | €150.00 a month more toil after the change |
      | €200.00 | €200.00 | no change in toil per month                |

  @id:change-impact.before-after.006 @rule:change-impact.before-after.no-comparison-without-complete-months @inferred @source:toilaudit/report.py#_before_after
  Scenario: No comparison is drawn without a complete month on both sides
    Given the history has complete months before 2026-04 but none after it
    When the operator runs the audit
    Then the section says "Not enough history to compare: no complete month after 2026-04"
    And no before/after figures or verdict are shown

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
      | €300.00 | €100.00 | 4          | The fix cost €300.00. At this saving it pays for itself in 1.5 months; over the 3 measured after it, it has returned €600.00, €300.00 net.                       |
      | €300.00 | €250.00 | 8          | The fix cost €600.00. At this saving it pays for itself in 12.0 months; over the 3 measured after it, it has returned €150.00, €450.00 short of its cost so far. |
      | €100.00 | €250.00 | 4          | The fix cost €300.00 and has not paid for itself: toil did not fall, so there is no saving to repay it from.                                                     |
