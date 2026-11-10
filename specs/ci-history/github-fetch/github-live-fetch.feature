@domain:ci-history @area:github-fetch @from:toilaudit/fetch
Feature: Fetching run history live from GitHub
  Lets an operator audit a repository straight from the GitHub API, on a schedule and without a hand-made export, while keeping the API token out of every log, flag and file.

  Background:
    Given the operator audits the repository "acme/shop" with a live fetch

  @id:ci-history.github-fetch.001 @rule:ci-history.github-fetch.token-from-environment-only @verified @source:toilaudit/fetch.py#token_from_env @test:tests/test_fetch.py#test_token_comes_from_the_environment_only
  Scenario Outline: The API token is taken from the environment
    Given the environment holds <variables>
    When the operator runs the audit
    Then the fetch authenticates with the token "<used>"

    Examples:
      | variables                                             | used          |
      | GITHUB_TOKEN=ghp_example_a                            | ghp_example_a |
      | GH_TOKEN=ghp_example_b                                | ghp_example_b |
      | GITHUB_TOKEN=ghp_example_a and GH_TOKEN=ghp_example_b | ghp_example_a |
      | an empty GITHUB_TOKEN and GH_TOKEN=ghp_example_b      | ghp_example_b |

  @id:ci-history.github-fetch.002 @rule:ci-history.github-fetch.missing-token-refused @verified @source:toilaudit/fetch.py#token_from_env @test:tests/test_fetch.py#test_token_comes_from_the_environment_only
  Scenario: A live fetch without a token is refused with a pointer to the environment
    Given neither GITHUB_TOKEN nor GH_TOKEN is set
    When the operator runs the audit
    Then no runs are fetched
    And the operator sees "toil-audit: no API token. Set GITHUB_TOKEN (or GH_TOKEN) — it is read from the environment only, never passed as a flag."
    And the message does not offer a --token option

  @id:ci-history.github-fetch.003 @rule:ci-history.github-fetch.token-never-persisted @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_token_is_sent_but_never_in_the_url @test:tests/test_fetch.py#test_the_cache_never_contains_the_token
  Scenario: The API token is never written into URLs or saved history
    Given GITHUB_TOKEN is set to "ghp_example_secret"
    And saving fetched history is enabled
    When the operator runs the audit
    Then the token is sent to GitHub only as a bearer credential
    And no requested address contains "ghp_example_secret"
    And no saved history file contains "ghp_example_secret"

  @id:ci-history.github-fetch.004 @rule:ci-history.github-fetch.since-filters-at-source @verified @source:toilaudit/fetch.py#fetch_github_runs @test:tests/test_fetch.py#test_since_becomes_an_api_filter_not_a_local_trim
  Scenario: Only runs created on or after the start date are fetched
    Given the operator gives the start date 2026-07-01
    When the operator runs the audit
    Then GitHub is asked only for runs created on or after 2026-07-01
    And runs created before 2026-07-01 are not in the audit

  @id:ci-history.github-fetch.005 @rule:ci-history.github-fetch.same-result-as-export @verified @source:toilaudit/fetch.py#fetch_github_runs @test:tests/test_fetch.py#test_api_and_export_agree_over_the_same_period @test:tests/test_fetch.py#test_fetch_github_runs_returns_raw_objects_for_the_shared_loader @test:tests/test_fetch.py#test_pagination_stops_on_a_short_page
  Scenario: A live fetch audits the same runs as an export of the same period
    Given GitHub holds 3 completed runs and 1 run still in progress for the period
    And an export of the same period holds the same 4 runs
    When the operator runs the audit
    Then the live fetch yields the same runs as the export
    And the run still in progress is left out of both

  @id:ci-history.github-fetch.006 @rule:ci-history.github-fetch.history-capped-at-1000-runs @inferred @source:toilaudit/fetch.py#fetch_pages @questionable
  Scenario: A live fetch covers at most the latest 1000 runs, without a warning
    Given GitHub holds 1500 runs for the period
    When the operator runs the audit
    Then only the latest 1000 runs are audited
    And the report gives no sign that older runs were left out

  @id:ci-history.github-fetch.007 @rule:ci-history.github-fetch.api-error-stops-fetch @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_other_http_errors_propagate @questionable
  Scenario: A repository GitHub cannot find stops the audit with GitHub's error
    Given the repository "acme/missing" does not exist on GitHub
    When the operator runs the audit for "acme/missing"
    Then no report is produced
    And the operator sees GitHub's "404" error as an unhandled crash, not a "toil-audit:" message
