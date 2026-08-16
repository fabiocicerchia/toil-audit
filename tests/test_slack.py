"""Weekly Slack delivery.

No network: the opener and the clock are injected. The interesting cases are
the ones where delivery goes wrong, because the requirement is that none of
them cost the report.
"""

import json
import urllib.error

import pytest

from toilaudit import slack
from toilaudit.costing import CostLine, CostSummary

WEBHOOK = "https://hooks.slack.example/services/T000/B000/xxxxSECRETxxxx"


def summary(total=412.30, minutes=330.0, lines=None):
    if lines is None:
        lines = [
            CostLine("FLAKY_RECOVERY", 9, 9, 135.0, 168.75, 0.0, 0.0),
            CostLine("RERUN", 10, 10, 100.0, 125.0, 150.0, 1.11),
            CostLine("QUEUE_STALL", 3, 3, 18.0, 22.5, 0.0, 0.0),
            CostLine("ACTION_REQUIRED", 1, 1, 5.0, 0.0, 0.0, 0.0),
        ]
    return CostSummary(
        lines=lines,
        by_workflow={},
        by_template=[],
        by_month={},
        total_engineer_minutes=minutes,
        total_eur=total,
    )


class Opener:
    """A urlopen stand-in recording what it was asked to send."""

    def __init__(self, statuses=(200,), raises=None):
        self.statuses = list(statuses)
        self.raises = list(raises or [])
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.raises:
            err = self.raises.pop(0)
            if err is not None:
                raise err
        status = self.statuses.pop(0) if self.statuses else 200
        return _Response(status)


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestWebhookSecret:
    def test_read_from_the_environment_only(self):
        assert slack.webhook_from_env({"TOIL_AUDIT_SLACK_WEBHOOK": "a"}) == "a"
        assert slack.webhook_from_env({"SLACK_WEBHOOK_URL": "b"}) == "b"
        assert slack.webhook_from_env({}) == ""

    def test_an_error_names_the_host_not_the_url(self):
        # The path is the credential: anyone holding it can post as the app, so
        # it must not reach a log line or a CI transcript.
        opener = Opener(raises=[urllib.error.HTTPError(WEBHOOK, 404, "gone", {}, None)])
        with pytest.raises(slack.DeliveryError) as err:
            slack.post(WEBHOOK, {"text": "x"}, opener=opener, sleep=lambda _: None)
        assert "xxxxSECRETxxxx" not in str(err.value)
        assert "hooks.slack.example" in str(err.value)

    def test_a_transport_failure_message_carries_no_url_either(self):
        opener = Opener(raises=[OSError("connection refused")] * 3)
        with pytest.raises(slack.DeliveryError) as err:
            slack.post(WEBHOOK, {"text": "x"}, opener=opener, sleep=lambda _: None)
        assert "xxxxSECRETxxxx" not in str(err.value)


class TestRetry:
    def test_a_transient_failure_is_retried(self):
        opener = Opener(statuses=[200], raises=[OSError("timeout"), None])
        slept = []
        assert slack.post(WEBHOOK, {"text": "x"}, opener=opener, sleep=slept.append)
        assert len(opener.requests) == 2
        assert slept  # it waited between attempts

    def test_a_5xx_is_retried(self):
        opener = Opener(statuses=[500, 200])
        assert slack.post(WEBHOOK, {"text": "x"}, opener=opener, sleep=lambda _: None)
        assert len(opener.requests) == 2

    def test_a_4xx_is_not_retried(self):
        # A revoked or wrong webhook: repeating it neither fixes anything nor
        # tells anyone.
        opener = Opener(raises=[urllib.error.HTTPError(WEBHOOK, 403, "no", {}, None)])
        with pytest.raises(slack.DeliveryError):
            slack.post(WEBHOOK, {"text": "x"}, opener=opener, sleep=lambda _: None)
        assert len(opener.requests) == 1

    def test_it_gives_up_rather_than_looping(self):
        opener = Opener(raises=[OSError("nope")] * 5)
        with pytest.raises(slack.DeliveryError):
            slack.post(
                WEBHOOK, {"text": "x"}, attempts=3, opener=opener, sleep=lambda _: None
            )
        assert len(opener.requests) == 3


class TestMessage:
    def test_carries_the_figure_and_the_top_signals(self):
        payload = slack.build_message("owner/repo", summary(), {})
        text = json.dumps(payload)
        assert "owner/repo" in text
        assert "412.30" in text
        assert "Flaky Recovery" in text
        assert "Rerun" in text

    def test_only_the_top_signals(self):
        payload = slack.build_message("owner/repo", summary(), {}, top=2)
        text = json.dumps(payload)
        assert "Queue Stall" not in text

    def test_a_zero_cost_signal_is_not_listed(self):
        # ACTION_REQUIRED in the fixture costs nothing; listing it pads the
        # message with a line nobody can act on.
        payload = slack.build_message("owner/repo", summary(), {}, top=99)
        assert "Action Required" not in json.dumps(payload)

    def test_no_signals_says_so_rather_than_showing_an_empty_list(self):
        payload = slack.build_message("owner/repo", summary(lines=[]), {})
        assert "No toil signals" in json.dumps(payload)

    def test_the_payload_carries_no_repository_content(self):
        # Repo name, euros, counts. Nothing from a run, a commit or a log.
        payload = slack.build_message("owner/repo", summary(), {})
        allowed = {"text", "blocks"}
        assert set(payload) == allowed


class TestDelta:
    def test_first_run_makes_no_comparison(self):
        # +100% or 0% would both read as a real movement.
        line = slack.delta_line("owner/repo", 412.30, {})
        assert "first report" in line
        assert "%" not in line

    def test_an_increase(self):
        state = {"owner/repo": {"total_eur": 350.0}}
        assert "+18%" in slack.delta_line("owner/repo", 412.30, state)

    def test_a_decrease(self):
        state = {"owner/repo": {"total_eur": 500.0}}
        line = slack.delta_line("owner/repo", 412.30, state)
        assert "-18%" in line

    def test_a_previous_zero_does_not_divide(self):
        state = {"owner/repo": {"total_eur": 0.0}}
        assert "was EUR 0.00" in slack.delta_line("owner/repo", 412.30, state)

    def test_repos_are_tracked_separately(self):
        state = {"a/b": {"total_eur": 100.0}}
        assert "first report" in slack.delta_line("c/d", 50.0, state)


class TestState:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        slack.save_state({"a/b": {"total_eur": 1.5}}, path)
        assert slack.load_state(path) == {"a/b": {"total_eur": 1.5}}

    def test_a_missing_or_corrupt_state_file_is_empty_not_fatal(self, tmp_path):
        # A lost cache must not fail the run; it costs the comparison, not the
        # report.
        assert slack.load_state(tmp_path / "nope.json") == {}
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        assert slack.load_state(bad) == {}
