"""Which test caused the flaky-recovery loop.

FLAKY_RECOVERY detects fail-then-pass on the same commit from run metadata
alone. That prices the toil correctly and names nothing, and the name is the
part that makes it fixable — "flaky tests cost EUR 4,200" is a slide, while
"tests/test_orders.py cost EUR 1,900 of it" is a ticket.

The identity has to come from the logs, which brings two constraints that shape
this module more than the parsing does:

**Log content is used for matching only.** Nothing from a log line is stored in
the report — not as evidence, not as an excerpt. A failing job echoes whatever
the failure printed, which routinely includes tokens, connection strings and
customer data. What survives is the test identity the pattern captured, which
is a path and a test name.

**Attribution partitions the total; it never adds to it.** Each recovery's euro
cost is already counted by `costing`. Attribution only says which file that
existing cost belongs to, and a recovery whose cause cannot be identified is
counted as unattributed rather than spread across the others or quietly
dropped. A ranking that does not add up to the total it partitions is worse
than no ranking.
"""

import io
import zipfile
from dataclasses import dataclass, field

from .patterns import GO_FAIL, GO_FILE, PATTERNS, SUSPICIOUS


def _go_failures(log_text: str) -> set[str]:
    """Test files from a `go test` log, but only if it reported a failure."""
    if not GO_FAIL.search(log_text):
        return set()
    return {
        match.group("path")
        for match in GO_FILE.finditer(log_text)
        if not SUSPICIOUS.search(match.group("path"))
    }


def failing_tests(log_text: str) -> list[str]:
    """Test identities named as failing in one job's log.

    Returns paths (or `path::name` where the framework gives one), de-duplicated
    and sorted so a report is stable across runs. Never returns a log line.
    """
    found: set[str] = _go_failures(log_text)
    for pattern in PATTERNS:
        for match in pattern.finditer(log_text):
            groups = match.groupdict()
            path = (groups.get("path") or "").strip()
            if not path or SUSPICIOUS.search(path):
                continue
            name = (groups.get("name") or "").strip()
            # The file is the unit someone fixes; the test name is kept when
            # the framework supplies one, because a 3000-line file with one
            # flaky case is a different ticket from a file that is all flaky.
            found.add(f"{path}::{name}" if name else path)
    return sorted(found)


def file_of(identity: str) -> str:
    """`tests/x.py::test_y` -> `tests/x.py`, for ranking by file.

    Named file_of rather than test_file so pytest does not try to collect it
    as a test case when it is imported into one.
    """
    return identity.split("::", 1)[0]


@dataclass
class Attribution:
    """How the flaky-recovery cost splits across test files."""

    by_file: dict[str, float] = field(default_factory=dict)
    by_test: dict[str, float] = field(default_factory=dict)
    # Recoveries whose cause no pattern matched. Counted, never guessed at and
    # never spread across the files that were identified.
    unattributed: int = 0
    unattributed_eur: float = 0.0
    attributed: int = 0

    @property
    def total_eur(self) -> float:
        return round(sum(self.by_file.values()) + self.unattributed_eur, 2)

    def ranked(self) -> list[tuple[str, float]]:
        """Test files, most expensive first."""
        return sorted(self.by_file.items(), key=lambda kv: (-kv[1], kv[0]))


def attribute(recoveries, logs_for, cost_of) -> Attribution:
    """Split the cost of each flaky recovery across the tests that failed.

    `recoveries` are the FLAKY_RECOVERY signals; `logs_for(signal)` returns the
    failed run's log text (or "" when it cannot be read); `cost_of(signal)` is
    the euro figure `costing` already assigned to it.

    A run that names several failing tests splits its cost evenly between them.
    Weighting by anything else would be inventing evidence: the run metadata
    says one recovery happened, not which of the three failures cost the time.
    """
    out = Attribution()
    for signal in recoveries:
        eur = float(cost_of(signal))
        try:
            text = logs_for(signal) or ""
        except Exception:  # noqa: BLE001 - see below
            # Deliberately blind. The fetcher is supplied by the caller and can
            # fail in any way a filesystem or an HTTP client can: a log that
            # cannot be read is an unattributed recovery, not a failed audit,
            # and the euro figure is correct either way.
            text = ""
        identities = failing_tests(text)
        if not identities:
            out.unattributed += 1
            out.unattributed_eur = round(out.unattributed_eur + eur, 6)
            continue
        out.attributed += 1
        share = eur / len(identities)
        for identity in identities:
            out.by_test[identity] = round(out.by_test.get(identity, 0.0) + share, 6)
            path = file_of(identity)
            out.by_file[path] = round(out.by_file.get(path, 0.0) + share, 6)
    # Round once at the end: rounding each share would drift the partition away
    # from the total it is supposed to divide.
    out.by_file = {k: round(v, 2) for k, v in out.by_file.items()}
    out.by_test = {k: round(v, 2) for k, v in out.by_test.items()}
    out.unattributed_eur = round(out.unattributed_eur, 2)
    return out


def logs_from_zip(data: bytes) -> str:
    """Text of every log file in a GitHub run-logs zip.

    The API serves logs as a zip of per-step text files. Read in memory and
    never written to disk: the point of this module is that log content does
    not persist anywhere.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return ""
    parts = []
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        try:
            parts.append(archive.read(name).decode("utf-8", "replace"))
        except KeyError:
            continue
    return "\n".join(parts)


def summarise(attribution: Attribution, top: int = 10) -> list[str]:
    """Markdown lines for the report."""
    lines = ["## Flaky recoveries by test file", ""]
    if not attribution.by_file and not attribution.unattributed:
        lines.append("No flaky recoveries detected.")
        return lines

    ranked = attribution.ranked()[:top]
    if ranked:
        lines.append("| test file | attributed cost |")
        lines.append("|---|---:|")
        for path, eur in ranked:
            lines.append(f"| `{path}` | EUR {eur:,.2f} |")
        lines.append("")
    if attribution.unattributed:
        lines.append(
            f"{attribution.unattributed} recovery(ies) worth EUR "
            f"{attribution.unattributed_eur:,.2f} could not be attributed — no "
            "recognised test failure in the logs. Counted here rather than "
            "spread across the files above."
        )
        lines.append("")
    return lines
