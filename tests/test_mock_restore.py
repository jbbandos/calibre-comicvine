"""Property 5: the Mock_Comicvine swap is always restored.

**Validates: Requirements 2.1**

For any offline test body (passing, failing an assertion, or raising), running
it under ``with_mock_comicvine`` must leave the ``pycomicvine`` binding in the
plugin modules (and the socket guard) exactly as it was before the test.
"""
import importlib
import io
import random
import socket
import unittest

from .mock_comicvine import PATCHED_MODULES, PLUGIN_PACKAGE, with_mock_comicvine

ITERATIONS = 150
OUTCOMES = ("pass", "fail", "raise")


def _bindings():
    """Snapshot of the names the fixture patches."""
    snap = {}
    for name in PATCHED_MODULES:
        module = importlib.import_module("%s.%s" % (PLUGIN_PACKAGE, name))
        snap[name] = module.pycomicvine
    snap["socket.connect"] = socket.socket.connect
    snap["socket.connect_ex"] = socket.socket.connect_ex
    snap["socket.create_connection"] = socket.create_connection
    return snap


def _run_under_fixture(outcome, fail_in_cleanup_order):
    """Run one throwaway test using the fixture; return (result, mock, inside)."""
    inside = {}

    class Inner(unittest.TestCase):
        def runTest(self):
            if fail_in_cleanup_order:
                # An unrelated cleanup registered before the fixture.
                self.addCleanup(lambda: None)
            inside["mock"] = with_mock_comicvine(self)
            inside["during"] = _bindings()
            if outcome == "fail":
                self.fail("deliberate failure")
            elif outcome == "raise":
                raise RuntimeError("deliberate error")

    result = unittest.TextTestRunner(stream=io.StringIO()).run(Inner())
    return result, inside


class MockRestoreProperty(unittest.TestCase):
    def test_binding_restored_for_any_outcome(self):
        rng = random.Random(5)
        before = _bindings()
        for i in range(ITERATIONS):
            outcome = rng.choice(OUTCOMES)
            result, inside = _run_under_fixture(outcome, rng.random() < 0.5)

            # The inner test ended with the outcome we asked for.
            if outcome == "pass":
                self.assertTrue(result.wasSuccessful(), i)
            elif outcome == "fail":
                self.assertEqual(len(result.failures), 1, i)
            else:
                self.assertEqual(len(result.errors), 1, i)

            # While the test ran, the mock really was swapped in.
            for name in PATCHED_MODULES:
                self.assertIs(inside["during"][name], inside["mock"], (i, name))
                self.assertIsNot(before[name], inside["mock"])

            # Afterwards every original binding is back, by identity.
            after = _bindings()
            for key, original in before.items():
                self.assertIs(after[key], original, (i, outcome, key))


if __name__ == "__main__":
    unittest.main()
