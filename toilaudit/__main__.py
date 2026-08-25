"""CLI: python -m toilaudit runs.json [--rate 75] [--out report.md]
python -m toilaudit --repo owner/name [--since 2026-07-01]
"""

import argparse
from pathlib import Path

from .attribute import attribute, logs_from_zip
from .costing import summarize_costs
from .fetch import fetch_github_runs
from .ingest import LOADERS, runs_from_objects
from .report import build_report
from .signals import detect_signals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="toil-audit",
        description="Quantify CI/CD babysitting cost in euros from a workflow-runs export.",
    )
    parser.add_argument(
        "runs_json",
        nargs="?",
        help="gh api 'repos/O/R/actions/runs' --paginate, "
        "or glab api 'projects/:id/pipelines' --paginate",
    )
    parser.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help="fetch the history from the GitHub API instead of an export. The "
        "token comes from GITHUB_TOKEN or GH_TOKEN in the environment — "
        "never a flag",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="with --repo: only runs created on or after this date",
    )
    parser.add_argument(
        "--cache-dir",
        default=".toilaudit-cache",
        help="where fetched pages are cached so re-analysis does not re-fetch "
        "(default .toilaudit-cache)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="with --repo: always fetch, do not read or write the cache",
    )
    parser.add_argument(
        "--provider",
        choices=sorted(LOADERS),
        default="github",
        help="CI system the export came from (default github)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=75.0,
        help="loaded engineer hourly rate in EUR (default 75)",
    )
    parser.add_argument(
        "--runner-rate",
        type=float,
        default=0.0074,
        help="runner cost in EUR per minute (default 0.0074)",
    )
    parser.add_argument(
        "--out", help="write the Markdown report here instead of stdout"
    )
    parser.add_argument(
        "--attribute-logs",
        metavar="DIR",
        help="attribute flaky recoveries to the test that caused them, reading "
        "each failed run's log from DIR/<run_id>.txt (or .zip, as the API "
        "serves them). Log content is used for matching only — no excerpt "
        "reaches the report",
    )
    args = parser.parse_args(argv)

    if bool(args.repo) == bool(args.runs_json):
        parser.error("give either an export file or --repo, not both")

    if args.repo:
        raw = fetch_github_runs(
            args.repo,
            created=f">={args.since}" if args.since else "",
            cache_dir=None if args.no_cache else args.cache_dir,
        )
        runs = runs_from_objects(raw)
    else:
        runs = LOADERS[args.provider](args.runs_json)
    signals = detect_signals(runs)
    summary = summarize_costs(signals, args.rate, args.runner_rate)
    attribution = None
    if args.attribute_logs:
        attribution = attribute(
            [s for s in signals if s.kind == "FLAKY_RECOVERY"],
            lambda sig: _read_log(args.attribute_logs, sig.run.run_id),
            lambda sig: sig.engineer_minutes / 60.0 * args.rate,
        )

    report = build_report(runs, signals, summary, args.rate, attribution)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(report + "\n")
        print(f"Wrote {args.out} — total toil {summary.total_eur:,.2f} EUR")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _read_log(directory, run_id):
    """One run's log from a directory, as text.

    Files rather than a live download: the logs endpoint is a separate scope
    and a large transfer, and an audit that already has the logs on disk (gh
    run download, or a CI artifact) should not need either. Accepts the zip
    the API serves and a plain .txt, so both work without unpacking anything.
    """
    base = Path(directory) / str(run_id)
    for suffix in (".txt", ".log"):
        path = base.with_suffix(suffix)
        if path.exists():
            return path.read_text(errors="replace")
    zipped = base.with_suffix(".zip")
    if zipped.exists():
        return logs_from_zip(zipped.read_bytes())
    return ""
