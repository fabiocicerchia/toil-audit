@domain:toil-detection @area:failure-triage @from:toilaudit/signals
Feature: Pricing failure triage
  Charges engineering leads for the time people actually spent on broken commits, measured from the timeline rather than assumed, so the euro figure holds up.

  Background:
    Given each failed run is charged the runner time it used

  @id:toil-detection.failure-triage.001 @rule:toil.triage.once-per-broken-commit @verified @source:toilaudit/signals.py#detect_signals @test:tests/test_toilaudit.py#test_one_broken_commit_is_triaged_once
  Scenario: A broken commit is triaged once however many workflows fail on it
    Given workflows "CI", "lint" and "security" in repository acme/shop each failed on commit dead01, each after 10 minutes
    When the operator audits the run history
    Then exactly one of the three failures is charged engineer time
    And the other two show "(same commit, already triaged)" and are charged no engineer time
    And all three failures together are charged 30 minutes of runner time

  @id:toil-detection.failure-triage.002 @rule:toil.triage.priced-from-next-push @verified @source:toilaudit/signals.py#_triage_minutes @test:tests/test_toilaudit.py#test_fast_fix_bills_the_observed_gap_not_the_estimate @test:tests/test_toilaudit.py#test_slow_fix_is_capped_at_the_estimate
  Scenario Outline: Triage is priced from the time until the next push, floored at a glance and capped at the estimate
    Given a run on branch main failed on commit bad
    And a person pushed a new commit to main <gap> after the failed run finished
    When the operator audits the run history
    Then the failure is charged <charged> engineer minutes
    And the incident shows "next push <shown> min later"

    Examples:
      | gap        | charged | shown |
      | 3 minutes  | 3       | 3     |
      | 20 seconds | 1       | 0     |
      | one day    | 8       | 1440  |

  @id:toil-detection.failure-triage.003 @rule:toil.triage.unfixed-or-bot-fixed-is-a-glance @verified @source:toilaudit/signals.py#_triage_minutes @test:tests/test_toilaudit.py#test_never_fixed_means_nobody_triaged_it @test:tests/test_toilaudit.py#test_bot_pushing_over_its_own_branch_is_not_triage @test:tests/test_toilaudit.py#test_jenkins_push_actor_is_the_change_author
  Scenario Outline: A failure nobody fixed, or that only a bot pushed over, costs a glance
    Given a run on branch <branch> failed
    And <follow-up>
    When the operator audits the run history
    Then the failure is charged 1 engineer minute
    And the incident shows "<reason>"

    Examples:
      | branch       | follow-up                                                     | reason                                         |
      | main         | no later commit was ever pushed to main                       | never fixed, nobody looked                     |
      | dependabot/x | dependabot[bot] pushed a new commit 14 minutes later          | not a human, dependabot[bot] pushed over it    |
      | main         | a new commit with no named author was pushed 14 minutes later | not a human, an unnamed trigger pushed over it |
