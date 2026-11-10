@domain:command-line @area:input-selection @from:toilaudit/toilaudit
Feature: Choosing what to audit
  Lets an operator point the audit at exactly one source of CI history and refuses option combinations that would make the euro figure meaningless.

  @id:command-line.input-selection.001 @rule:command-line.input.exactly-one-source @inferred @source:toilaudit/__main__.py#main
  Scenario Outline: An audit needs exactly one source of run history
    Given the operator has a workflow-runs export "runs.json"
    When the operator runs toil-audit with <arguments>
    Then the command is refused with "give either an export file or --repo, not both"
    And the exit status is 2
    And no report is written

    Examples:
      | arguments                    |
      | runs.json --repo acme/shop   |
      | no export file and no --repo |

  @id:command-line.input-selection.002 @rule:command-line.input.fix-hours-must-price-a-change @verified @source:toilaudit/__main__.py#main @test:tests/test_compare.py#test_fix_hours_without_a_change_is_refused @test:tests/test_compare.py#test_fix_hours_that_are_not_a_finite_cost_are_refused
  Scenario Outline: Fix hours are refused unless they price a named change with a finite, non-negative cost
    Given the operator has a workflow-runs export "runs.json"
    When the operator runs toil-audit on runs.json with <arguments>
    Then the command is refused with "<message>"
    And the exit status is 2
    And no report is written

    Examples:
      | arguments                           | message                                            |
      | --fix-hours 3                       | --fix-hours prices a change; name it with --change |
      | --change 2026-01-15 --fix-hours nan | --fix-hours must be a finite, non-negative number  |
      | --change 2026-01-15 --fix-hours inf | --fix-hours must be a finite, non-negative number  |
      | --change 2026-01-15 --fix-hours -1  | --fix-hours must be a finite, non-negative number  |
