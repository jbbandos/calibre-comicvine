"""Property 7: Expected-failure tests never count as ordinary failures.

**Validates: Requirements 8.2, 8.3**

Random suites of expected-failure tests (some that fail or raise as expected,
some that unexpectedly pass) are run through the real runner classes, with
ordinary passing tests mixed in.
"""
import io
import random
import unittest

from . import run_tests

ITERATIONS = 100

KINDS = ("xfail_assert", "xfail_raise", "xpass", "ok")


def _make_case(index, kind):
    """Build a TestCase class holding a single test of the given kind."""
    if kind == "xfail_assert":
        def body(self):
            self.assertEqual(1, 2)
        body = unittest.expectedFailure(body)
    elif kind == "xfail_raise":
        def body(self):
            raise RuntimeError("expected defect")
        body = unittest.expectedFailure(body)
    elif kind == "xpass":
        def body(self):
            pass
        body = unittest.expectedFailure(body)
    else:
        def body(self):
            pass
    return type("Case%d" % index, (unittest.TestCase,), {"test_it": body})


def _run(kinds, extra_failure=False):
    suite = unittest.TestSuite()
    cases = []
    for i, kind in enumerate(kinds):
        cls = _make_case(i, kind)
        cases.append((cls, kind))
        suite.addTest(cls("test_it"))
    if extra_failure:
        def boom(self):
            self.fail("ordinary failure")
        cls = type("Ordinary", (unittest.TestCase,), {"test_it": boom})
        suite.addTest(cls("test_it"))
    result = run_tests.SuiteRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result, cases


class ExpectedFailureHandlingTest(unittest.TestCase):
    def test_expected_failures_excluded_from_failed_count(self):
        rng = random.Random(7001)
        for _ in range(ITERATIONS):
            kinds = [rng.choice(KINDS) for _ in range(rng.randint(0, 12))]
            result, _ = _run(kinds)
            counts = result.counts()
            n_xfail = sum(k in ("xfail_assert", "xfail_raise") for k in kinds)
            self.assertEqual(counts["failed"], 0, kinds)
            self.assertEqual(counts["expected failures"], n_xfail, kinds)
            self.assertEqual(run_tests.exit_status(result), 0, kinds)

    def test_unexpected_passes_reported_by_name(self):
        rng = random.Random(7002)
        for _ in range(ITERATIONS):
            kinds = [rng.choice(KINDS) for _ in range(rng.randint(0, 12))]
            result, cases = _run(kinds)
            expected_names = sorted(
                cls.__name__ for cls, kind in cases if kind == "xpass"
            )
            reported = sorted(
                name.split(".")[-2] for name in result.unexpected_pass_names
            )
            self.assertEqual(reported, expected_names, kinds)
            self.assertEqual(
                result.counts()["unexpected passes"], len(expected_names)
            )
            # Unexpected passes are not counted as passed or failed.
            self.assertEqual(
                result.counts()["passed"], sum(k == "ok" for k in kinds)
            )
            summary = io.StringIO()
            run_tests.print_summary(result, summary)
            text = summary.getvalue()
            for name in result.unexpected_pass_names:
                self.assertIn(name, text)

    def test_unexpected_pass_does_not_change_exit_status(self):
        rng = random.Random(7003)
        for _ in range(ITERATIONS):
            kinds = [rng.choice(KINDS) for _ in range(rng.randint(1, 12))]
            with_ordinary_failure = rng.random() < 0.5
            result, _ = _run(kinds, extra_failure=with_ordinary_failure)
            expected_status = 1 if with_ordinary_failure else 0
            self.assertEqual(
                run_tests.exit_status(result), expected_status, kinds
            )
            if with_ordinary_failure:
                self.assertEqual(result.counts()["failed"], 1)


if __name__ == "__main__":
    unittest.main()
