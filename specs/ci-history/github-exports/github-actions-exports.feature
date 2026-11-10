@domain:ci-history @area:github-exports @from:toilaudit/ingest
Feature: Reading GitHub Actions exports
  Lets an operator audit a repository from a saved GitHub Actions run export, with the same result a live fetch would give.

  Background:
    Given the operator has exported workflow runs from GitHub Actions

  @id:ci-history.github-exports.001 @rule:ci-history.exports.paginated-pages-read-as-one @verified @source:toilaudit/ingest.py#_load_json_pages @test:tests/test_toilaudit.py#test_paginated_concatenation @test:tests/test_toilaudit.py#test_gitlab_accepts_concatenated_pages @test:tests/test_toilaudit.py#test_jenkins_concatenated_job_documents_are_one_export @test:tests/test_toilaudit.py#test_jenkins_builds_key_is_accepted_as_well_as_allbuilds
  Scenario Outline: An export made of several concatenated pages is read as one export
    Given a <provider> export file holding <documents> documents written back to back, as paginated export tools produce them
    When the operator analyses the export
    Then every run from every document is counted, <runs> runs in total

    Examples:
      | provider | documents                                     | runs |
      | github   | 2                                             | 2    |
      | gitlab   | 2                                             | 3    |
      | jenkins  | 2 (one listing allBuilds, one listing builds) | 2    |
