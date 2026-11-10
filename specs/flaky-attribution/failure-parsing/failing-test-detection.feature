@domain:flaky-attribution @area:failure-parsing @from:toilaudit/attribute
Feature: Recognising failing tests in CI logs
  Gives the flaky-cost ranking a trustworthy test identity drawn from common test-runner output, without leaking log content into a shared report.

  Background:
    Given the operator runs the audit with failed-run logs supplied for attribution

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
