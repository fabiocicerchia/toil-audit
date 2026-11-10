# Specifications of toil-audit

What this code does, one atomic Gherkin scenario per behaviour, read from the code by code-atlas.
Tags: `@verified` a test asserts it · `@inferred` read from the code only · `@gap` an entry point no test covers · `@human` written or amended by a person, never rewritten.

## Audit report

The Markdown report that presents the euro figure and how it was reached.

- **Bottom line**: [Stating the monthly toil bill](audit-report/bottom-line/monthly-toil-headline.feature) (5)
- **Cost breakdown**: [Breaking down where the toil cost comes from](audit-report/cost-breakdown/toil-cost-breakdown.feature) (3)

## Change impact

Shows whether a fix actually cut toil cost.

- **Before and after comparison**: [Comparing toil before and after a change](change-impact/before-after/before-after-comparison.feature) (4)
- **Change boundary**: [Naming the change a comparison is split at](change-impact/change-boundary/change-boundary.feature) (2)
- **Fix return on investment**: [Pricing a fix and its payback](change-impact/fix-roi/fix-roi.feature) (1)

## CI history import

Getting pipeline run history into the audit, either pulled live or read from a provider export.

- **Fetch cache and rate limits**: [Re-running and rate limits on live fetches](ci-history/fetch-cache/fetch-cache-and-rate-limits.feature) (4)
- **GitHub exports**: [Reading GitHub Actions exports](ci-history/github-exports/github-actions-exports.feature) (1)
- **GitHub live fetch**: [Fetching run history live from GitHub](ci-history/github-fetch/github-live-fetch.feature) (7)
- **GitLab exports**: [Reading GitLab CI pipeline exports](ci-history/gitlab-exports/gitlab-exports.feature) (4)
- **Jenkins exports**: [Reading Jenkins build exports](ci-history/jenkins-exports/jenkins-exports.feature) (7)
- **Run normalisation**: [Normalising CI runs before costing](ci-history/run-normalisation/run-normalisation.feature) (4)

## Command line

How a user runs an audit and gets its result.

- **Errors and exit codes**: [Audit outcomes and exit codes](command-line/errors-exit-codes/audit-outcomes-and-exit-codes.feature) (3)
- **Input selection**: [Choosing what to audit](command-line/input-selection/choosing-what-to-audit.feature) (2)

## Cost model

Turns detected toil and runner usage into euros, with every input visible and overridable.

- **Cost summary**: [Rolling up toil cost](cost-model/cost-summary/rolling-up-toil-cost.feature) (4)
- **Engineer rate**: [Pricing toil in euros](cost-model/engineer-rate/pricing-toil-in-euros.feature) (3)

## Flaky test attribution

Names the tests and test files behind flaky recoveries, using the failed runs' logs.

- **Failing-test detection**: [Recognising the failing test in a CI log](flaky-attribution/failure-parsing/failing-test-detection-patterns.feature) (7), [Recognising failing tests in CI logs](flaky-attribution/failure-parsing/failing-test-detection.feature) (1)
- **Log sources**: [Reading failed-run logs for flaky attribution](flaky-attribution/log-sources/flaky-log-sources.feature) (1)
- **Top offenders**: [Attributing flaky-recovery cost to test files](flaky-attribution/offender-ranking/flaky-cost-by-test-file.feature) (7)

## Toil detection

Finds the moments in run history where a person had to touch or wait on the pipeline.

- **Failure triage**: [Pricing failure triage](toil-detection/failure-triage/failure-triage.feature) (3)
- **Flaky recoveries**: [Detecting flaky recoveries](toil-detection/flaky-recoveries/flaky-recoveries.feature) (3)
- **Manual triggers and approvals**: [Flagging manual triggers and approval gates](toil-detection/manual-triggers/manual-triggers-approvals.feature) (1)
- **Queue stalls**: [Flagging queue stalls](toil-detection/queue-stalls/queue-stalls.feature) (1)
- **Reruns**: [Counting reruns](toil-detection/reruns/rerun-toil.feature) (2)
- **Shared-template fan-out**: [Recognising one fix pushed to many repositories](toil-detection/template-fanout/template-fanout.feature) (3)
