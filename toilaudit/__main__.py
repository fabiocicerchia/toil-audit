"""CLI: python -m toilaudit runs.json [--rate 75] [--out report.md]
python -m toilaudit --repo owner/name [--since 2026-07-01]
"""

import argparse

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
    report = build_report(runs, signals, summary, args.rate)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(report + "\n")
        print(f"Wrote {args.out} — total toil {summary.total_eur:,.2f} EUR")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
