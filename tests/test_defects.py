"""Expected_Failure tests for suspected plugin defects (Requirement 8).

Every test here asserts the *correct* behaviour and is decorated with
``unittest.expectedFailure`` because the unmodified plugin does not provide
it.  See ``tests/DEFECTS.md`` for the matching Defect_Report rows.

This module currently covers ``cli_main`` and the ``utils.py`` functions
(task 8.1), plus ``build_meta``, ``identify`` and ``download_cover`` (8.2).
"""
import datetime
import io
import logging
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from multiprocessing.pool import ThreadPool
from queue import Queue
from types import SimpleNamespace
from unittest import mock

from calibre.ebooks.metadata.book.base import Metadata

from calibre_plugins.comicvine import source as source_module
from calibre_plugins.comicvine import utils
from calibre_plugins.comicvine.source import Comicvine

from .fixtures import FakeClock, add_isolation
from .mock_comicvine import (
    MockComicvineMixin,
    MockIssue,
    MockPerson,
    MockVolume,
    default_fixtures,
)
from .test_download_cover import FakeLog
from .test_keygen import IdMetadata
from .test_normalised_title import FakeQuery


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


# --------------------------------------------------------------------------
# cli_main (defects 1a, 1b, 2, 3)
# --------------------------------------------------------------------------
class CliMainDefectTests(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.source = Comicvine(None)
        self.identify_calls = []

        def fake_identify(log, result_queue, abort, **kwargs):
            self.identify_calls.append(kwargs)

        self.source.identify = fake_identify

    def run_cli(self, args):
        """Run ``cli_main``; return all text it printed or logged.

        ``SystemExit`` (an option-parser style usage exit) is tolerated;
        any other exception propagates to the caller.
        """
        out, err = io.StringIO(), io.StringIO()
        handler = _ListHandler()
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                try:
                    self.source.cli_main(args)
                except SystemExit:
                    pass
        finally:
            root.removeHandler(handler)
        return out.getvalue() + err.getvalue() + "\n".join(handler.messages)

    @unittest.expectedFailure
    def test_ampersand_separated_authors_are_stripped(self):
        """1a: ``a:X & Y`` yields one stripped name per author."""
        self.run_cli(["a:Brian K. Vaughan & Fiona Staples"])
        self.assertEqual(
            self.identify_calls[0]["authors"], ["Brian K. Vaughan", "Fiona Staples"]
        )

    @unittest.expectedFailure
    def test_multiple_author_arguments_are_all_retained(self):
        """1b: every ``a:`` argument contributes its authors."""
        self.run_cli(["a:Alice", "a:Bob"])
        self.assertEqual(self.identify_calls[0]["authors"], ["Alice", "Bob"])

    @unittest.expectedFailure
    def test_repeated_title_and_id_arguments_handled_consistently(self):
        """2: repeats are rejected with a message, or the same choice
        (first or last) is made for ``t:`` and ``i:`` and the user is told."""
        output = self.run_cli(
            ["t:First", "t:Second", "i:comicvine:1", "i:comicvine:2"]
        )
        if not self.identify_calls:
            # Rejected: a usage or error message must have been produced.
            self.assertTrue(output.strip(), "repeat rejected without a message")
            return
        kwargs = self.identify_calls[0]
        title_choice = {"First": "first", "Second": "last"}.get(kwargs["title"])
        id_choice = {1: "first", 2: "last"}.get(kwargs["identifiers"]["comicvine"])
        self.assertEqual(title_choice, id_choice)
        # Silently discarding the other value is not acceptable.
        self.assertTrue(output.strip(), "repeated argument silently discarded")

    @unittest.expectedFailure
    def test_non_numeric_comicvine_id_reports_error(self):
        """3: ``i:comicvine:abc`` gives a message, not a ValueError."""
        output = self.run_cli(["i:comicvine:abc"])
        self.assertTrue(output.strip(), "no usage or error message printed")


# --------------------------------------------------------------------------
# normalised_title (defect 4)
# --------------------------------------------------------------------------
class NormalisedTitleDefectTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_return_shape_is_consistent_for_every_input_type(self):
        """4: ``(Optional[str], list)`` for str, None, int and bytes."""
        for value in ("Saga #1", None, 12, b"Saga #1"):
            result = utils.normalised_title(FakeQuery(), value)
            self.assertIsInstance(result, tuple, repr(value))
            self.assertEqual(len(result), 2, repr(value))
            issue_number, tokens = result
            self.assertTrue(
                issue_number is None or isinstance(issue_number, str),
                "issue number for %r is %r" % (value, issue_number),
            )
            self.assertIsInstance(tokens, list, "tokens for %r" % (value,))


# --------------------------------------------------------------------------
# find_title (defect 5)
# --------------------------------------------------------------------------
class FindTitleDefectTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_query_has_no_literal_and_none_without_issue_number(self):
        """5: no ``AND None`` in the volume query when no issue number."""
        queries = []

        def fake_find_volumes(volume_title, log, volumeid=None):
            queries.append(volume_title)
            return []

        original = utils.find_volumes
        utils.find_volumes = fake_find_volumes
        try:
            issue_number, _ = utils.find_title(FakeQuery(), "Saga", SimpleNamespace(
                debug=lambda *a, **k: None))
        finally:
            utils.find_volumes = original
        self.assertIsNone(issue_number)
        self.assertEqual(len(queries), 1)
        self.assertNotIn("AND None", queries[0])


# --------------------------------------------------------------------------
# score_title (defects 6a, 6b, 6c)
# --------------------------------------------------------------------------
def _stub_meta(series_index="1"):
    return SimpleNamespace(
        series="Saga", series_index=series_index, pubdate=None, comments=None
    )


class ScoreTitleDefectTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_title_none_returns_a_score(self):
        """6a: ``title=None`` must not raise ``TypeError``."""
        score = utils.score_title(
            _stub_meta(), title=None, issue_number="1", title_tokens=["saga"]
        )
        self.assertIsInstance(score, int)

    @unittest.expectedFailure
    def test_similarity_penalty_applied_once_not_per_token(self):
        """6b: the Levenshtein penalty must not scale with the token count.

        Both token lists are fully present in the volume text, so only the
        similarity penalty could make the scores differ.
        """
        if not hasattr(utils, "Levenshtein"):
            self.skipTest("Levenshtein module not available")
        kwargs = dict(title="saga #1 extra words", issue_number="1")
        one = utils.score_title(_stub_meta(), title_tokens=["saga"], **kwargs)
        three = utils.score_title(
            _stub_meta(), title_tokens=["saga", "saga", "saga"], **kwargs
        )
        self.assertEqual(one, three)

    @unittest.expectedFailure
    def test_real_metadata_float_series_index_scores_exact_match_zero(self):
        """6c: calibre documents ``series_index`` as a float field.  With a
        numeric index, ``series_index not in title`` raises ``TypeError`` and
        ``series_index != issue_number`` compares float with str.

        Confirmed under this calibre runtime: assigning the string that
        ``build_meta`` uses leaves ``series_index`` a ``str``, so only a
        numeric value (e.g. one loaded from a library) triggers the defect.
        """
        meta = Metadata("Saga #1", ["Brian K. Vaughan"])
        meta.series = "Saga"
        meta.series_index = 1.0
        score = utils.score_title(
            meta, title="saga #1", issue_number="1", title_tokens=["saga"]
        )
        self.assertEqual(score, 0)


# --------------------------------------------------------------------------
# keygen (defect 7)
# --------------------------------------------------------------------------
class KeygenDefectTests(unittest.TestCase):
    def _meta(self, cls):
        meta = cls("Title", ["Brian K. Vaughan"])
        meta.set_identifier("comicvine", "123")
        return meta

    @unittest.expectedFailure
    def test_string_and_int_identifier_of_equal_value_match(self):
        """7: ``"123"`` (from build_meta) must match ``123`` (from cli_main).

        Uses a ``get_identifier`` shim so the comparison itself is reached.
        """
        score = utils.keygen(
            self._meta(IdMetadata),
            authors=["Someone Else"],  # +10 unless the id fast path returns 0
            identifiers={"comicvine": 123},
        )
        self.assertEqual(score, 0)

    @unittest.expectedFailure
    def test_identifier_fast_path_works_with_stock_metadata(self):
        """7 (finding): the installed calibre ``Metadata`` has no
        ``get_identifier``, so the fast path never fires even for equal
        string identifiers."""
        meta = self._meta(Metadata)
        score = utils.keygen(
            meta,
            authors=["Someone Else"],
            identifiers={"comicvine": "123"},
        )
        self.assertEqual(score, 0)


# --------------------------------------------------------------------------
# retry_on_cv_error (defects 8a, 8b)
# --------------------------------------------------------------------------
class RetryDefectTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        ctx = self.clock.installed(("utils",))
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)

    @unittest.expectedFailure
    def test_zero_retries_still_calls_target_once(self):
        """8a: ``retries=0`` calls the target once and returns its result."""
        calls = []

        def target():
            calls.append(1)
            return "result"

        result = utils.retry_on_cv_error(retries=0)(target)()
        self.assertEqual(len(calls), 1)
        self.assertEqual(result, "result")

    @unittest.expectedFailure
    def test_no_sleep_after_final_failed_attempt(self):
        """8b (suspected, likely already correct, so an unexpected pass is
        probable): no back-off sleep follows the last failed attempt."""
        retries = 3

        def target():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            utils.retry_on_cv_error(retries=retries)(target)()
        # One back-off between each pair of attempts, none after the last.
        self.assertEqual(len(self.clock.sleeps), retries - 1)


# --------------------------------------------------------------------------
# build_meta (defects 9a, 9b)      -- task 8.2
# --------------------------------------------------------------------------
class _WarnLog:
    def warn(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class BuildMetaDefectTests(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.issue = default_fixtures()["issues"][0]

    @unittest.expectedFailure
    def test_non_numeric_issue_number_gives_numeric_series_index(self):
        """9a: a non-numeric issue number (``"Annual"``) must not leave a
        non-numeric ``series_index`` on the Metadata.

        Confirmed under this calibre runtime: ``Metadata.series_index`` does
        *not* coerce or reject the assignment, so ``build_meta`` does not
        raise; the string ``"Annual"`` is stored verbatim (and even ``"1"``
        stays a ``str``).  The defect is therefore that a non-numeric
        ``str`` ends up in a field calibre documents as a float.
        """
        self.issue.issue_number = "Annual"
        meta = utils.build_meta(_WarnLog(), self.issue)
        self.assertIsNotNone(meta)
        self.assertIsInstance(meta.series_index, (int, float))

    @unittest.expectedFailure
    def test_person_credits_none_is_tolerated(self):
        """9b: ``person_credits=None`` yields Metadata with no authors
        instead of ``TypeError``."""
        self.issue.person_credits = None
        meta = utils.build_meta(_WarnLog(), self.issue)
        self.assertIsNotNone(meta)


# --------------------------------------------------------------------------
# identify (defects 10a-10d)       -- task 8.2
# --------------------------------------------------------------------------
class _RecordingPool(ThreadPool):
    """Real ThreadPool that records close()/terminate() calls.

    Instances are always terminated at test cleanup so no thread leaks
    from the test itself.
    """

    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.closed_calls = 0
        _RecordingPool.instances.append(self)

    def close(self):
        self.closed_calls += 1
        super().close()

    def terminate(self):
        self.closed_calls += 1
        super().terminate()


class IdentifyDefectTests(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        add_isolation(self, worker_threads=2, max_volumes=5)
        self.source = Comicvine(None)
        self.log = mock.Mock()
        self.queue = Queue()
        self.volume = self.cv.volumes[0]

    def identify(self, abort=None, **kwargs):
        return self.source.identify(
            self.log, self.queue, abort or threading.Event(), **kwargs
        )

    @unittest.expectedFailure
    def test_abort_event_stops_work(self):
        """10a: a set ``abort`` event means nothing is queued."""
        abort = threading.Event()
        abort.set()
        self.identify(abort=abort, title="Saga #1")
        self.assertEqual(list(self.queue.queue), [])

    @unittest.expectedFailure
    def test_timeout_bounds_identify(self):
        """10b: ``timeout`` bounds how long ``identify`` waits for workers."""
        release = threading.Event()
        self.addCleanup(release.set)

        def slow_enqueue(log, result_queue, shutdown, issue):
            release.wait(1.5)

        self.source.enqueue = slow_enqueue
        start = time.monotonic()
        self.identify(title="Saga #1", timeout=0.1)
        elapsed = time.monotonic() - start
        release.set()
        self.assertLess(elapsed, 1.0)

    @unittest.expectedFailure
    def test_thread_pool_is_closed(self):
        """10c: the ThreadPool is closed (or terminated) after use."""
        _RecordingPool.instances = []
        with mock.patch.object(source_module, "ThreadPool", _RecordingPool):
            self.identify(title="Saga #1")
        pools = list(_RecordingPool.instances)
        for pool in pools:
            self.addCleanup(pool.terminate)
        self.assertEqual(len(pools), 1)
        self.assertGreaterEqual(pools[0].closed_calls, 1)

    @unittest.expectedFailure
    def test_empty_author_intersection_is_not_silent(self):
        """10d: when the author search is disjoint from the title
        candidates, fall back to the title candidates or log the fact."""
        other = MockPerson(id=5, name="Someone Else")
        other_issue = MockIssue(
            id=300099,
            name="Elsewhere",
            volume=MockVolume(id=1, name="Other Volume"),
            issue_number="7",
            person_credits=[other],
        )
        other.issues.append(other_issue)
        self.cv.people.append(other)
        self.identify(title="Saga #1", authors=["Someone Else"])
        queued = list(self.queue.queue)
        logged = any(
            getattr(self.log, name).called
            for name in ("info", "warn", "warning", "error")
        )
        self.assertTrue(queued or logged, "no results and nothing logged")


# --------------------------------------------------------------------------
# download_cover (defect 11)       -- task 8.2
# --------------------------------------------------------------------------
class DownloadCoverDefectTests(MockComicvineMixin, unittest.TestCase):
    @unittest.expectedFailure
    def test_cover_urls_failure_is_handled_and_logged(self):
        """11: a ``cover_urls`` failure is caught and logged, not raised."""
        source = Comicvine(None)
        log = FakeLog()
        queue = Queue()
        failure = RuntimeError("cover lookup failed")
        with mock.patch.object(utils, "cover_urls", side_effect=failure):
            source.download_cover(
                log, queue, None, identifiers={"comicvine": 300001}
            )
        self.assertEqual(len(log.exceptions), 1)
        self.assertTrue(queue.empty())




# --------------------------------------------------------------------------
# touched_fields identifier keys (defect 13, fixed in 0.14.4) -- normal tests
# --------------------------------------------------------------------------
class TouchedFieldsTests(unittest.TestCase):
    """Regression tests: calibre's ``Source.test_fields`` only recognises
    ``identifier:<type>`` (singular); ``identifiers:<type>`` was treated as a
    plain field name and could never be satisfied."""

    def test_touched_fields_are_plain_names_or_singular_identifiers(self):
        for field in Comicvine.touched_fields:
            if ":" in field:
                self.assertTrue(
                    field.startswith("identifier:"),
                    "%r must start with 'identifier:'" % field,
                )
                self.assertFalse(field.startswith("identifiers:"), field)
                self.assertTrue(field.partition(":")[2], field)
            else:
                self.assertTrue(field.isidentifier(), field)

    def test_comicvine_identifier_keys_are_declared(self):
        self.assertIn("identifier:comicvine", Comicvine.touched_fields)
        self.assertIn("identifier:comicvine-volume", Comicvine.touched_fields)

    def test_test_fields_accepts_metadata_with_both_identifiers(self):
        mi = Metadata("Saga", ["Brian K. Vaughan"])
        mi.comments = "A comic."
        mi.publisher = "Image"
        mi.pubdate = datetime.datetime(2012, 3, 14)
        mi.series = "Saga"
        mi.set_identifier("comicvine", "300001")
        mi.set_identifier("comicvine-volume", "100001")
        self.assertIsNone(Comicvine(None).test_fields(mi))

    def test_test_fields_reports_missing_identifier(self):
        mi = Metadata("Saga", ["Brian K. Vaughan"])
        mi.comments = "A comic."
        mi.publisher = "Image"
        mi.pubdate = datetime.datetime(2012, 3, 14)
        mi.series = "Saga"
        mi.set_identifier("comicvine", "300001")
        # calibre formats the message as "identifier: <name>" (with a space)
        missing = Comicvine(None).test_fields(mi)
        self.assertEqual(missing.replace(" ", ""), "identifier:comicvine-volume")


if __name__ == "__main__":
    unittest.main()
