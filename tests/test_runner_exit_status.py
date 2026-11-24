"""Property 1: exit status matches failure outcome.

**Validates: Requirements 1.5, 1.6, 8.3**

Random mixes of outcomes are built into small in-memory suites and run through
the runner's own ``SuiteRunner``/``exit_status``. Discovery is never invoked
(``run_tests.run`` is not called), so the nested runs cannot recurse into the
whole suite.
"""
import importlib.util
import io
import os
import random
import unittest

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_tests.py")
_spec = importlib.util.spec_from_file_location("_runner_under_test_status", _PATH)
run_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_tests)

OUTCOMES = ("pass", "fail", "error", "skip", "xfail", "xpass")


def _make_case(outcome):
    """Return a TestCase instance that produces the given outcome."""

    class Generated(unittest.TestCase):
        def runTest(self):
            if outcome == "fail" or outcome == "xfail":
                self.fail("boom")
            elif outcome == "error":
                raise RuntimeError("boom")
            elif outcome == "skip":
                self.skipTest("skipped")

    if outcome == "xfail" or outcome == "xpass":
        Generated.runTest = unittest.expectedFailure(Generated.runTest)
    return Generated()


def _run(outcomes):
    suite = unittest.TestSuite(_make_case(o) for o in outcomes)
    stream = io.StringIO()
    result = run_tests.SuiteRunner(stream=stream, verbosity=0).run(suite)
    return result


class RunnerExitStatusProperty(unittest.TestCase):
    def test_exit_status_zero_iff_no_unexpected_failures(self):
        rng = random.Random(1234)
        for _ in range(150):
            outcomes = [rng.choice(OUTCOMES) for _ in range(rng.randint(0, 12))]
            result = _run(outcomes)
            has_bad = any(o in ("fail", "error") for o in outcomes)
            expected = 1 if has_bad else 0
            self.assertEqual(
                run_tests.exit_status(result), expected, "outcomes=%r" % (outcomes,)
            )

    def test_unexpected_pass_never_changes_exit_status(self):
        rng = random.Random(99)
        for _ in range(100):
            base = [
                rng.choice(OUTCOMES[:-1]) for _ in range(rng.randint(0, 8))
            ]
            extra = ["xpass"] * rng.randint(1, 4)
            mixed = base + extra
            rng.shuffle(mixed)
            self.assertEqual(
                run_tests.exit_status(_run(base)),
                run_tests.exit_status(_run(mixed)),
                "base=%r mixed=%r" % (base, mixed),
            )

    def test_unexpected_passes_are_reported_by_name(self):
        result = _run(["xpass", "pass"])
        self.assertEqual(len(result.unexpected_pass_names), 1)
        self.assertEqual(run_tests.exit_status(result), 0)


if __name__ == "__main__":
    unittest.main()
