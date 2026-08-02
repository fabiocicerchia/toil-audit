# toil-audit

[![CI](https://github.com/fabiocicerchia/toil-audit/actions/workflows/code-quality.yml/badge.svg)](https://github.com/fabiocicerchia/toil-audit/actions/workflows/code-quality.yml)
[![Security](https://github.com/fabiocicerchia/toil-audit/actions/workflows/security.yml/badge.svg)](https://github.com/fabiocicerchia/toil-audit/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/fabiocicerchia/toil-audit/badge)](https://securityscorecards.dev/viewer/?uri=github.com/fabiocicerchia/toil-audit)


Analyzes CI/CD run history and **quantifies the cost of manual pipeline
babysitting in euros** — the number that turns "our CI is flaky" into a
budget conversation.

> Positioning: consulting-tool-first. Run it against a prospect's repo and
> open the engagement with "your pipelines cost you €X/month in engineer
> time". The SaaS version is the same audit, continuously.

## Toil signals & assumptions

| Signal | What happened | Engineer time (default) |
|---|---|---|
| Manual re-run | `run_attempt > 1` — someone pressed re-run and waited | 10 min |
| Flaky red→green | same commit fails then passes with no new push | 15 min |
| Manual dispatch | `workflow_dispatch` — a human is the scheduler | 5 min |
| Queue stall | run queued > 15 min — two context switches | 6 min |
| Failure triage | every failed run gets its logs read | 8 min |

Engineer cost uses a loaded rate (default **€75/h**); wasted runner minutes
(failed runs, repeat attempts) are priced separately at the GitHub-hosted
runner rate (default €0.0074/min). Every number is a CLI flag — the audit
is only as credible as its assumptions are defensible.

## Run it

```bash
# export the run history (any repo you can read):
gh api 'repos/OWNER/REPO/actions/runs?per_page=100' --paginate > runs.json

# no dependencies beyond the standard library:
python -m toilaudit runs.json --rate 85 --out toil-report.md

# or try the bundled sample:
python -m toilaudit data/sample_runs.json
```

Output: a Markdown report with the bottom-line €, a per-signal cost table,
the costliest workflows, and sample incidents to point at in the meeting.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Roadmap to product

- [ ] GitLab CI and Jenkins ingestion.
- [ ] Pull logs directly via the API instead of a JSON export.
- [ ] Trend mode: monthly toil delta after fixes land (prove the ROI).
- [ ] Flaky-test attribution: which test file causes the red→green loops.
- [ ] Scheduled SaaS: weekly toil report per repo, Slack delivery.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go through
[GitHub Security Advisories](https://github.com/fabiocicerchia/toil-audit/security/advisories/new),
never a public issue — see [SECURITY.md](SECURITY.md).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
