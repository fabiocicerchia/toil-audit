@domain:ci-history @area:gitlab-exports @from:toilaudit/ingest
Feature: Reading GitLab CI pipeline exports
  Lets a GitLab team get the same toil audit as GitHub users, by mapping pipeline statuses, sources and retries onto the same signals.

  Background:
    Given Given the operator has exported pipelines from GitLab CI

  @id:ci-history.gitlab-exports.001 @rule:ci-history.gitlab.retry-is-next-pipeline-on-same-commit @verified @source:toilaudit/ingest.py#load_gitlab_runs @test:tests/test_toilaudit.py#test_gitlab_derives_run_attempts_from_repeated_commits @test:tests/test_toilaudit.py#test_gitlab_runs_flow_through_the_signal_detectors
  Scenario: A second pipeline on the same commit and branch counts as a retry
    Given pipeline 11 on commit abc of main in acme/widgets failed
    And pipeline 12 on the same commit and branch was created ten minutes later
    And pipeline 13 ran on a different commit
    When the operator analyses the export
    Then pipeline 11 is attempt 1
    And pipeline 12 is attempt 2 and shows up as a rerun
    And pipeline 13 is attempt 1

  @id:ci-history.gitlab-exports.002 @rule:ci-history.gitlab.status-maps-to-outcome @verified @source:toilaudit/ingest.py#_to_gitlab_run @test:tests/test_toilaudit.py#test_gitlab_vocabulary_maps_onto_the_detectors
  Scenario Outline: GitLab pipeline statuses are read as the matching run outcome
    Given a pipeline with status <status>
    When the operator analyses the export
    Then the run's outcome is <outcome>

    Examples:
      | status   | outcome                                |
      | success  | success                                |
      | failed   | failure                                |
      | canceled | cancelled                              |
      | manual   | action_required (waiting for a person) |
      | skipped  | skipped                                |

  @id:ci-history.gitlab-exports.003 @rule:ci-history.gitlab.source-maps-to-trigger @verified @source:toilaudit/ingest.py#_to_gitlab_run @test:tests/test_toilaudit.py#test_gitlab_vocabulary_maps_onto_the_detectors @questionable
  Scenario Outline: Pipelines started from the UI, the API or a trigger token count as manual triggers
    Given a pipeline whose source is <source>
    When the operator analyses the export
    Then the run's trigger is <trigger>

    Examples:
      | source              | trigger                    |
      | push                | push                       |
      | merge_request_event | pull_request               |
      | schedule            | schedule                   |
      | web                 | workflow_dispatch (manual) |
      | api                 | workflow_dispatch (manual) |
      | trigger             | workflow_dispatch (manual) |

  @id:ci-history.gitlab-exports.004 @rule:ci-history.gitlab.repository-from-pipeline-url @verified @source:toilaudit/ingest.py#_gitlab_repo @test:tests/test_toilaudit.py#test_gitlab_vocabulary_maps_onto_the_detectors
  Scenario Outline: A pipeline's repository is its project path, subgroups included
    Given a pipeline whose address is <url> in project <project_id>
    When the operator analyses the export
    Then the run is attributed to the repository <repo>

    Examples:
      | url                                                         | project_id | repo              |
      | https://gitlab.com/acme/widgets/-/pipelines/11              | 7          | acme/widgets      |
      | https://gitlab.example.com/group/sub/project/-/pipelines/61 | 9          | group/sub/project |
      | (none)                                                      | 7          | project-7         |
