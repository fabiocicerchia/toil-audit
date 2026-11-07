@domain:ci-history @area:run-normalisation @from:toilaudit/ingest
Feature: Normalising CI runs before costing
  Gives a finance or platform owner a euro figure built only from finished runs with credible timings, whatever CI system produced them.

  @id:ci-history.run-normalisation.001 @rule:ci-history.runs.unfinished-runs-excluded @verified @source:toilaudit/ingest.py#runs_from_objects @test:tests/test_toilaudit.py#test_in_progress_runs_skipped @test:tests/test_toilaudit.py#test_gitlab_derives_run_attempts_from_repeated_commits @test:tests/test_toilaudit.py#test_jenkins_derives_attempts_from_builds_of_one_commit @test:tests/test_fetch.py#test_api_and_export_agree_over_the_same_period
  Scenario Outline: Runs that have not finished are left out of the audit
    Given a <provider> export containing a run whose state is <state>
    When the operator analyses the export
    Then that run does not appear in the audit

    Examples:
      | provider | state                               |
      | github   | status in_progress                  |
      | gitlab   | status running                      |
      | jenkins  | result not yet set (still building) |

  @id:ci-history.run-normalisation.002 @rule:ci-history.runs.duration-capped-at-six-hours @inferred @source:toilaudit/ingest.py#Run @questionable
  Scenario: No run is charged more than six hours of runner time
    Given a GitHub run that started on 2025-06-18 at 21:29 and whose record was last touched on 2026-07-25
    When the operator analyses the export
    Then the run's duration counts as 6 hours, not 400 days

  @id:ci-history.run-normalisation.003 @rule:ci-history.runs.unmeasured-queue-time-is-zero @verified @source:toilaudit/ingest.py#_to_gitlab_run @test:tests/test_toilaudit.py#test_gitlab_timings_and_missing_detail_fields @test:tests/test_toilaudit.py#test_jenkins_timings
  Scenario Outline: Queue time the export does not record is counted as zero, not estimated
    Given a <provider> run that <missing>
    When the operator analyses the export
    Then the run's queue time is 0 seconds
    And its duration is measured from <from> to <to>

    Examples:
      | provider | missing                                                      | from        | to                            |
      | gitlab   | comes from the pipeline list, without start and finish times | creation    | last update                   |
      | jenkins  | has no Metrics plugin queuing duration                       | build start | build start plus its duration |

  @id:ci-history.run-normalisation.004 @rule:ci-history.runs.bot-actors-are-not-people @verified @source:toilaudit/ingest.py#Run @test:tests/test_toilaudit.py#test_gitlab_vocabulary_maps_onto_the_detectors @test:tests/test_toilaudit.py#test_jenkins_vocabulary_maps_onto_the_detectors
  Scenario Outline: A run started by a bot account is not treated as a person's
    Given a run triggered by the account <actor>
    When the operator analyses the export
    Then the run counts as started by a person: <human>

    Examples:
      | actor           | human |
      | fabio           | yes   |
      | dependabot[bot] | no    |
      | (nobody named)  | no    |
