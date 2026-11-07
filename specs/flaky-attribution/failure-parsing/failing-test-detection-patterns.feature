@domain:flaky-attribution @area:failure-parsing @from:toilaudit/patterns
Feature: Recognising the failing test in a CI log
  Lets the engineering lead see which test caused each flaky recovery, so the flaky cost becomes a ticket against a named test instead of a slide about flakiness.

  Background:
    Given a flaky recovery whose failed run left a job log

  @id:flaky-attribution.failure-parsing.006 @rule:flaky-attribution.failure-parsing.recognised-test-runners @inferred @source:toilaudit/patterns.py#PATTERNS
  Scenario Outline: Failing tests are named from each supported test runner's own failure output
    Given the failed run's log contains the line "<log line>"
    When the operator runs the audit
    Then the recovery is attributed to "<identity>"

    Examples:
      | log line                                                                       | identity                                   |
      | FAILED tests/test_orders.py::test_split_by_region - AssertionError: 3 != 4     | tests/test_orders.py::test_split_by_region |
      | ERROR tests/test_billing.py::test_invoice_totals                               | tests/test_billing.py::test_invoice_totals |
      | rspec ./spec/orders_spec.rb:12 # Orders splits by region                       | spec/orders_spec.rb                        |
      | <testcase classname="tests.orders" name="test_split"><failure message="nope"/> | tests.orders::test_split                   |

  @id:flaky-attribution.failure-parsing.007 @rule:flaky-attribution.failure-parsing.timestamped-log-lines @inferred @source:toilaudit/patterns.py#PATTERNS
  Scenario: Failures are found in real GitHub logs whose lines start with a timestamp
    Given every line of the failed run's log starts with a timestamp such as "2026-08-15T10:00:30Z"
    And one line reads "2026-08-15T10:00:30Z FAILED tests/test_orders.py::test_split_by_region - AssertionError"
    When the operator runs the audit
    Then the recovery is attributed to "tests/test_orders.py::test_split_by_region"

  @id:flaky-attribution.failure-parsing.008 @rule:flaky-attribution.failure-parsing.passing-output-names-nothing @inferred @source:toilaudit/patterns.py#PATTERNS
  Scenario: A log that only mentions errors in passing names no failing test
    Given the failed run's log reads "all 412 tests passed in 30s" and "error: none"
    When the operator runs the audit
    Then no failing test is named for the recovery
    And the recovery's cost is counted as unattributed

  @id:flaky-attribution.failure-parsing.009 @rule:flaky-attribution.failure-parsing.only-failing-junit-cases @inferred @source:toilaudit/patterns.py#PATTERNS
  Scenario: Only the JUnit test cases that failed are named
    Given the failed run's JUnit report lists case "tests.orders" "test_split" with a failure
    Andcase "tests.billing" "test_ok" without a failure
    When the operator runs the audit
    Then the recovery is attributed to "tests.orders::test_split" only

  @id:flaky-attribution.failure-parsing.010 @rule:flaky-attribution.failure-parsing.foreign-tests-ignored @inferred @source:toilaudit/patterns.py#SUSPICIOUS
  Scenario Outline: Failing tests outside the repository are never blamed
    Given the failed run's log contains the line "<log line>"
    When the operator runs the audit
    Then no failing test is named for the recovery

    Examples:
      | log line                                                                 |
      | FAILED /usr/lib/python3/site-packages/pkg/tests/test_x.py::test_y - boom |
      | FAILED ../other-repo/tests/test_z.py::test_w - boom                      |
      | ● node_modules/lib/x.test.js › nope                                      |
      | C:/agent/tests/test_x.py::test_y FAILED                                  |

  @id:flaky-attribution.failure-parsing.011 @rule:flaky-attribution.failure-parsing.go-failures-by-file @inferred @source:toilaudit/patterns.py#GO_FAIL
  Scenario Outline: A failing Go run is attributed to the test files its log mentions
    Given the failed run's log shows "orders_test.go:42: want 4, got 3"
    Andthe log <reports a failure>
    When the operator runs the audit
    Then the named failing tests are <identities>

    Examples:
      | reports a failure                      | identities       |
      | contains "--- FAIL: TestSplit (0.00s)" | "orders_test.go" |
      | contains no "--- FAIL" line            | none             |

  @id:flaky-attribution.failure-parsing.012 @rule:flaky-attribution.failure-parsing.failure-message-never-reported @inferred @source:toilaudit/patterns.py#PATTERNS
  Scenario: A failure message is never copied into the report, only the test's name
    Given the failed run's log contains "FAILED tests/test_auth.py::test_login - AssertionError: token=ghp_EXAMPLEVALUE"
    When the operator runs the audit
    Then the recovery is attributed to "tests/test_auth.py::test_login"
    And the text "ghp_EXAMPLEVALUE" appears nowhere in the attribution

  @id:flaky-attribution.failure-parsing.013 @rule:flaky-attribution.failure-parsing.jest-failure-counted-twice @inferred @source:toilaudit/patterns.py#PATTERNS @questionable
  Scenario: One failing Jest test is named twice, by title and by bare file
    Given the failed run's log contains "● tests/orders.test.js › splits by region"
    Andthe stack line "at tests/orders.test.js:12:34"
    When the operator runs the audit
    Then the named failing tests are "tests/orders.test.js" and "tests/orders.test.js::splits by region"
    And each is credited half of the recovery's cost, so tests/orders.test.js is still charged the full cost in the by-file ranking
