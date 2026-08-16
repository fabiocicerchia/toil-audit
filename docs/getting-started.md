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

```
## Flaky recoveries by test file

| test file | attributed cost |
|---|---:|
| `tests/test_orders.py` | EUR 37.50 |

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
