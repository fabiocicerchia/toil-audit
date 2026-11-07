@domain:ci-history @area:jenkins-exports @from:toilaudit/ingest
Feature: Reading Jenkins build exports
  Lets a Jenkins team audit their toil by recovering, from build data, the repository, commit, branch, trigger, author and retries that Jenkins does not report directly.

  Background:
    Given the operator has exported builds from Jenkins

  @id:ci-history.jenkins-exports.001 @rule:ci-history.jenkins.retry-is-rebuild-of-same-commit-and-branch @verified @source:toilaudit/ingest.py#_jenkins_attempt_key @test:tests/test_toilaudit.py#test_jenkins_derives_attempts_from_builds_of_one_commit @test:tests/test_toilaudit.py#test_jenkins_same_commit_on_another_branch_is_not_a_retry @test:tests/test_toilaudit.py#test_jenkins_timer_rebuild_and_branchless_build_are_not_retries
  Scenario Outline: Only a rebuild of the same commit on the same branch in the same job counts as a retry
    Given a build of job app that failed
    And a later build of app that <second>
    When the operator analyses the export
    Then the later build is attempt <attempt>

    Examples:
      | second                                   | attempt |
      | built the same commit on the same branch | 2       |
      | built the same commit on another branch  | 1       |
      | has no git revision recorded             | 1       |
      | has a git revision but no branch         | 1       |

  @id:ci-history.jenkins-exports.002 @rule:ci-history.jenkins.timer-build-is-never-a-retry @verified @source:toilaudit/ingest.py#_jenkins_attempt @test:tests/test_toilaudit.py#test_jenkins_timer_rebuild_and_branchless_build_are_not_retries
  Scenario: A scheduled rebuild of an unchanged commit is not a retry, but a person rebuilding after it is
    Given a nightly timer builds commit abc on main two nights running
    And a person then rebuilds commit abc on main by hand, twice
    When the operator analyses the export
    Then both nightly builds are attempt 1
    And the person's rebuilds are attempts 2 and 3
    And the next nightly build is attempt 1 again

  @id:ci-history.jenkins-exports.003 @rule:ci-history.jenkins.result-maps-to-outcome @verified @source:toilaudit/ingest.py#_to_jenkins_run @test:tests/test_toilaudit.py#test_jenkins_vocabulary_maps_onto_the_detectors
  Scenario Outline: Jenkins build results are read as the matching run outcome
    Given a finished build with result <result>
    When the operator analyses the export
    Then the run's outcome is <outcome>

    Examples:
      | result    | outcome   |
      | SUCCESS   | success   |
      | FAILURE   | failure   |
      | UNSTABLE  | failure   |
      | ABORTED   | cancelled |
      | NOT_BUILT | skipped   |

  @id:ci-history.jenkins-exports.004 @rule:ci-history.jenkins.cause-maps-to-trigger @verified @source:toilaudit/ingest.py#_jenkins_event @test:tests/test_toilaudit.py#test_jenkins_vocabulary_maps_onto_the_detectors @test:tests/test_toilaudit.py#test_jenkins_runs_flow_through_the_signal_detectors
  Scenario Outline: Jenkins build causes are read as the matching trigger, and a build a person started counts as manual whatever else caused it
    Given a build of job <job> whose recorded causes are <causes>
    When the operator analyses the export
    Then the run's trigger is <trigger>

    Examples:
      | job                | causes                                | trigger                    |
      | widgets/main       | a user (Build Now, Replay or Rebuild) | workflow_dispatch (manual) |
      | widgets/main       | an SCM change and a user              | workflow_dispatch (manual) |
      | ops/nightly-backup | a timer                               | schedule                   |
      | widgets/main       | an SCM push                           | push                       |
      | widgets/PR-7       | a branch event                        | pull_request               |
      | deploy             | an upstream job                       | workflow_run               |
      | deploy             | none recognised                       | unknown                    |

  @id:ci-history.jenkins-exports.005 @rule:ci-history.jenkins.repository-and-workflow-identity @verified @source:toilaudit/ingest.py#_jenkins_repo @test:tests/test_toilaudit.py#test_jenkins_repo_and_workflow_derivation @test:tests/test_toilaudit.py#test_jenkins_slashed_branch_and_spaced_folder_are_decoded @test:tests/test_toilaudit.py#test_jenkins_git_remote_forms
  Scenario Outline: Builds are attributed to their git repository, and all branch jobs of a multibranch pipeline to one workflow
    Given a build at <job_url> that checked out <checkout>
    When the operator analyses the export
    Then the run's repository is <repo>
    And its workflow is <workflow> on branch <branch>

    Examples:
      | job_url                                                          | checkout                                           | repo         | workflow | branch    |
      | https://ci.example.com/job/acme/job/widgets/job/main/42/         | https://github.com/acme/widgets.git at origin/main | acme/widgets | widgets  | main      |
      | https://ci.example.com/job/acme/job/widgets/job/PR-7/3/          | git@github.com:acme/widgets.git at PR-7            | acme/widgets | widgets  | PR-7      |
      | https://ci.example.com/job/acme/job/widgets/job/feature%252Fx/1/ | a revision on feature/x                            | acme/widgets | widgets  | feature/x |
      | https://ci.example.com/job/My%20Folder/job/nightly/2/            | nothing                                            | My Folder    | nightly  | (none)    |

  @id:ci-history.jenkins-exports.006 @rule:ci-history.jenkins.ambiguous-checkouts-carry-no-git-data @verified @source:toilaudit/ingest.py#_jenkins_checkouts @test:tests/test_toilaudit.py#test_jenkins_two_checkouts_of_different_commits_are_no_git_data @test:tests/test_toilaudit.py#test_jenkins_same_path_on_two_hosts_is_two_checkouts
  Scenario Outline: A build that checked out more than one repository or commit is not tied to any commit
    Given a build of team/app whose checkouts are <checkouts>
    When the operator analyses the export
    Then the run's commit is <sha> and its repository is <repo>

    Examples:
      | checkouts                                                    | sha    | repo     |
      | acme/pipeline-lib at 111 and acme/app at aaa                 | (none) | team     |
      | acme/app at ccc, recorded twice                              | ccc    | acme/app |
      | acme/app on gitlab.example at aaa and acme/app on github.com | (none) | team     |
      | https and scp-style addresses of github.com/acme/app at aaa  | aaa    | acme/app |

  @id:ci-history.jenkins-exports.007 @rule:ci-history.jenkins.push-actor-is-change-author @verified @source:toilaudit/ingest.py#_jenkins_change @test:tests/test_toilaudit.py#test_jenkins_push_actor_is_the_change_author @test:tests/test_toilaudit.py#test_jenkins_repo_and_workflow_derivation
  Scenario Outline: A push-triggered build is attributed to the author of its change
    Given an SCM-triggered build whose first change was written by <author> and whose causes name no user
    When the operator analyses the export
    Then the run is attributed to <author>
    And the change's first line becomes the run's title

    Examples:
      | author          |
      | Ada             |
      | dependabot[bot] |
