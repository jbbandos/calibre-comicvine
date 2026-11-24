"""Tests for ``Comicvine.enqueue`` (Requirement 4.8)."""
import threading
import unittest
import unittest.mock
from queue import Queue

from calibre.ebooks.metadata.book.base import Metadata
from calibre_plugins.comicvine.source import Comicvine

from .mock_comicvine import MockComicvineMixin, default_fixtures


class FakeLog:
    def __init__(self):
        self.warnings = []

    def warn(self, *args):
        self.warnings.append(args)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class EnqueueTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.source = Comicvine(None)
        self.log = FakeLog()
        self.queue = Queue()
        self.shutdown = threading.Event()
        self.issue = default_fixtures()["issues"][0]

    def enqueue(self, issue=None):
        self.source.enqueue(
            self.log, self.queue, self.shutdown, issue or self.issue
        )

    def test_built_metadata_is_queued(self):
        self.enqueue()
        self.assertEqual(self.queue.qsize(), 1)
        meta = self.queue.get_nowait()
        self.assertIsInstance(meta, Metadata)
        self.assertEqual(meta.title, "Saga #1: Chapter One")
        self.assertEqual(meta.authors, ["Brian K. Vaughan"])

    def test_queued_metadata_carries_comicvine_identifiers(self):
        self.enqueue()
        meta = self.queue.get_nowait()
        self.assertEqual(
            meta.get_identifiers(),
            {"comicvine": "300001", "comicvine-volume": "49104"},
        )

    def test_metadata_is_cleaned_by_the_plugin_source(self):
        with unittest.mock.patch.object(
            self.source,
            "clean_downloaded_metadata",
            wraps=self.source.clean_downloaded_metadata,
        ) as clean:
            self.enqueue()
        meta = self.queue.get_nowait()
        clean.assert_called_once_with(meta)

    def test_each_issue_adds_one_entry(self):
        self.enqueue()
        self.enqueue()
        self.assertEqual(self.queue.qsize(), 2)

    def test_shutdown_raises_and_queues_nothing(self):
        self.shutdown.set()
        with self.assertRaises(threading.ThreadError):
            self.enqueue()
        self.assertTrue(self.queue.empty())

    def test_issue_that_builds_no_metadata_is_not_queued(self):
        self.issue.volume = None
        self.enqueue()
        self.assertTrue(self.queue.empty())
        self.assertEqual(len(self.log.warnings), 1)


if __name__ == "__main__":
    unittest.main()
