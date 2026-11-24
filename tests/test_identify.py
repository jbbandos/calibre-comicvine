"""Tests for ``Comicvine.identify`` (Requirement 4.7)."""
import threading
import unittest
from queue import Queue
from unittest import mock

from calibre_plugins.comicvine.source import Comicvine

from .fixtures import add_isolation
from .mock_comicvine import MockComicvineMixin, MockIssue, MockPerson


class IdentifyTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        add_isolation(self, worker_threads=2, max_volumes=5)
        self.source = Comicvine(None)
        self.log = mock.Mock()
        self.queue = Queue()
        self.volume = self.cv.volumes[0]

    def identify(self, **kwargs):
        return self.source.identify(
            self.log, self.queue, threading.Event(), **kwargs
        )

    def results(self):
        return list(self.queue.queue)

    def add_issue(self, issue_id, number, name, credits=()):
        issue = MockIssue(
            id=issue_id,
            name=name,
            volume=self.volume,
            issue_number=number,
            person_credits=list(credits),
        )
        self.cv.issues.append(issue)
        return issue

    def test_title_with_issue_number_queues_matching_result(self):
        self.add_issue(300002, "2", "Chapter Two")
        self.assertIsNone(self.identify(title="Saga #1"))
        results = self.results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Saga #1: Chapter One")
        self.assertEqual(results[0].identifiers["comicvine"], "300001")
        self.assertEqual(results[0].identifiers["comicvine-volume"], "49104")

    def test_title_without_issue_number_queues_all_volume_issues(self):
        self.add_issue(300002, "2", "Chapter Two")
        self.identify(title="Saga")
        ids = sorted(m.identifiers["comicvine"] for m in self.results())
        self.assertEqual(ids, ["300001", "300002"])

    def test_missing_issue_number_falls_back_to_volume_issues(self):
        # Issue 9 does not exist, so identify retries without the number.
        self.identify(title="Saga #9")
        self.assertEqual(len(self.results()), 1)

    def test_comicvine_identifier_looks_up_issue_directly(self):
        self.identify(identifiers={"comicvine": "300001"})
        results = self.results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].identifiers["comicvine"], "300001")
        names = [call[0] for call in self.cv.calls]
        self.assertEqual(names, ["Issue"])

    def test_comicvine_identifier_accepts_int(self):
        self.identify(identifiers={"comicvine": 300001})
        self.assertEqual(len(self.results()), 1)

    def test_volume_identifier_restricts_search(self):
        self.identify(title="Saga #1", identifiers={"comicvine-volume": "49104"})
        self.assertEqual(len(self.results()), 1)
        self.assertIn("Volume", [call[0] for call in self.cv.calls])

    def test_authors_refine_candidates(self):
        other = MockPerson(id=5, name="Someone Else")
        other_issue = self.add_issue(300003, "1", "Other", [other])
        other.issues.append(other_issue)
        self.identify(title="Saga", authors=["Vaughan"])
        ids = [m.identifiers["comicvine"] for m in self.results()]
        self.assertEqual(ids, ["300001"])

    def test_no_matching_volume_queues_nothing(self):
        self.cv.volumes = []
        self.identify(title="Nothing #1")
        self.assertEqual(self.results(), [])

    def test_no_title_or_identifiers_queues_nothing(self):
        self.assertIsNone(self.identify())
        self.assertEqual(self.results(), [])
        self.assertEqual(self.cv.calls, [])


if __name__ == "__main__":
    unittest.main()
