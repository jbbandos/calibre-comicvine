"""Tests for ``utils.TokenBucket`` (Requirement 4.6).

Time is driven by ``FakeClock`` and the bucket's JSONConfig and the plugin
PREFS are replaced by in-memory stores, so nothing sleeps or touches disk.
"""
import unittest

from calibre_plugins.comicvine import utils

from .fixtures import FakeClock, add_isolation

STORE_NAME = "plugins/comicvine_tokens"


class TokenBucketTest(unittest.TestCase):
    def make_bucket(self, rate=1, burst=5):
        self.clock = FakeClock()
        self.prefs, self.stores = add_isolation(
            self, requests_rate=rate, requests_burst=burst
        )
        ctx = self.clock.installed(("utils",))
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        bucket = utils.TokenBucket()
        self.store = self.stores[STORE_NAME]
        return bucket

    def test_new_bucket_is_empty(self):
        bucket = self.make_bucket()
        self.assertEqual(bucket.tokens, 0)

    def test_tokens_refill_with_elapsed_time(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.clock.advance(3)
        self.assertEqual(bucket.tokens, 3)

    def test_refill_scales_with_rate(self):
        bucket = self.make_bucket(rate=2, burst=10)
        self.clock.advance(2)
        self.assertEqual(bucket.tokens, 4)

    def test_partial_token_is_not_granted(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.clock.advance(0.5)
        self.assertEqual(bucket.tokens, 0)

    def test_tokens_capped_at_burst(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.clock.advance(1000)
        self.assertEqual(bucket.tokens, 5)

    def test_refill_that_would_exceed_burst_is_capped(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.store["tokens"] = 4
        self.clock.advance(3)
        self.assertEqual(bucket.tokens, 5)

    def test_full_bucket_does_not_refill(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.store["tokens"] = 5
        self.clock.advance(10)
        self.assertEqual(bucket.tokens, 5)

    def test_consume_takes_a_token_without_sleeping(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.store["tokens"] = 2
        self.store["update"] = self.clock.now()
        bucket.consume()
        self.assertEqual(bucket.tokens, 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_consume_up_to_capacity_never_sleeps(self):
        bucket = self.make_bucket(rate=1, burst=3)
        self.clock.advance(100)
        for _ in range(3):
            bucket.consume()
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(bucket.tokens, 0)

    def test_consume_on_empty_bucket_waits_for_next_token(self):
        bucket = self.make_bucket(rate=1, burst=5)
        bucket.consume()
        self.assertEqual(len(self.clock.sleeps), 1)
        self.assertAlmostEqual(self.clock.sleeps[0], 1.0)
        self.assertEqual(bucket.tokens, 0)

    def test_wait_is_shorter_when_part_of_interval_has_elapsed(self):
        bucket = self.make_bucket(rate=1, burst=5)
        self.clock.advance(0.25)
        bucket.consume()
        self.assertEqual(len(self.clock.sleeps), 1)
        self.assertAlmostEqual(self.clock.sleeps[0], 0.75)

    def test_wait_scales_with_rate(self):
        bucket = self.make_bucket(rate=4, burst=5)
        bucket.consume()
        self.assertAlmostEqual(self.clock.sleeps[0], 0.25)

    def test_each_consume_on_empty_bucket_costs_one_interval(self):
        bucket = self.make_bucket(rate=2, burst=5)
        for _ in range(4):
            bucket.consume()
        self.assertAlmostEqual(sum(self.clock.sleeps), 2.0)

    def test_state_is_stored_in_isolated_config_only(self):
        bucket = self.make_bucket()
        self.clock.advance(2)
        bucket.tokens  # noqa: B018 - property access refills the store
        self.assertEqual(list(self.stores), [STORE_NAME])
        self.assertEqual(self.store["tokens"], 2)


if __name__ == "__main__":
    unittest.main()
