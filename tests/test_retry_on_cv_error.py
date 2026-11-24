"""Tests for ``utils.retry_on_cv_error`` (Requirement 4.5).

``time.sleep`` inside ``utils`` is replaced by ``FakeClock`` so no test
actually waits.  ``retries=0`` is a documented defect and is covered in
``test_defects.py``, so it is not exercised here.
"""
import unittest

from calibre_plugins.comicvine import utils

from .fixtures import FakeClock


class Flaky:
    """Callable that raises ``exc`` for the first ``failures`` calls."""

    def __init__(self, failures, exc=ValueError, result="ok"):
        self.failures = failures
        self.exc = exc
        self.result = result
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc("failure %d" % self.calls)
        return self.result


class RetryOnCvErrorTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        ctx = self.clock.installed(("utils",))
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)

    def test_success_first_try_no_sleep(self):
        target = Flaky(0)
        self.assertEqual(utils.retry_on_cv_error(retries=3)(target)(), "ok")
        self.assertEqual(target.calls, 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_passes_arguments_through(self):
        def target(a, b=0):
            return (a, b)

        self.assertEqual(utils.retry_on_cv_error()(target)(1, b=2), (1, 2))

    def test_retries_then_succeeds(self):
        target = Flaky(2)
        self.assertEqual(utils.retry_on_cv_error(retries=3)(target)(), "ok")
        self.assertEqual(target.calls, 3)
        self.assertEqual(len(self.clock.sleeps), 2)

    def test_reraises_original_exception_after_all_retries(self):
        target = Flaky(10, exc=KeyError)
        wrapped = utils.retry_on_cv_error(retries=3)(target)
        with self.assertRaises(KeyError) as ctx:
            wrapped()
        self.assertEqual(target.calls, 3)
        self.assertIn("failure 3", str(ctx.exception))

    def test_default_retries_is_two(self):
        target = Flaky(10)
        with self.assertRaises(ValueError):
            utils.retry_on_cv_error()(target)()
        self.assertEqual(target.calls, 2)

    def test_single_retry_calls_once_and_does_not_sleep(self):
        target = Flaky(10)
        with self.assertRaises(ValueError):
            utils.retry_on_cv_error(retries=1)(target)()
        self.assertEqual(target.calls, 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_backoff_sleeps_between_attempts_only(self):
        target = Flaky(10)
        with self.assertRaises(ValueError):
            utils.retry_on_cv_error(retries=4)(target)()
        # One sleep between each pair of attempts, none after the last.
        self.assertEqual(len(self.clock.sleeps), 3)
        for delay in self.clock.sleeps:
            self.assertGreaterEqual(delay, 0.1)
            self.assertLessEqual(delay, 0.6)

    def test_rate_limit_error_is_raised_immediately(self):
        target = Flaky(10, exc=utils.RateLimitExceededError)
        with self.assertRaises(utils.RateLimitExceededError):
            utils.retry_on_cv_error(retries=5)(target)()
        self.assertEqual(target.calls, 1)
        self.assertEqual(self.clock.sleeps, [])


if __name__ == "__main__":
    unittest.main()
