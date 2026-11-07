@domain:flaky-attribution @area:offender-ranking @from:toilaudit/attribute
Feature: Attributing flaky-recovery cost to test files
  Lets an engineering lead see which test files the flaky-recovery euros belong to, so a slide figure becomes a ticket against a named file.

  Background:
    Given the operator runs the audit with failed-run logs supplied for attribution

  @id:flaky-attribution.offender-ranking.001 @rule:flaky-attribution.offender-ranking.partitions-the-flaky-total @inferred @source:toilaudit/attribute.py#attribute @questionable
  Scenario: Attributed and unattributed flaky cost add up to the flaky-recovery total
    Given 3 flaky recoveries each priced at EUR 30.00
    And the logs of 2 of them name a failing test and the third names none
    When the operator produces the audit report
    Then the attributed and unattributed amounts together total EUR 90.00
    And 1 recovery worth EUR 30.00 is reported as unattributed
    And the unattributed EUR 30.00 is not added to any test file

  @id:flaky-attribution.offender-ranking.002 @rule:flaky-attribution.offender-ranking.even-split-across-failing-tests @inferred @source:toilaudit/attribute.py#attribute
  Scenario: A recovery whose log names several failing tests splits its cost evenly between them
    Given one flaky recovery priced at EUR 30.00
    And its log names tests/test_orders.py::test_split_by_region and tests/test_billing.py::test_invoice_totals as failing
    When the operator produces the audit report
    Then tests/test_orders.py is charged EUR 15.00
    And tests/test_billing.py is charged EUR 15.00

  @id:flaky-attribution.offender-ranking.003 @rule:flaky-attribution.offender-ranking.unreadable-log-is-unattributed @inferred @source:toilaudit/attribute.py#attribute
  Scenario Outline: A recovery whose log cannot be read is counted as unattributed and the audit still completes
    Given one flaky recovery priced at EUR 12.00
    And its log <log_state>
    When the operator produces the audit report
    Then the report is produced
    And 1 recovery worth EUR 12.00 is reported as unattributed

    Examples:
      | log_state                         |
      | is missing from the log directory |
      | fails to be read                  |
      | is a corrupt zip archive          |
      | names no recognised test failure  |

  @id:flaky-attribution.offender-ranking.004 @rule:flaky-attribution.log-sources.zip-reads-every-step @inferred @source:toilaudit/attribute.py#logs_from_zip
  Scenario: A run's log archive is searched across all of its step logs
    Given a flaky recovery whose log is a zip archive of step logs
    And the failing test tests/test_orders.py::test_split_by_region appears only in the second step's log
    When the operator produces the audit report
    Then tests/test_orders.py is charged the recovery's cost

  @id:flaky-attribution.offender-ranking.005 @rule:flaky-attribution.offender-ranking.top-files-ranked-by-cost @inferred @source:toilaudit/attribute.py#summarise
  Scenario: The report lists the ten most expensive test files, costliest first
    Given recoveries charging spec/orders_spec.rb EUR 20.00 and tests/orders.test.js EUR 10.00
    When the operator produces the audit report
    Then the section "Flaky recoveries by test file" shows a table of test file and attributed cost
    And spec/orders_spec.rb is listed first at "EUR 20.00"
    And files with equal cost are listed alphabetically
    And no more than 10 files are listed

  @id:flaky-attribution.offender-ranking.006 @rule:flaky-attribution.offender-ranking.unattributed-share-declared @inferred @source:toilaudit/attribute.py#summarise
  Scenario: The report states how many recoveries and euros could not be attributed
    Given 2 flaky recoveries worth EUR 45.00 in total have no recognised test failure in their logs
    When the operator produces the audit report
    Then the report says "2 recovery(ies) worth EUR 45.00 could not be attributed — no recognised test failure in the logs"
    And the report says the amount is counted there rather than spread across the files above

  @id:flaky-attribution.offender-ranking.007 @rule:flaky-attribution.offender-ranking.none-detected-message @inferred @source:toilaudit/attribute.py#summarise
  Scenario: With no flaky recoveries the report says none were detected
    Given the run history contains no flaky recoveries
    When the operator produces the audit report
    Then the section "Flaky recoveries by test file" says "No flaky recoveries detected."
