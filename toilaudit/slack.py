"""Posting the weekly figure where people already argue about it.

The audit otherwise runs when someone remembers, which is the manual-babysitting
pattern this tool exists to price. A scheduled job that posts the number into a
channel turns it into a thing people notice moving.

Four things this module is careful about, none of them the HTTP call:

**The secret never leaves the environment.** The webhook URL is a credential —
anyone holding it can post as the app — so it is read from the environment,
never taken as a flag, and never written into a log line. Errors are reported
with the host, not the URL.

**A failed post never loses the report.** The markdown is written to disk before
anything is sent. Delivery is retried, and if it still fails the run says so and
exits with the report intact, because a notification failing is not the audit
failing.

**Week-over-week needs last week's number.** It is kept in a small state file
next to the report rather than recomputed, since the previous run already did
that arithmetic and re-deriving it needs the old window's data.

**No request content in the payload.** Repo names, euro figures and signal
counts only.
"""

import json
import os
import time
import urllib.error
import urllib.request

WEBHOOK_ENV = ("TOIL_AUDIT_SLACK_WEBHOOK", "SLACK_WEBHOOK_URL")
STATE_FILE = ".toilaudit-weekly.json"


class DeliveryError(Exception):
    """The report was produced; only sending it failed."""


def webhook_from_env(env=None):
    """The Slack webhook, from the environment only.

    Not a flag: a flag is visible in shell history, in `ps`, and in the command
    line CI prints into its own logs — and this URL is the credential.
    """
    env = os.environ if env is None else env
    for name in WEBHOOK_ENV:
        if env.get(name):
            return env[name]
    return ""


def _host_of(url):
    """Just the host, for error messages. The path carries the secret."""
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0] or "the webhook host"


def load_state(path=STATE_FILE):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state, path=STATE_FILE):
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def delta_line(repo, current_eur, state):
    """`EUR 412.30 (+18% vs last week)`, or no comparison on the first run.

    A first run has nothing to compare against and says so, rather than
    printing +100% or 0% — both of which read as a real movement.
    """
    previous = (state.get(repo) or {}).get("total_eur")
    if previous is None:
        return f"EUR {current_eur:,.2f} (first report — no comparison yet)"
    if previous == 0:
        return f"EUR {current_eur:,.2f} (was EUR 0.00 last week)"
    change = (current_eur - previous) / previous * 100
    arrow = "+" if change >= 0 else ""
    return f"EUR {current_eur:,.2f} ({arrow}{change:.0f}% vs last week)"


def build_message(repo, summary, state, top=3):
    """The Slack payload: the figure, the movement, and what drove it.

    Blocks rather than a wall of text, because the figure is the thing people
    should see without opening anything.
    """
    lines = [line for line in summary.lines if line.total_eur > 0][:top]
    detail = (
        "\n".join(
            f"• {line.kind.replace('_', ' ').title()} — EUR {line.total_eur:,.2f}"
            f" ({line.count} event{'s' if line.count != 1 else ''})"
            for line in lines
        )
        or "• No toil signals detected this week."
    )

    text = f"*{repo}* — {delta_line(repo, summary.total_eur, state)}"
    return {
        "text": f"{repo}: {delta_line(repo, summary.total_eur, state)}",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": detail}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"{summary.total_engineer_minutes:,.0f} engineer-minutes "
                        "· weekly toil-audit",
                    }
                ],
            },
        ],
    }


def post(
    webhook,
    payload,
    attempts=3,
    backoff=2.0,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
):
    """Send it, retrying a transient failure.

    Retries on transport errors and 5xx only. A 4xx means the webhook is wrong
    or revoked, and repeating it neither fixes that nor tells anyone.
    """
    body = json.dumps(payload).encode()
    last = ""
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            webhook, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with opener(request, timeout=10) as response:
                code = getattr(response, "status", 200)
                if 200 <= code < 300:
                    return True
                last = f"HTTP {code}"
        except urllib.error.HTTPError as err:
            last = f"HTTP {err.code}"
            if err.code < 500:
                # Not transient: a bad or revoked webhook.
                raise DeliveryError(
                    f"{_host_of(webhook)} rejected the report: {last}"
                ) from None
        except Exception as err:  # noqa: BLE001 - transport: DNS, TLS, timeout
            last = type(err).__name__
        if attempt < attempts:
            sleep(backoff * attempt)
    raise DeliveryError(
        f"could not deliver to {_host_of(webhook)} after {attempts} attempts: {last}"
    )
