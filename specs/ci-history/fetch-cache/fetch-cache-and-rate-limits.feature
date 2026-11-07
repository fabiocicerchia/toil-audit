@domain:ci-history @area:fetch-cache @from:toilaudit/fetch
Feature: Re-running and rate limits on live fetches
  Lets an operator re-run an audit offline at no extra API cost and survive GitHub rate limits without losing history already fetched.

  Background:
    Given the operator audits the repository "acme/shop" with a live fetch

  @id:ci-history.fetch-cache.001 @rule:ci-history.fetch-cache.rerun-is-offline @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_cache_means_the_second_run_makes_no_requests @test:tests/test_fetch.py#test_cache_key_is_per_page_not_per_repo @questionable
  Scenario: Re-running an audit over the same window makes no new requests
    Given the operator already audited "acme/shop" from 2026-07-01 with saved history enabled
    When the operator runs the same audit again
    Then no request is sent to GitHub
    And the same runs as the first audit are analysed, page for page

  @id:ci-history.fetch-cache.002 @rule:ci-history.fetch-cache.rate-limit-waits-and-resumes @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_rate_limit_waits_and_resumes_on_the_same_page
  Scenario: A rate limit pauses the fetch until the reset and loses no runs
    Given GitHub reports the rate limit as exhausted until 60 seconds from now
    When the operator runs the audit
    Then the fetch waits 61 seconds
    And it resumes from the page it was refused
    And every run of the period is audited

  @id:ci-history.fetch-cache.003 @rule:ci-history.fetch-cache.rate-limit-gives-up @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_rate_limit_gives_up_rather_than_looping_for_ever
  Scenario: A fetch that keeps hitting the rate limit gives up after three waits
    Given GitHub keeps reporting the rate limit as exhausted
    When the operator runs the audit
    Then the fetch waits at most 3 times
    And no report is produced
    And the operator sees "toil-audit: rate limited on page 1; waited 3 times already"

  @id:ci-history.fetch-cache.004 @rule:ci-history.fetch-cache.refusal-not-waited-out @verified @source:toilaudit/fetch.py#fetch_pages @test:tests/test_fetch.py#test_a_403_that_is_not_a_rate_limit_is_not_retried @questionable
  Scenario: A refusal that is not a rate limit is not waited out, but is reported as one
    Given GitHub refuses the request with 403 while 4999 requests remain
    When the operator runs the audit
    Then the fetch does not wait
    And no report is produced
    And the operator sees "toil-audit: rate limited on page 1; not waiting"
