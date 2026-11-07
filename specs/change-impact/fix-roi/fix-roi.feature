@domain:change-impact @area:fix-roi @from:toilaudit/compare
Feature: Pricing a fix and its payback
  Turns the hours a fix took into euros at the configured rate and states whether, and when, the measured saving pays it back, so the fix can be justified in a budget conversation.

  Background:
    Given an export of CI run history
    And the operator names the change with --change

  @id:change-impact.fix-roi.001 @rule:change-impact.fix-roi.payback-and-net-return @verified @source:toilaudit/compare.py#Comparison @test:tests/test_compare.py#test_a_saving_and_its_roi @test:tests/test_compare.py#test_what_a_fix_returned_counts_the_months_after_it_only @test:tests/test_compare.py#test_the_report_states_a_saving_and_its_roi @test:tests/test_compare.py#test_the_report_states_what_the_fix_has_netted_so_far
  Scenario Outline: A fix that reduced toil is priced at the engineer rate and given a payback time and net return
    Given the before average is €400.00 a month and the after average is €100.00 a month over 2 complete months
    And the engineer rate is €75 an hour
    When the operator runs the audit with --fix-hours <hours>
    Then the report states "The fix cost <cost>"
    And it says it pays for itself in <payback> months and has returned €600.00
    And it reports <so far>

    Examples:
      | hours | cost      | payback | so far                           |
      | 8     | €600.00   | 2.0     | €0.00 net                        |
      | 4     | €300.00   | 1.0     | €300.00 net                      |
      | 20    | €1,500.00 | 5.0     | €900.00 short of its cost so far |

  @id:change-impact.fix-roi.002 @rule:change-impact.fix-roi.no-saving-never-pays-back @verified @source:toilaudit/compare.py#Comparison @test:tests/test_compare.py#test_toil_that_went_up_is_reported_as_a_loss @test:tests/test_compare.py#test_no_change_in_toil_never_pays_back_rather_than_dividing_by_zero @test:tests/test_compare.py#test_the_report_states_an_increase
  Scenario: A fix after which toil did not fall is reported as not paid for
    Given the after average is the same as or higher than the before average
    And the fix took 4 hours at €75 an hour
    When the operator runs the audit with --fix-hours 4
    Then the report states "The fix cost €300.00 and has not paid for itself"
    And no payback time is given

  @id:change-impact.fix-roi.003 @rule:change-impact.fix-roi.zero-cost-fix-owes-nothing @verified @source:toilaudit/report.py#_before_after @test:tests/test_compare.py#test_a_fix_that_cost_nothing_is_not_reported_as_unpaid
  Scenario: A fix that took no hours is not reported as unpaid
    Given toil rose after the change
    When the operator runs the audit with --fix-hours 0
    Then the report says "The fix cost nothing, so there is nothing for it to repay."
    And it does not say the fix has not paid for itself

  @id:change-impact.fix-roi.004 @rule:change-impact.fix-roi.no-hours-no-roi @verified @source:toilaudit/compare.py#compare @test:tests/test_compare.py#test_no_fix_hours_means_no_roi @test:tests/test_compare.py#test_without_fix_hours_the_roi_is_left_out_and_says_so
  Scenario: Without the hours a fix took, no return on investment is stated
    Given toil fell after the change
    When the operator runs the audit without --fix-hours
    Then the before/after comparison is shown
    And the report says "No ROI: pass `--fix-hours` with the engineer-hours the fix took."

  @id:change-impact.fix-roi.005 @rule:change-impact.fix-roi.invalid-fix-hours-refused @verified @source:toilaudit/__main__.py#main @test:tests/test_compare.py#test_fix_hours_without_a_change_is_refused @test:tests/test_compare.py#test_fix_hours_that_are_not_a_finite_cost_are_refused
  Scenario Outline: Fix hours that cannot be priced are refused
    When the operator runs the audit with <options>
    Then the audit stops with a usage error and no report
    And the error says "<message>"

    Examples:
      | options                             | message                                            |
      | --fix-hours 3 and no --change       | --fix-hours prices a change; name it with --change |
      | --change 2026-01-15 --fix-hours -1  | --fix-hours must be a finite, non-negative number  |
      | --change 2026-01-15 --fix-hours nan | --fix-hours must be a finite, non-negative number  |
      | --change 2026-01-15 --fix-hours inf | --fix-hours must be a finite, non-negative number  |
