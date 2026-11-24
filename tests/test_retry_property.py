"""Property test for ``utils.retry_on_cv_error``.

**Property 3: Retry decorator calls exactly as configured**

**Validates: Requirements 4.5, 8.9**

N >= 1 only: ``retries=0`` is defect 8a and is covered by an
Expected_Failure test in ``test_defects.py``.
"""
import random
import unittest

from calibre_plugins.comicvine import utils

from .fixtures import FakeClock

ITERATIONS = 200
SEED = 20240603


class _Boom(Exception):
    pass


class RetryPropertyTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        ctx = self.clock.installed(("utils",))
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)

    def test_call_count_and_outcome_match_configuration(self):
        rng = random.Random(SEED)
        for _ in range(ITERATIONS):
            n = rng.randint(1, 8)
            # m failures before success; None means it never succeeds.
            m = None if rng.random() < 0.3 else rng.randint(0, 12)
            calls = []
            sleeps_before = len(self.clock.sleeps)

            def target(*args, **kwargs):
                calls.append((args, kwargs))
                if m is None or len(calls) <= m:
                    raise _Boom("failure %d" % len(calls))
                return ("result", len(calls))

            wrapped = utils.retry_on_cv_error(retries=n)(target)
            ctx = "n=%r m=%r" % (n, m)
            if m is not None and m + 1 <= n:
                self.assertEqual(wrapped(1, k=2), ("result", m + 1), ctx)
                self.assertEqual(len(calls), m + 1, ctx)
                self.assertEqual(calls[0], ((1,), {"k": 2}), ctx)
            else:
                with self.assertRaises(_Boom, msg=ctx) as raised:
                    wrapped(1, k=2)
                self.assertEqual(len(calls), n, ctx)
                self.assertEqual(str(raised.exception), "failure %d" % n, ctx)
            # Never sleeps after the final attempt.
            self.assertLessEqual(len(self.clock.sleeps) - sleeps_before,
                                 max(len(calls) - 1, 0), ctx)


if __name__ == "__main__":
    unittest.main()
