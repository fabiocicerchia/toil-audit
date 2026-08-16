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

The [README](../README.md) covers what toil-audit does and why.

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
