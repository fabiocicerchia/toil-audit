@domain:cost-model @area:engineer-rate @from:toilaudit/costing
Feature: Pricing toil in euros
  Lets the operator price detected toil with their own engineer and runner rates, so the euro figure a budget owner sees rests on visible, overridable inputs.

  Background:
    Given CI run history in which toil signals have been detected

  @id:cost-model.engineer-rate.001 @rule:cost-model.engineer-rate.minutes-priced-at-hourly-rate @verified @source:toilaudit/costing.py#summarize_costs @test:tests/test_toilaudit.py#test_euro_math
  Scenario Outline: Engineer time is priced at the loaded hourly rate
    Given the history contains toil that cost <engineer_minutes> engineer-minutes
    When the operator runs the audit with an engineer rate of <rate>
    Then the engineer cost reported for that toil is <engineer_cost>
    And when no rate is given the engineer rate is 75 EUR per hour

    Examples:
      | engineer_minutes | rate      | engineer_cost |
      | 10               | 60 EUR/h  | 10.00 EUR     |
      | 10               | 75 EUR/h  | 12.50 EUR     |
      | 90               | 120 EUR/h | 180.00 EUR    |

  @id:cost-model.engineer-rate.002 @rule:cost-model.runner-cost.wasted-minutes-priced-per-minute @verified @source:toilaudit/costing.py#summarize_costs @test:tests/test_toilaudit.py#test_euro_math
  Scenario Outline: Wasted runner time is priced at the per-minute runner rate
    Given the history contains toil that wasted <compute_minutes> runner-minutes
    When the operator runs the audit with a runner rate of <runner_rate>
    Then the compute waste reported for that toil is <compute_cost>
    And when no runner rate is given it is 0.0074 EUR per minute

    Examples:
      | compute_minutes | runner_rate    | compute_cost |
      | 12              | 0.10 EUR/min   | 1.20 EUR     |
      | 1000            | 0.0074 EUR/min | 7.40 EUR     |

  @id:cost-model.engineer-rate.003 @rule:cost-model.cost-summary.total-is-engineer-plus-compute @verified @source:toilaudit/costing.py#summarize_costs @test:tests/test_toilaudit.py#test_euro_math
  Scenario: Total toil is engineer cost plus compute waste, reported separately
    Given toil that cost 10 engineer-minutes and wasted 12 runner-minutes
    When the operator runs the audit at 60 EUR per hour and 0.10 EUR per runner-minute
    Then the engineer cost is shown as 10.00 EUR
    And the compute waste is shown as 1.20 EUR
    And the total toil is 11.20 EUR
