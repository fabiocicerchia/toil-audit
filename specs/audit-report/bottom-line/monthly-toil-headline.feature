@domain:audit-report @area:bottom-line @from:toilaudit/report
Feature: Stating the monthly toil bill
  Gives the engineering lead one defensible euro figure per month, checked against how much human keyboard time the history can actually hold, so the number survives a budget conversation.

  Background:
    Given a CI run history has been audited at a loaded engineer rate

  @id:audit-report.bottom-line.001 @rule:audit-report.bottom-line.headline-is-last-complete-month @verified @source:toilaudit/report.py#_bottom_line @test:tests/test_toilaudit.py#test_partial_edge_months_excluded_from_run_rate
  Scenario: The headline is the cost of the last complete calendar month
    Given the history starts on 2026-06-15 and ends on 2026-08-04
    And toil in July 2026 cost €480.00 and took 32 engineer-hours
    When the operator runs the audit
    Then the headline reads "€480.00 in 2026-07 (last full month)"
    And the report says July's rate is 32 engineer-hours a month, 25% of one engineer
    And the report also states the total across all months covered

  @id:audit-report.bottom-line.002 @rule:audit-report.bottom-line.average-when-no-complete-month @inferred @source:toilaudit/report.py#_bottom_line @questionable
  Scenario: Without a complete month the headline is a per-month average over the span
    Given the history covers 2026-06-03 to 2026-06-18, so no calendar month is complete
    And the toil in it cost €120.00 in total
    When the operator runs the audit
    Then the headline reads "€243.52 per month" of toil
    And the report states "€120.00 total over 0.5 months" and the engineer-hours behind it

  @id:audit-report.bottom-line.003 @rule:audit-report.keyboard-time.ceiling-from-human-pushes @verified @source:toilaudit/report.py#keyboard_hours @test:tests/test_toilaudit.py#test_one_sitting_is_its_span_plus_a_lead_in @test:tests/test_toilaudit.py#test_bots_do_not_sit_at_keyboards
  Scenario: Human keyboard time is capped by when people pushed, with a lead-in per sitting
    Given in one month people pushed at 18:00, 18:20 and 18:40, and nobody pushed again that month
    And a bot also pushed during that month
    When the operator runs the audit
    Then the pushes count as one sitting of 40 minutes plus a 30-minute lead-in
    And the bot's pushes add no keyboard time
    And the report says push timing puts at most 1 h of human keyboard time in that month

  @id:audit-report.bottom-line.004 @rule:audit-report.keyboard-time.bill-over-half-is-flagged @verified @source:toilaudit/report.py#_bottom_line @test:tests/test_toilaudit.py#test_report_flags_a_bill_bigger_than_the_working_month
  Scenario Outline: A bill above half of the possible keyboard time is flagged as indefensible
    Given the headline month bills <billed> h of toil
    And push timing allows at most <ceiling> h of human keyboard time that month
    When the operator runs the audit
    Then the sanity check reports the bill as <share> of everything done that month
    And the warning "too high to defend in a room — lower the per-signal minutes" is <warning>

    Examples:
      | billed | ceiling | share | warning |
      | 10     | 40      | 25%   | absent  |
      | 20     | 40      | 50%   | absent  |
      | 27     | 5       | 540%  | shown   |

  @id:audit-report.bottom-line.005 @rule:audit-report.monthly-trend.partial-months-marked @verified @source:toilaudit/report.py#_monthly_trend @test:tests/test_toilaudit.py#test_partial_edge_months_excluded_from_run_rate
  Scenario: The monthly trend shows every month and marks the partial ones
    Given the history starts on 2026-06-15 and ends on 2026-08-04
    And July 2026 had runs but no toil
    When the operator runs the audit
    Then the trend lists 2026-06, 2026-07 and 2026-08
    And 2026-06 and 2026-08 carry the note "(partial month)"
    And 2026-07 shows €0.00 with no bar
