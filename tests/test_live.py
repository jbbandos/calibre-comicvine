"""Opt-in live smoke tests (Requirements 7.1-7.6).

Enabled with ``COMICVINE_LIVE=1`` or ``run_tests.py --live``. The tests run
``calibre-debug`` as subprocesses against the installed plugin, which uses the
API key already configured in its own preferences. The suite never reads
``COMICVINE_API_KEY`` and never reads, sets, or prints ``PREFS["api_key"]``.
"""
import os
import re
import subprocess
import unittest

LIVE_ENABLED = os.environ.get("COMICVINE_LIVE") == "1"
SKIP_REASON = "live tests not enabled (set COMICVINE_LIVE=1 or pass --live)"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 300

# Reports only whether a key is present, never its value.
KEY_PROBE = (
    "from calibre.customize.ui import initialize_plugins;"
    "initialize_plugins();"
    "from calibre_plugins.comicvine.config import PREFS;"
    "print('COMICVINE_KEY_PRESENT' if str(PREFS['api_key']).strip() "
    "else 'COMICVINE_KEY_ABSENT')"
)

# README examples, as argument lists after ``calibre-debug -r Comicvine``.
README_EXAMPLES = [
    ["t:The Invisibles #15", "a:Grant Morrison"],
    ["i:comicvine:41736"],
    ["t:Batman #12", "i:comicvine-volume:42721"],
]

# Result lines printed by Comicvine._print_result: "Found: ..." or "(0000) - ...".
RESULT_LINE = re.compile(r"^(Found:|\(\d+\)\s*-)", re.MULTILINE)


def redact(text, secrets):
    """Return ``text`` with every non-empty secret replaced by a marker."""
    if text is None:
        return text
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    # Longest first so a secret containing another is fully removed.
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "***REDACTED***")
    return text


def run_calibre_debug(*args):
    """Run calibre-debug, returning (returncode, redacted stdout, redacted stderr)."""
    proc = subprocess.run(
        ["calibre-debug", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=TIMEOUT,
        check=False,
    )
    return proc.returncode, redact(proc.stdout, []), redact(proc.stderr, [])


@unittest.skipUnless(LIVE_ENABLED, SKIP_REASON)
class LiveSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, out, _err = run_calibre_debug("-c", KEY_PROBE)
        if code != 0 or "COMICVINE_KEY_PRESENT" not in out:
            raise unittest.SkipTest(
                "no Comicvine API key configured in the installed plugin's preferences"
            )

    def test_init_runs(self):
        code, out, err = run_calibre_debug("-e", "__init__.py")
        self.assertEqual(code, 0, f"stdout:\n{out}\nstderr:\n{err}")

    def test_readme_examples_return_results(self):
        for example in README_EXAMPLES:
            with self.subTest(example=example):
                code, out, err = run_calibre_debug("-r", "Comicvine", *example)
                self.assertEqual(code, 0, f"stdout:\n{out}\nstderr:\n{err}")
                self.assertRegex(
                    out, RESULT_LINE, f"no results.\nstdout:\n{out}\nstderr:\n{err}"
                )


if __name__ == "__main__":
    unittest.main()
