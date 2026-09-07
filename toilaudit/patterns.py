"""Regexes that recognise a failing test in a CI job log.

Definitions only — `attribute` holds the logic that applies them. Nothing else
in the package compiles a regex from a literal.
"""

import re

# Per-framework patterns for "this test failed". Anchored on the framework's
# own failure syntax rather than on the word "error", which appears in passing
# builds constantly.
#
# Each pattern must capture a `path` group; `name` is optional. Sources are the
# frameworks' default reporters:
#   pytest   FAILED tests/test_orders.py::test_split - AssertionError
#   go test  --- FAIL: TestSplit (0.00s)  + the preceding file:line
#   jest     ● tests/orders.test.js › splits    /  at tests/orders.test.js:12
#   junit    <testcase classname="tests.orders" name="test_split"><failure
#   rspec    rspec ./spec/orders_spec.rb:12 # Orders splits
# Note the lack of a `^` anchor on most of these: GitHub prefixes every log
# line with an ISO timestamp, so anchoring to the start of the line matches
# nothing on a real download and everything in a hand-written fixture — the
# kind of pattern that passes its tests and finds zero failures in production.
PATTERNS = (
    re.compile(
        r"(?:^|\s)FAILED\s+(?P<path>[\w./\\-]+\.py)::(?P<name>[\w:.\[\]-]+)",
        re.MULTILINE,
    ),
    re.compile(
        r"(?:^|\s)ERROR\s+(?P<path>[\w./\\-]+\.py)::(?P<name>[\w:.\[\]-]+)",
        re.MULTILINE,
    ),
    re.compile(
        r"(?:^|\s)(?:●|✕|✗)\s+(?P<path>[\w./\\-]+\.(?:test|spec)\.[jt]sx?)\s*[›>]\s*(?P<name>[^\n]+)",
        re.MULTILINE,
    ),
    re.compile(
        r"(?:^|\s)at\s+(?P<path>[\w./\\-]+\.(?:test|spec)\.[jt]sx?):\d+", re.MULTILINE
    ),
    re.compile(r"rspec\s+\./(?P<path>[\w./\\-]+_spec\.rb):\d+", re.MULTILINE),
    re.compile(
        r'<testcase[^>]*classname="(?P<path>[\w.]+)"[^>]*name="(?P<name>[^"]+)"[^>]*>\s*<failure',
        re.MULTILINE,
    ),
)

# Go is the exception: `--- FAIL: TestX` names the test but not the file, and
# the file:line is on an earlier line with nothing tying the two together. So
# the presence of a FAIL gates it, and the _test.go paths in the same log are
# taken as the failing files — cruder, but it does not invent an association
# the log does not actually make.
GO_FAIL = re.compile(r"^\s*---\s+FAIL:\s+\w+", re.MULTILINE)
GO_FILE = re.compile(r"(?P<path>[\w./\\-]+_test\.go):\d+")

# A path that escapes the repo, or is absolute, is not a test file in this
# project — it is a dependency's own failing test, or a pattern misfiring.
SUSPICIOUS = re.compile(
    r"(^/)|(^[A-Za-z]:)|(\.\.)|(site-packages)|(node_modules)|(/usr/)"
)
