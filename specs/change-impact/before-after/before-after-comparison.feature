@domain:change-impact @area:before-after @from:toilaudit/compare
Feature: Comparing toil before and after a change
  Shows an engineering lead the average monthly toil cost on each side of a named change, so they can tell whether the fix actually reduced babysitting.

  Background:
    Given an export of CI run history
    And the operator names the change with --change

  @id:change-impact.before-after.001 @rule:change-impact.before-after.complete-months-either-side-of-change-month @verified @source:toilaudit/compare.py#compare @test:tests/test_compare.py#test_the_month_of_the_change_is_in_neither_window @test:tests/test_compare.py#test_a_saving_and_its_roi
  Scenario: Each side is averaged over its complete months, and the month of the change is left out
    Given complete months cost 2026-01 €400, 2026-02 €400, 2026-03 €250, 2026-04 €100, 2026-05 €100
    And the change landed on 2026-03-10
    When the operator runs the audit
    Then the Before row reads "2026-01 → 2026-02, 2 months" at €400.00 per month
    And the After row reads "2026-04 → 2026-05, 2 months" at €100.00 per month
    And the report says "2026-03 is left out: the change split it."

  @id:change-impact.before-after.002 @rule:change-impact.before-after.toil-free-month-counts-as-zero @verified @source:toilaudit/compare.py#month_series @test:tests/test_compare.py#test_a_month_with_no_toil_counts_as_zero_not_as_missing @test:tests/test_compare.py#test_a_clean_month_after_the_fix_lowers_the_after_average
  Scenario: A month with runs but no toil counts as a zero-cost month
    Given the change landed on 2026-03-15
    And 2026-04 had CI runs but no toil, and 2026-05 had toil
    When the operator runs the audit
    Then the After row reads "2026-04 → 2026-05, 2 months"
    And 2026-04 contributes €0.00 to the after average

  @id:change-impact.before-after.003 @rule:change-impact.before-after.verdict-states-direction @verified @source:toilaudit/report.py#_before_after @test:tests/test_compare.py#test_the_report_states_an_increase @test:tests/test_compare.py#test_the_report_states_a_saving_and_its_roi @test:tests/test_compare.py#test_toil_that_went_up_is_reported_as_a_loss @test:tests/test_compare.py#test_no_change_in_toil_never_pays_back_rather_than_dividing_by_zero
  Scenario Outline: The report states whether toil per month fell, rose or stayed the same after the change
    Given the before average is <before> a month and the after average is <after> a month
    When the operator runs the audit
    Then the report states "<verdict> toil after the change" or "no change in toil per month"

    Examples:
      | before  | after   | verdict              |
      | €400.00 | €100.00 | €300.00 a month less |
      | €100.00 | €250.00 | €150.00 a month more |
      | €200.00 | €200.00 | no change            |

  @id:change-impact.before-after.004 @rule:change-impact.before-after.one-sided-history-not-compared @verified @source:toilaudit/compare.py#Comparison @test:tests/test_compare.py#test_a_boundary_with_nothing_complete_on_one_side_is_not_comparable
  Scenario: Without a complete month on both sides, no comparison is given
    Given the only complete month is 2026-01
    And the change landed on 2026-02-01
    When the operator runs the audit
    Then the report says "Not enough history to compare: no complete month after 2026-02"
    And no before/after figures or ROI are shown
