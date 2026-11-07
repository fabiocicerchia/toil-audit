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

  @id:command-line.input-selection.003 @rule:command-line.input.unknown-change-is-refused @verified @source:toilaudit/__main__.py#main @test:tests/test_compare.py#test_an_unknown_commit_is_refused_rather_than_guessed
  Scenario: A change the history cannot place is refused rather than guessed
    Given the operator has a workflow-runs export in which no run built commit "deadbee"
    When the operator runs toil-audit on the export with --change deadbee
    Then the command is refused with a message starting "--change:"
    And the exit status is 2
    And no before/after comparison is reported

  @id:command-line.input-selection.004 @rule:cost-model.rates.overridable-with-defaults @inferred @source:toilaudit/__main__.py#_build_parser
  Scenario Outline: Engineer and runner rates default to 75 EUR an hour and 0.0074 EUR a minute and can be overridden
    Given the operator has a workflow-runs export "runs.json"
    When the operator runs toil-audit on runs.json <rate options>
    Then engineer time is priced at <engineer rate> EUR per hour
    And runner time on wasted runs is priced at <runner rate> EUR per minute

    Examples:
      | rate options                       | engineer rate | runner rate |
      | with no rate options               | 75            | 0.0074      |
      | with --rate 90 --runner-rate 0.008 | 90            | 0.008       |
