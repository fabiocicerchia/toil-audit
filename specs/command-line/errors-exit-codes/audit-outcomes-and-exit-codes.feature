@domain:command-line @area:errors-exit-codes @from:toilaudit/toilaudit
Feature: Audit outcomes and exit codes
  Gives operators and CI gates a distinct exit status for each kind of failure, so an unreadable input is never mistaken for a zero-cost pipeline.

  @id:command-line.errors-exit-codes.001 @rule:command-line.errors.distinct-exit-code-per-failure @verified @source:toilaudit/__main__.py#EXIT_CODES @test:tests/test_exit_codes.py#test_missing_export_file_is_noinput @test:tests/test_exit_codes.py#test_unparsable_export_is_dataerr @test:tests/test_exit_codes.py#test_missing_token_is_config @test:tests/test_exit_codes.py#test_rate_limit_is_unavailable
  Scenario Outline: Each expected failure stops the audit with its own exit status
    Given <situation>
    When the operator runs toil-audit <source>
    Then a message starting "toil-audit:" is printed on standard error
    And the exit status is <status>
    And no report is written

    Examples:
      | situation                                          | source                | status |
      | the export file nope.json does not exist           | on nope.json          | 66     |
      | the export file runs.json does not contain JSON    | on runs.json          | 65     |
      | neither GITHUB_TOKEN nor GH_TOKEN is set           | with --repo acme/shop | 78     |
      | GitHub rate-limits the fetch and the tool gives up | with --repo acme/shop | 69     |

  @id:command-line.errors-exit-codes.002 @rule:command-line.errors.empty-history-is-not-zero-toil @verified @source:toilaudit/__main__.py#main @test:tests/test_exit_codes.py#test_export_with_no_runs_is_dataerr
  Scenario Outline: History with no completed runs is reported as nothing to audit, never as zero cost
    Given the export "<file>" contains <content>
    When the operator runs toil-audit on <file>
    Then "toil-audit: no completed runs in <file> — nothing to audit" is printed on standard error
    And the exit status is 65
    And no report and no "0.00 EUR" figure is produced

    Examples:
      | file       | content                   |
      | empty.json | nothing at all            |
      | null.json  | JSON with no list of runs |

  @id:command-line.errors-exit-codes.003 @rule:command-line.output.report-to-stdout-or-file @verified @source:toilaudit/__main__.py#main @test:tests/test_compare.py#test_a_clean_last_month_is_the_headline_and_in_the_trend
  Scenario Outline: The report goes to standard output, or to the named file with a one-line total
    Given the operator has a workflow-runs export "runs.json" with toil in it
    When the operator runs toil-audit on runs.json <output option>
    Then <where the report goes>
    And <what standard output shows>
    And the exit status is 0

    Examples:
      | output option         | where the report goes                             | what standard output shows                 |
      | with no output option | the Markdown report is printed on standard output | the full report, including the bottom line |
      | with --out report.md  | the Markdown report is written to report.md       | "Wrote report.md — total toil <total> EUR" |
