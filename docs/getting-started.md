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
| 65   | the export could not be parsed                                     |
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

## Weekly report into Slack

The audit otherwise runs when someone remembers, which is the manual
babysitting this tool exists to price. `.github/workflows/weekly-toil.yml`
runs it every Monday at 07:00 UTC and posts the figure:

> **owner/repo** — EUR 412.30 (+18% vs last week)
> • Flaky Recovery — EUR 168.75 (9 events)
> • Rerun — EUR 125.00 (10 events)
> • Queue Stall — EUR 22.50 (3 events)

```sh
python -m toilaudit --repo owner/name --since 2026-08-09 \
  --out report.md --slack owner/name
```

Monday morning on purpose: the number lands before anyone has decided what to
work on, and a Friday report is read on Monday anyway, by which time it
describes the week before last.

**The webhook is a credential.** Anyone holding that URL can post as the app,
so it comes from `TOIL_AUDIT_SLACK_WEBHOOK` in the environment — there is no
`--webhook` flag, because a flag is visible in `ps` and in the command line CI
prints into its own logs. Failures name the *host*, never the URL, and there is
a test asserting the secret does not appear in an error message.

**A failed post never loses the report.** The markdown is written to disk
before anything is sent, uploaded as an artifact with `if: always()`, and a
delivery failure exits 3 with the report intact rather than failing the audit.

Delivery retries transport errors and 5xx. A 4xx is not retried: the webhook is
wrong or revoked, and repeating it neither fixes that nor tells anyone.

**The week-over-week delta** needs last week's figure, kept in
`.toilaudit-weekly.json` (cached between runs). The baseline is only updated
after a *successful* post, so next week never compares against a figure nobody
saw. A first run says "first report" rather than printing +100%, and a missing
or corrupt state file costs the comparison, not the report.

Repos and cadence are inputs: edit the `cron`, or run the workflow by hand with
a space-separated repo list.
