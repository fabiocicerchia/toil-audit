@domain:flaky-attribution @area:log-sources @from:toilaudit/toilaudit
Feature: Reading failed-run logs for flaky attribution
  Lets an operator attribute flaky recoveries to tests from logs already on disk, without a live download.

  Background:
    Given the operator has a workflow-runs export with flaky recoveries

  @id:flaky-attribution.log-sources.001 @rule:flaky-attribution.logs.read-from-directory-by-run-id @inferred @source:toilaudit/__main__.py#_read_log @questionable
  Scenario Outline: Each failed run's log is read from the log directory by run id, as text or as the zip the API serves
    Given the log directory "logs" holds the failed run 4242's log as "<file>"
    When the operator runs toil-audit on the export with --attribute-logs logs
    Then the flaky recovery of run 4242 is attributed to the failing test named in that log
    And no line of the log appears in the report

    Examples:
      | file     |
      | 4242.txt |
      | 4242.log |
      | 4242.zip |
