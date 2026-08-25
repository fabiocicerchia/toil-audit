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
