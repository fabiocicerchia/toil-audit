@domain:flaky-attribution @area:failure-parsing @from:toilaudit/attribute
Feature: Recognising failing tests in CI logs
  Gives the flaky-cost ranking a trustworthy test identity drawn from common test-runner output, without leaking log content into a shared report.

  Background:
    Given the operator runs the audit with failed-run logs supplied for attribution

  @id:flaky-attribution.failure-parsing.001 @rule:flaky-attribution.failure-parsing.log-content-never-reported @inferred @source:toilaudit/attribute.py#failing_tests
  Scenario: Only the test identity from a log reaches the report, never the log text
    Given a flaky recovery whose log contains "FAILED tests/test_auth.py::test_login - AssertionError: token=ghp_EXAMPLEONLY"
    When the operator produces the audit report
    Then the recovery is attributed to tests/test_auth.py
    And the text "ghp_EXAMPLEONLY" appears nowhere in the report

  @id:flaky-attribution.failure-parsing.002 @rule:flaky-attribution.failure-parsing.recognised-runner-formats @inferred @source:toilaudit/attribute.py#failing_tests
  Scenario Outline: Failing tests are recognised from the output of common test runners
    Given a flaky recovery whose log contains <log_line>
    When the operator produces the audit report
    Then the recovery is attributed to the test identity <identity>

    Examples:
      | runner         | log_line                                                           | identity                                   |
      | pytest failure | FAILED tests/test_orders.py::test_split_by_region - AssertionError | tests/test_orders.py::test_split_by_region |
      | pytest error   | ERROR tests/test_billing.py::test_invoice_totals                   | tests/test_billing.py::test_invoice_totals |
      | jest           | ● tests/orders.test.js › splits by region                          | tests/orders.test.js::splits by region     |
      | rspec          | rspec ./spec/orders_spec.rb:12 # Orders splits by region           | spec/orders_spec.rb                        |
      | junit xml      | <testcase classname="tests.orders" name="test_split"><failure      | tests.orders::test_split                   |

  @id:flaky-attribution.failure-parsing.003 @rule:flaky-attribution.failure-parsing.go-failure-names-test-files @inferred @source:toilaudit/attribute.py#_go_failures
  Scenario: A Go test log that reports a failure is attributed to every Go test file it mentions
    Given a flaky recovery whose log contains "orders_test.go:42: want 4, got 3" and "--- FAIL: TestSplit (0.00s)"
    When the operator produces the audit report
    Then the recovery is attributed to orders_test.go

  @id:flaky-attribution.failure-parsing.004 @rule:flaky-attribution.failure-parsing.outside-repo-tests-ignored @inferred @source:toilaudit/attribute.py#failing_tests
  Scenario Outline: Failing tests outside the repository are not attributed
    Given a flaky recovery whose log only reports failures at <path>
    When the operator produces the audit report
    Then the recovery is reported as unattributed

    Examples:
      | path                                               |
      | /usr/lib/python3/site-packages/pkg/tests/test_x.py |
      | ../other-repo/tests/test_z.py                      |
      | node_modules/lib/x.test.js                         |

  @id:flaky-attribution.failure-parsing.005 @rule:flaky-attribution.failure-parsing.plain-error-words-ignored @inferred @source:toilaudit/attribute.py#failing_tests
  Scenario: A log mentioning errors without a test-runner failure names no test
    Given a flaky recovery whose log says "all 412 tests passed in 30s" and "error: none"
    When the operator produces the audit report
    Then the recovery is reported as unattributed
