# Getting Started

## Install

```sh
git clone https://github.com/fabiocicerchia/toil-audit.git
cd toil-audit
pip install -e .
```

## First run

```sh
python -m toilaudit --help
```

The [README](README.md) covers what toil-audit does and why.

## Exit codes

Scheduled runs need to tell "the audit failed" from "the audit ran", so each
expected failure has its own code from `sysexits(3)` rather than a blanket 1:

| Code | Meaning                                                            |
| ---- | ------------------------------------------------------------------ |
| 0    | the report was written                                             |
| 2    | argparse rejected the command line                                 |
| 65   | the export could not be parsed, or held no completed runs          |
| 66   | the export file does not exist                                     |
| 69   | the GitHub API rate-limited the fetch and waiting did not clear it |
| 78   | no `GITHUB_TOKEN` (or `GH_TOKEN`) in the environment               |

Anything else is a bug in toil-audit and still exits with a traceback.

## Naming the flaky test

`FLAKY_RECOVERY` prices the fail-then-pass loop from run metadata alone, which
gives you a number and no name. "Flaky tests cost EUR 4,200" is a slide;
"`tests/test_orders.py` cost EUR 1,900 of it" is a ticket.

Point `--attribute-logs` at a directory of failed-run logs — `<run_id>.txt` or
the `.zip` the API serves, both work:

```sh
gh run download 12345678 --dir logs/
python -m toilaudit runs.json --attribute-logs logs/
```

```text
## Flaky recoveries by test file

| test file              | attributed cost |
| ---------------------- | --------------: |
| `tests/test_orders.py` | EUR 37.50       |

7 recovery(ies) worth EUR 131.25 could not be attributed …
```

Two properties worth knowing, because they are what make the ranking
trustworthy:

**It partitions the existing total, never inflates it.** The attributed and
unattributed figures add back up to the Flaky row in the summary table above
them. A recovery whose cause no pattern matched is counted as unattributed —
never spread across the files that *were* identified, and never dropped.

**Log content is used for matching only.** No excerpt reaches the report. A
failing job echoes whatever the failure printed, which routinely includes
tokens and connection strings; what survives is the test identity — a path and
a test name.

A run naming several failing tests splits its cost evenly between them. The
metadata says one recovery happened, not which of the three failures cost the
time, so any other weighting would be inventing evidence.

Recognised: pytest, go test, jest/vitest, rspec and JUnit XML. Paths outside
the repo (`site-packages`, `node_modules`, absolute paths) are ignored — a
dependency's own failing test is not your flaky test.

## Jenkins

Jenkins returns almost nothing from `api/json` unless asked, so name the fields.
One job:

`curl -u` sends the token in the clear unless `JENKINS_URL` is `https://`.

```sh
TREE='allBuilds[number,queueId,result,timestamp,duration,url,actions[causes[_class,userId],lastBuiltRevision[SHA1,branch[name]],remoteUrls,queuingDurationMillis],changeSets[items[msg,author[fullName]]]]'
curl -fsS -u "$JENKINS_USER:$JENKINS_TOKEN" -G \
  --data-urlencode "tree=$TREE" "$JENKINS_URL/job/widgets/job/main/api/json" > builds.json
python -m toilaudit builds.json --provider jenkins
```

Several jobs go into one file by appending each job's document to it (`>>`);
the documents are read one after another. For a multibranch pipeline, export
each branch job (`job/widgets/job/main`, `job/widgets/job/PR-7`, …).

`allBuilds` rather than `builds`, which stops at the newest 100. What each
field becomes:

- `result` — `SUCCESS`, `FAILURE`, `UNSTABLE` (counted as a failure), `ABORTED`
  (cancelled), `NOT_BUILT` (skipped). A build still running is left out.
- causes — a user-started build (including Replay and Rebuild) is a manual
  dispatch, a timer is a schedule, an SCM or branch event is a push, and a
  multibranch job named `PR-<n>` is a pull request. The user who started a
  build is its actor; for any other build it is the first change's author, so a
  push by `dependabot[bot]` is a bot's and a person's push is a person's.
- `lastBuiltRevision` and `remoteUrls`, from the git plugin, give the sha, the
  branch and the repository. Without them the job's folder stands in for the
  repository and the build is never counted as a retry.
- `queuingDurationMillis` comes from the Metrics plugin. Without it, queue time
  is zero rather than invented.
- `queueId` is the run id, because build numbers repeat across jobs; name log
  files for `--attribute-logs` after it.

`data/sample_jenkins.json` is a worked example of the shape.

## Fetching from the API

The export step is what stopped this being scheduled. `--repo` fetches the run
history directly:

```sh
export GITHUB_TOKEN=...
python -m toilaudit --repo OWNER/REPO --since 2026-07-01 --out report.md
```

**The token is read from the environment only** — `GITHUB_TOKEN` or `GH_TOKEN`.
There is deliberately no `--token` flag: a flag is visible in shell history, in
`ps`, and in the command line CI prints into its own logs. It is never logged
and never written to the cache.

**Rate limits are a pause, not a failure.** A 403 or 429 carrying
`X-RateLimit-Remaining: 0` is waited out until `X-RateLimit-Reset`, and the
fetch resumes on the page it stopped on — nothing already fetched is lost and
nothing is skipped. After a few waits it gives up rather than looping.

**Pages are cached** under `--cache-dir` (default `.toilaudit-cache`), keyed by
URL, so re-analysing the same window makes no requests at all. `--no-cache`
forces a fresh fetch.

`--since` becomes the API's own `created` filter, so a narrow window costs
fewer requests rather than being trimmed after the fact. Note the listing
endpoint caps at 1000 runs however you paginate it.
