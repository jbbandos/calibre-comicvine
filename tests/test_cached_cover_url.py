"""Tests for the cover URL cached by ``enqueue`` and returned by
``Comicvine.get_cached_cover_url``."""
import threading
import unittest
from queue import Queue
from calibre_plugins.comicvine.source import Comicvine
from .mock_comicvine import MockComicvineMixin, default_fixtures


class FakeLog:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class CachedCoverUrlTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.source = Comicvine(None)
        self.issue = default_fixtures()["issues"][0]

    def enqueue(self):
        self.source.enqueue(
            FakeLog(), Queue(), threading.Event(), self.issue
        )

    def test_original_is_preferred_for_str_and_int_ids_for_str_and_int_ids(self):
        self.enqueue()
        for cv_id in ("300001", 300001):
            self.assertEqual(
                self.source.get_cached_cover_url({"comicvine": cv_id}),
                "http://mock.invalid/original.jpg",
            )

    def test_issue_without_image_gives_none(self):
        self.issue.image = {}
        self.enqueue()
        self.assertIsNone(
            self.source.get_cached_cover_url({"comicvine": "300001"})
        )

    def test_super_url_used_when_no_original(self):
        self.issue.image = {
            "super_url": "http://mock.invalid/super.jpg",
            "medium_url": "http://mock.invalid/medium.jpg",
        }
        self.enqueue()
        self.assertEqual(
            self.source.get_cached_cover_url({"comicvine": "300001"}),
            "http://mock.invalid/super.jpg",
        )

    def test_only_medium_url_is_not_cached(self):
        self.issue.image = {"medium_url": "http://mock.invalid/medium.jpg"}
        self.enqueue()
        self.assertIsNone(
            self.source.get_cached_cover_url({"comicvine": "300001"})
        )

    def test_missing_identifier_gives_none(self):
        self.enqueue()
        for identifiers in (None, {}, {"isbn": "1"}, {"comicvine": ""},
                            {"comicvine": None}):
            self.assertIsNone(self.source.get_cached_cover_url(identifiers))
