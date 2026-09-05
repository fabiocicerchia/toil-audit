# toil-audit

[![CI](https://github.com/fabiocicerchia/toil-audit/actions/workflows/code-quality.yml/badge.svg)](https://github.com/fabiocicerchia/toil-audit/actions/workflows/code-quality.yml)
[![Security](https://github.com/fabiocicerchia/toil-audit/actions/workflows/security.yml/badge.svg)](https://github.com/fabiocicerchia/toil-audit/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/fabiocicerchia/toil-audit/badge)](https://securityscorecards.dev/viewer/?uri=github.com/fabiocicerchia/toil-audit)
[![CI carbon](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/fabiocicerchia/toil-audit/gh-pages/badge.json)](.github/workflows/carbon-badge.yml)

Analyzes CI/CD run history and **quantifies the cost of manual pipeline
babysitting in euros** — the number that turns "our CI is flaky" into a
budget conversation.

## Toil signals & assumptions

| Signal          | What happened                                              | Engineer time (default) |
| --------------- | ---------------------------------------------------------- | ----------------------- |
| Manual re-run   | `run_attempt > 1` — someone pressed re-run and waited      | 10 min                  |
| Flaky red→green | same commit fails then passes with no new push             | 15 min                  |
| Manual dispatch | `workflow_dispatch` — a human is the scheduler             | 5 min                   |
| Queue stall     | run queued > 15 min — two context switches                 | 6 min                   |
| Failure triage  | logs read once per broken commit, not per red check        | 8 min                   |
| Approval gate   | `action_required` — the run is parked until a human clicks | 5 min                   |

Engineer cost uses a loaded rate (default **€75/h**); wasted runner minutes
(failed runs, repeat attempts) are priced separately at the GitHub-hosted
runner rate (default €0.0074/min). Every number is a CLI flag — the audit
is only as credible as its assumptions are defensible.

## Run it

```bash
# straight from the API — no export step, so this can run on a schedule:
export GITHUB_TOKEN=...            # environment only, never a flag
python -m toilaudit --repo OWNER/REPO --since 2026-07-01 --out toil-report.md

# pages are cached under .toilaudit-cache, so re-analysing costs nothing
python -m toilaudit --repo OWNER/REPO --since 2026-07-01 --rate 85
```

Or from an export, which is still the right thing for a one-off audit:

```bash
# export the run history (any repo you can read):
gh api 'repos/OWNER/REPO/actions/runs?per_page=100' --paginate > runs.json

# no dependencies beyond the standard library:
python -m toilaudit runs.json --rate 85 --out toil-report.md

# or every repo of an org/user — concatenated exports load as one dataset:
gh repo list OWNER --limit 200 --json nameWithOwner -q '.[].nameWithOwner' \
  | xargs -I{} gh api 'repos/{}/actions/runs?per_page=100' --paginate > org-runs.json

python -m toilaudit org-runs.json --out org-toil-report.md

# attribute flaky recoveries to the test that caused them (logs on disk):
gh run download <run-id> --dir logs/   # or: gh api .../logs > logs/<run-id>.zip
python -m toilaudit runs.json --attribute-logs logs/

# or try the bundled sample:
python -m toilaudit data/sample_runs.json

# GitLab CI:
glab api 'projects/:id/pipelines?per_page=100' --paginate > pipelines.json
python -m toilaudit pipelines.json --provider gitlab
```

**GitLab note.** GitLab has no run-attempt counter — pressing "retry" creates a
*new pipeline on the same commit* — so attempts are derived by grouping
pipelines on (project, sha, ref) in creation order. The list endpoint also
omits `started_at`/`finished_at`; without them queue time reads as zero rather
than being invented. Export from `/pipelines/:id` if you want real queue
figures.

Org mode aggregates by workflow *name*, so identically named workflows
(`CI`, `release`) merge across repos in the costliest-workflows table.

Output: a Markdown report with the bottom-line €, a per-signal cost table,
the costliest workflows, and sample incidents to point at in the meeting.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Install

```sh
git clone https://github.com/fabiocicerchia/toil-audit.git
cd toil-audit
pip install -e .
```

## Usage

```sh
python -m toilaudit --help
```

## Documentation

Full docs live in [`docs/`](docs/). Runnable examples live in [`examples/`](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go through
[GitHub Security Advisories](https://github.com/fabiocicerchia/toil-audit/security/advisories/new),
never a public issue — see [SECURITY.md](SECURITY.md).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
