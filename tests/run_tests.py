"""Test_Runner for the Comicvine plugin test suite.

Run inside calibre:

    calibre-debug -e tests/run_tests.py [-- --live]

Options:
    --live    Enable the live smoke tests (sets COMICVINE_LIVE=1).
"""

import importlib
import os
import sys
import unittest

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # pragma: no cover - defensive, calibre-debug defines __file__
    _HERE = os.path.abspath("tests")
REPO_ROOT = os.path.dirname(_HERE)
DEFECTS_PATH = os.path.join(_HERE, "DEFECTS.md")
PLUGIN_MODULE = "calibre_plugins.comicvine"


class SuiteResult(unittest.TextTestResult):
    """TestResult tracking passed, failed, skipped, expected-failure and
    unexpected-pass outcomes separately.

    Unlike the default, an unexpected pass does not make the run
    unsuccessful; it is only reported.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []
        self.unexpected_pass_names = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.unexpected_pass_names.append(test.id())

    def wasSuccessful(self):
        # Failures and errors outside the expected-failure set only.
        return not self.failures and not self.errors

    def counts(self):
        """Return the four reported counts plus unexpected passes."""
        return {
            "passed": len(self.passed),
            "failed": len(self.failures) + len(self.errors),
            "skipped": len(self.skipped),
            "expected failures": len(self.expectedFailures),
            "unexpected passes": len(self.unexpected_pass_names),
        }


class SuiteRunner(unittest.TextTestRunner):
    resultclass = SuiteResult


def parse_args(argv):
    """Return True if --live was given."""
    return "--live" in argv


def print_summary(result, stream=None):
    stream = stream or sys.stdout
    counts = result.counts()
    stream.write("\n")
    stream.write("Passed: %d\n" % counts["passed"])
    stream.write("Failed: %d\n" % counts["failed"])
    stream.write("Skipped: %d\n" % counts["skipped"])
    for test, reason in result.skipped:
        stream.write("  %s: %s\n" % (test.id(), reason))
    stream.write("Expected failures: %d\n" % counts["expected failures"])
    if result.unexpected_pass_names:
        stream.write("Unexpected passes (%d):\n" % counts["unexpected passes"])
        for name in result.unexpected_pass_names:
            stream.write("  %s\n" % name)
    stream.write("Defect report: %s\n" % DEFECTS_PATH)
    stream.flush()


def exit_status(result):
    """0 iff there are no failures or errors outside the expected-failure set."""
    return 0 if result.wasSuccessful() else 1


def check_plugin_importable():
    """Return None if the plugin imports, else an error message."""
    try:
        importlib.import_module(PLUGIN_MODULE)
    except Exception as exc:  # ImportError or anything raised at import time
        return (
            "Comicvine plugin not importable from %s: %s" % (PLUGIN_MODULE, exc)
        )
    return None


def run(argv=None):
    """Run the suite and return the process exit status."""
    argv = sys.argv[1:] if argv is None else argv
    if parse_args(argv):
        os.environ["COMICVINE_LIVE"] = "1"

    error = check_plugin_importable()
    if error:
        sys.stderr.write(error + "\n")
        return 1

    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    suite = unittest.TestLoader().discover(
        _HERE, pattern="test_*.py", top_level_dir=REPO_ROOT
    )
    result = SuiteRunner(stream=sys.stderr, verbosity=1).run(suite)
    print_summary(result)
    return exit_status(result)


if __name__ == "__main__":
    sys.exit(run())
