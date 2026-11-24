"""Property 2: reported counts match actual outcomes.

**Validates: Requirements 1.4**
"""
import io
import random
import re
import unittest

from tests import run_tests

OUTCOMES = ("pass", "fail", "error", "skip", "xfail", "xpass")
ITERATIONS = 100


def make_case(outcome, index):
    """Return a TestCase class with one test producing ``outcome``."""

    def body(self):
        if outcome == "fail":
            self.fail("boom")
        elif outcome == "error":
            raise RuntimeError("boom")
        elif outcome == "skip":
            self.skipTest("skipped")
        elif outcome == "xfail":
            self.fail("expected")

    if outcome in ("xfail", "xpass"):
        body = unittest.expectedFailure(body)
    return type("Case%d" % index, (unittest.TestCase,), {"test_it": body})


def run_outcomes(outcomes):
    suite = unittest.TestSuite()
    for i, outcome in enumerate(outcomes):
        suite.addTest(make_case(outcome, i)("test_it"))
    stream = io.StringIO()
    result = run_tests.SuiteRunner(stream=stream, verbosity=0).run(suite)
    return result


def printed_counts(result):
    out = io.StringIO()
    run_tests.print_summary(result, stream=out)
    text = out.getvalue()
    return {
        key: int(re.search(r"^%s: (\d+)$" % label, text, re.M).group(1))
        for key, label in (
            ("passed", "Passed"),
            ("failed", "Failed"),
            ("skipped", "Skipped"),
            ("expected failures", "Expected failures"),
        )
    }


class RunnerCountsProperty(unittest.TestCase):
    def test_printed_counts_match_actual_outcomes(self):
        rng = random.Random(20240502)
        for _ in range(ITERATIONS):
            outcomes = [rng.choice(OUTCOMES) for _ in range(rng.randint(0, 15))]
            result = run_outcomes(outcomes)
            expected = {
                "passed": outcomes.count("pass"),
                "failed": outcomes.count("fail") + outcomes.count("error"),
                "skipped": outcomes.count("skip"),
                "expected failures": outcomes.count("xfail"),
            }
            self.assertEqual(printed_counts(result), expected, outcomes)

    def test_empty_run_prints_zero_counts(self):
        result = run_outcomes([])
        self.assertEqual(
            printed_counts(result),
            {"passed": 0, "failed": 0, "skipped": 0, "expected failures": 0},
        )


if __name__ == "__main__":
    unittest.main()
