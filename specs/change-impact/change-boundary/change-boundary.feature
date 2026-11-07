@domain:change-impact @area:change-boundary @from:toilaudit/compare
Feature: Naming the change a comparison is split at
  Lets an engineering lead say exactly when a fix landed, by date or by commit, so the before/after figures are attributed to that change and nothing nearby.

  Background:
    Given an export of CI run history for the repository

  @id:change-impact.change-boundary.001 @rule:change-impact.change-boundary.date-or-first-run-of-commit @verified @source:toilaudit/compare.py#resolve_boundary @test:tests/test_compare.py#test_boundary_by_date_or_by_the_commit_a_fix_landed_in @test:tests/test_compare.py#test_the_report_states_an_increase
  Scenario Outline: The change is placed at the named date or at the first run of the named commit
    Given runs built from commit fffffff… started on 2026-03-02 09:00 UTC and again on 2026-03-04 09:00 UTC
    When the operator runs the audit with --change <change>
    Then the report has a section headed "Before and after <heading date>"
    And the change is placed at <boundary>

    Examples:
      | change     | boundary                                           | heading date |
      | 2026-03-10 | 2026-03-10 00:00 UTC                               | 2026-03-10   |
      | fffffff    | 2026-03-02 09:00 UTC, the first run of that commit | 2026-03-02   |

  @id:change-impact.change-boundary.002 @rule:change-impact.change-boundary.unresolvable-change-refused @verified @source:toilaudit/compare.py#resolve_boundary @test:tests/test_compare.py#test_boundary_by_date_or_by_the_commit_a_fix_landed_in @test:tests/test_compare.py#test_a_sha_prefix_matching_two_commits_is_refused @test:tests/test_compare.py#test_an_unknown_commit_is_refused_rather_than_guessed
  Scenario Outline: A change that cannot be pinned to one point is refused rather than guessed
    Given no run in the export was built from commit 1234567
    And runs were built from two commits whose shas both start with abcdef1
    When the operator runs the audit with --change <change>
    Then the audit stops with a usage error and no report
    And the error says "--change: <message>"

    Examples:
      | change       | message                                                      |
      | last tuesday | 'last tuesday' is neither a YYYY-MM-DD date nor a commit sha |
      | abc12        | 'abc12' is neither a YYYY-MM-DD date nor a commit sha        |
      | 1234567      | no run in this export was built from commit 1234567          |
      | abcdef1      | abcdef1 matches more than one commit; give more of the sha   |
