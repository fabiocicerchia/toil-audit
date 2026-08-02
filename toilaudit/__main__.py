"""CLI: python -m toilaudit runs.json [--rate 75] [--out report.md]"""

import argparse

from .costing import summarize_costs
from .ingest import load_runs
from .report import build_report
from .signals import detect_signals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="toil-audit",
        description="Quantify CI/CD babysitting cost in euros from a workflow-runs export.",
    )
    parser.add_argument("runs_json", help="output of: gh api 'repos/O/R/actions/runs' --paginate")
    parser.add_argument("--rate", type=float, default=75.0,
                        help="loaded engineer hourly rate in EUR (default 75)")
    parser.add_argument("--runner-rate", type=float, default=0.0074,
                        help="runner cost in EUR per minute (default 0.0074)")
    parser.add_argument("--out", help="write the Markdown report here instead of stdout")
    args = parser.parse_args(argv)

    runs = load_runs(args.runs_json)
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
