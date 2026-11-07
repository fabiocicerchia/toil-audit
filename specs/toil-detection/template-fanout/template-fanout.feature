@domain:toil-detection @area:template-fanout @from:toilaudit/signals
Feature: Recognising one fix pushed to many repositories
  Keeps the audit from billing a single shared-template fix as many separate diagnoses when it lands in many repositories.

  Background:
    Given every failure below is later fixed by a person two hours after it

  @id:toil-detection.template-fanout.001 @rule:toil.fanout.diagnosed-once-across-repos @verified @source:toilaudit/signals.py#_fanout_followers @test:tests/test_toilaudit.py#test_one_fix_pushed_to_many_repos_is_diagnosed_once
  Scenario: The same failing fix in several repositories is billed as one diagnosis and cheap copies
    Given a commit titled "ci: fix pre-commit EOF on LICENSE" failed in 4 repositories, one minute apart
    When the operator audits the run history
    Then the first failure is charged 8 engineer minutes
    And each of the other three is charged 1 engineer minute
    And those three show "same fix pushed to several repos, diagnosed once"

  @id:toil-detection.template-fanout.002 @rule:toil.fanout.needs-same-fix-in-enough-repos @verified @source:toilaudit/signals.py#_fanout_followers @test:tests/test_toilaudit.py#test_unrelated_failures_are_not_fanout
  Scenario Outline: Failures that are not the same fix in at least three repositories are each billed in full
    Given <case>
    When the operator audits the run history
    Then each failure is charged 8 engineer minutes

    Examples:
      | case                                                                                             |
      | 4 repositories failed one minute apart on commits with different titles                          |
      | 2 repositories failed one minute apart on commits titled "ci: bump linter"                       |
      | 3 repositories failed on commits titled "ci: bump linter", each pushed 45 minutes after the last |

  @id:toil-detection.template-fanout.003 @rule:toil.fanout.requires-commit-identity @verified @source:toilaudit/signals.py#_fanout_followers @test:tests/test_toilaudit.py#test_failures_without_a_sha_are_never_fanout_copies
  Scenario: Failures that name no commit are never treated as copies of one fix
    Given Jenkins jobs without git data in 3 folders failed one minute apart, all titled "Bump the base image"
    When the operator audits the run history
    Then the audit shows three failures
    And none of them shows "same fix pushed to several repos"
