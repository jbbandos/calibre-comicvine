"""State-isolation tests for the fixtures in ``tests/fixtures.py``.

Verifies that ``isolated_jsonconfig`` / ``isolated_prefs`` (via
``add_isolation``) stop TokenBucket and PREFS state from leaking between
independent test cases, whatever the test order or outcome (Requirement 8.13).
A failure here is a fixture deficiency, not an Expected_Failure.

Real PREFS values are compared but never printed, so the API key cannot leak
through assertion messages.
"""
import importlib
import itertools
import unittest

from calibre_plugins.comicvine import config, utils

from .fixtures import (
    PLUGIN_PACKAGE,
    PREFS_MODULES,
    add_isolation,
    isolated_jsonconfig,
    isolated_prefs,
)


def _module(name):
    return importlib.import_module("%s.%s" % (PLUGIN_PACKAGE, name))


def _prefs_bindings():
    return {name: _module(name).PREFS for name in PREFS_MODULES}


def _real_prefs_snapshot():
    return {key: config.PREFS[key] for key in config.PREFS.defaults}


class _Boom(Exception):
    pass


class FixtureRestoreTest(unittest.TestCase):
    """Fixtures put back exactly what they replaced."""

    def setUp(self):
        self.bindings = _prefs_bindings()
        self.snapshot = _real_prefs_snapshot()
        self.real_jsonconfig = utils.JSONConfig

    def assert_restored(self):
        for name, original in self.bindings.items():
            self.assertIs(_module(name).PREFS, original, name)
        self.assertIs(utils.JSONConfig, self.real_jsonconfig)
        self.assertTrue(_real_prefs_snapshot() == self.snapshot, "real PREFS changed")

    def test_prefs_replaced_inside_and_restored_after(self):
        with isolated_prefs(requests_burst=99) as store:
            for name in PREFS_MODULES:
                self.assertIs(_module(name).PREFS, store, name)
            store["requests_burst"] = 1
            store["api_key"] = "mutated"
        self.assert_restored()

    def test_prefs_restored_after_exception(self):
        with self.assertRaises(_Boom):
            with isolated_prefs() as store:
                store["requests_rate"] = 123
                raise _Boom()
        self.assert_restored()

    def test_jsonconfig_replaced_inside_and_restored_after(self):
        with isolated_jsonconfig() as stores:
            self.assertIsNot(utils.JSONConfig, self.real_jsonconfig)
            bucket = utils.TokenBucket()
            bucket.params["tokens"] = 7
            self.assertEqual(stores["plugins/comicvine_tokens"]["tokens"], 7)
        self.assert_restored()

    def test_jsonconfig_restored_after_exception(self):
        with self.assertRaises(_Boom):
            with isolated_jsonconfig():
                utils.TokenBucket().params["tokens"] = 7
                raise _Boom()
        self.assert_restored()

    def test_add_isolation_restores_on_cleanup(self):
        class Inner(unittest.TestCase):
            def runTest(inner):
                prefs, stores = add_isolation(inner, requests_burst=2)
                prefs["requests_rate"] = 50
                utils.TokenBucket().params["tokens"] = 1
                raise _Boom()

        result = unittest.TestResult()
        Inner().run(result)
        self.assertEqual(len(result.errors), 1)
        self.assert_restored()

    def test_real_prefs_values_not_visible_inside_isolation(self):
        with isolated_prefs() as store:
            self.assertEqual(store["api_key"], "")


class FreshStateTest(unittest.TestCase):
    """Each use of a fixture starts from the baseline, not from prior mutations."""

    def test_prefs_start_from_defaults_after_prior_mutation(self):
        with isolated_prefs() as first:
            baseline = {k: first[k] for k in config.PREFS.defaults}
            first["requests_rate"] = 777
            first["requests_burst"] = 888
            first["extra_key"] = "x"
        with isolated_prefs() as second:
            self.assertEqual({k: second[k] for k in config.PREFS.defaults}, baseline)
            self.assertNotIn("extra_key", second)

    def test_prefs_overrides_do_not_persist(self):
        with isolated_prefs(requests_burst=42) as first:
            self.assertEqual(first["requests_burst"], 42)
        with isolated_prefs() as second:
            self.assertNotEqual(second["requests_burst"], 42)

    def test_token_bucket_state_starts_empty_after_prior_mutation(self):
        with isolated_jsonconfig() as first:
            bucket = utils.TokenBucket()
            bucket.params["tokens"] = 5
            bucket.params["update"] = 1.0
            self.assertEqual(first["plugins/comicvine_tokens"]["tokens"], 5)
        with isolated_jsonconfig() as second:
            bucket = utils.TokenBucket()
            self.assertEqual(bucket.params["tokens"], 0)
            self.assertNotEqual(bucket.params["update"], 1.0)
            self.assertIsNot(second["plugins/comicvine_tokens"], first["plugins/comicvine_tokens"])

    def test_token_bucket_defaults_do_not_leak_between_instances(self):
        with isolated_jsonconfig():
            first = utils.TokenBucket()
            first.params.defaults["tokens"] = 9
        with isolated_jsonconfig():
            self.assertEqual(utils.TokenBucket().params["tokens"], 0)


# Independent cases that each mutate state under the fixtures.  They are built
# by a factory (not defined at module level) so the loader does not run them
# directly; they are executed in controlled orders below.
BASELINE = {}


def _make_cases(observed):
    def record(testcase):
        prefs, stores = add_isolation(testcase)
        bucket = utils.TokenBucket()
        observed.append(
            (
                testcase.id(),
                {k: prefs[k] for k in config.PREFS.defaults},
                bucket.params["tokens"],
                dict(stores["plugins/comicvine_tokens"]),
            )
        )
        return prefs, bucket

    class Passing(unittest.TestCase):
        def runTest(self):
            prefs, bucket = record(self)
            prefs["requests_rate"] = 11
            prefs["requests_burst"] = 22
            bucket.params["tokens"] = 4

    class Failing(unittest.TestCase):
        def runTest(self):
            prefs, bucket = record(self)
            prefs["requests_rate"] = 33
            bucket.params["tokens"] = 6
            self.fail("deliberate failure")

    class Raising(unittest.TestCase):
        def runTest(self):
            prefs, bucket = record(self)
            prefs["requests_burst"] = 44
            bucket.params["tokens"] = 8
            raise _Boom()

    return Passing, Failing, Raising


class CrossTestLeakageTest(unittest.TestCase):
    """Property 9: every case sees the baseline regardless of order/outcome."""

    def run_in_order(self, order):
        observed = []
        cases = _make_cases(observed)
        result = unittest.TestResult()
        for index in order:
            cases[index]().run(result)
        return observed, result

    def test_every_case_sees_baseline_in_every_order(self):
        real_before = _real_prefs_snapshot()
        bindings_before = _prefs_bindings()
        jsonconfig_before = utils.JSONConfig
        reference = None
        for order in itertools.permutations(range(3)):
            observed, result = self.run_in_order(order)
            # Passing succeeds; Failing fails; Raising errors.
            self.assertEqual(len(result.failures), 1, order)
            self.assertEqual(len(result.errors), 1, order)
            self.assertEqual(len(observed), 3, order)
            states = [state[1:] for state in observed]
            for state in states:
                self.assertEqual(state[1], 0, order)
                self.assertNotIn("update", state[2] if state[2] else {}, order)
            if reference is None:
                reference = states[0]
            for state in states:
                self.assertEqual(state, reference, order)
            self.assertIs(utils.JSONConfig, jsonconfig_before, order)
            for name, original in bindings_before.items():
                self.assertIs(_module(name).PREFS, original, order)
            self.assertTrue(_real_prefs_snapshot() == real_before, "real PREFS changed")

    def test_state_does_not_leak_when_cases_repeat(self):
        for _ in range(20):
            observed, _result = self.run_in_order((0, 1, 2))
            self.assertEqual(len({repr(o[1:]) for o in observed}), 1)


if __name__ == "__main__":
    unittest.main()
