"""CLI: python -m toilaudit runs.json [--rate 75] [--out report.md]"""

import argparse
import sys

from .costing import summarize_costs
from .ingest import LOADERS
from .report import build_report
from .signals import detect_signals
from .slack import (
    DeliveryError,
    build_message,
    load_state,
    post,
    save_state,
    webhook_from_env,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="toil-audit",
        description="Quantify CI/CD babysitting cost in euros from a workflow-runs export.",
    )
    parser.add_argument(
        "runs_json",
        help="gh api 'repos/O/R/actions/runs' --paginate, "
        "or glab api 'projects/:id/pipelines' --paginate",
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
        "--slack",
        metavar="REPO",
        help="post the figure, its week-over-week delta and the top signals to "
        "Slack, labelled with REPO. The webhook comes from "
        "TOIL_AUDIT_SLACK_WEBHOOK (or SLACK_WEBHOOK_URL) in the environment — "
        "never a flag, because the URL is the credential",
    )
    parser.add_argument(
        "--state",
        default=".toilaudit-weekly.json",
        help="where last week's figure is kept, for the delta (default "
        ".toilaudit-weekly.json)",
    )
    args = parser.parse_args(argv)

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

    if args.slack:
        # After the report is on disk: a delivery failure must never be the
        # reason the week's audit is lost.
        webhook = webhook_from_env()
        if not webhook:
            print(
                "toil-audit: --slack given but TOIL_AUDIT_SLACK_WEBHOOK is not set",
                file=sys.stderr,
            )
            return 2
        state = load_state(args.state)
        try:
            post(webhook, build_message(args.slack, summary, state))
        except DeliveryError as err:
            print(f"toil-audit: {err}", file=sys.stderr)
            print("toil-audit: the report is unaffected", file=sys.stderr)
            return 3
        # Only after a successful post: a failed delivery must not move the
        # baseline, or next week's delta would compare against a figure nobody
        # ever saw.
        state[args.slack] = {"total_eur": summary.total_eur}
        save_state(state, args.state)
        print(f"toil-audit: posted {args.slack} to Slack")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
