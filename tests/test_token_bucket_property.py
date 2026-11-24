"""Property test for ``utils.TokenBucket`` (Property 4).

**Property 4: Token bucket never exceeds capacity and refills monotonically**
**Validates: Requirements 4.6**
"""
import random
import unittest

from calibre_plugins.comicvine import utils

from .fixtures import FakeClock, add_isolation

ITERATIONS = 150
SEED = 20240604


class TokenBucketPropertyTest(unittest.TestCase):
    def make_bucket(self, rate, burst):
        clock = FakeClock()
        add_isolation(self, requests_rate=rate, requests_burst=burst)
        ctx = clock.installed(("utils",))
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        return clock, utils.TokenBucket()

    def test_never_exceeds_capacity_over_random_operations(self):
        rng = random.Random(SEED)
        for i in range(ITERATIONS):
            rate = rng.randint(1, 5)
            burst = rng.randint(1, 10)
            with self.subTest(iteration=i, rate=rate, burst=burst):
                clock, bucket = self.make_bucket(rate, burst)
                for step in range(rng.randint(1, 40)):
                    if rng.random() < 0.5:
                        clock.advance(rng.uniform(0, 5))
                    else:
                        bucket.consume()
                    tokens = bucket.tokens
                    self.assertGreaterEqual(tokens, 0, f"step {step}")
                    self.assertLessEqual(tokens, burst, f"step {step}")

    def test_refill_is_monotonic_in_elapsed_time(self):
        rng = random.Random(SEED + 1)
        for i in range(ITERATIONS):
            rate = rng.randint(1, 5)
            burst = rng.randint(1, 10)
            with self.subTest(iteration=i, rate=rate, burst=burst):
                clock, bucket = self.make_bucket(rate, burst)
                # Drain some tokens first so there is room to refill.
                clock.advance(rng.uniform(0, 5))
                for _ in range(rng.randint(0, 3)):
                    if bucket.tokens >= 1:
                        bucket.consume()
                previous = bucket.tokens
                for step in range(rng.randint(1, 30)):
                    clock.advance(rng.uniform(0, 3))
                    current = bucket.tokens
                    self.assertGreaterEqual(current, previous, f"step {step}")
                    self.assertLessEqual(current, burst, f"step {step}")
                    previous = current


if __name__ == "__main__":
    unittest.main()
