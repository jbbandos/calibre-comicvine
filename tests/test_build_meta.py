"""Tests for ``utils.build_meta`` (Requirement 4.1)."""
import datetime
import unittest

from calibre_plugins.comicvine import utils

from .mock_comicvine import MockComicvineMixin, default_fixtures


class FakeLog:
    """Minimal calibre-style log recording warnings."""

    def __init__(self):
        self.warnings = []

    def warn(self, *args):
        self.warnings.append(args)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def fresh_issue():
    return default_fixtures()["issues"][0]


class BuildMetaTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.log = FakeLog()
        self.issue = fresh_issue()

    def build(self):
        return utils.build_meta(self.log, self.issue)

    def test_title_includes_volume_number_and_issue_name(self):
        self.assertEqual(self.build().title, "Saga #1: Chapter One")

    def test_title_without_issue_name(self):
        self.issue.name = None
        self.assertEqual(self.build().title, "Saga #1")

    def test_authors_come_from_person_credits(self):
        self.assertEqual(self.build().authors, ["Brian K. Vaughan"])

    def test_multiple_authors_keep_order(self):
        people = self.issue.person_credits
        people.append(type(people[0])(id=2, name="Fiona Staples"))
        self.assertEqual(
            self.build().authors, ["Brian K. Vaughan", "Fiona Staples"]
        )

    def test_series_and_series_index(self):
        meta = self.build()
        self.assertEqual(meta.series, "Saga")
        # build_meta assigns a str; this calibre's Metadata keeps it as a str
        # (no coercion), so float() is applied here before comparing.
        self.assertEqual(float(meta.series_index), 1.0)

    def test_series_index_from_other_issue_number(self):
        self.issue.issue_number = "12"
        self.assertEqual(float(self.build().series_index), 12.0)

    def test_identifiers(self):
        self.assertEqual(
            self.build().get_identifiers(),
            {"comicvine": "300001", "comicvine-volume": "49104"},
        )

    def test_comments_use_issue_description(self):
        self.assertEqual(self.build().comments, "Issue description")

    def test_comments_fall_back_to_volume_description(self):
        self.issue.description = ""
        self.assertEqual(self.build().comments, "Volume description")

    def test_pubdate_prefers_store_date(self):
        pubdate = self.build().pubdate
        self.assertEqual((pubdate.year, pubdate.month, pubdate.day), (2012, 3, 14))

    def test_pubdate_falls_back_to_cover_date(self):
        self.issue.store_date = None
        pubdate = self.build().pubdate
        self.assertEqual((pubdate.year, pubdate.month, pubdate.day), (2012, 3, 1))

    def test_publisher(self):
        self.assertEqual(self.build().publisher, "Image")

    def test_no_publisher(self):
        self.issue.volume.publisher = None
        self.assertFalse(self.build().publisher)

    def test_has_cover_reflects_image(self):
        self.assertTrue(self.build().has_cover)
        self.issue.image = {}
        self.assertFalse(self.build().has_cover)

    def test_none_issue_returns_none_and_warns(self):
        self.assertIsNone(utils.build_meta(self.log, None))
        self.assertEqual(len(self.log.warnings), 1)

    def test_issue_without_volume_returns_none(self):
        self.issue.volume = None
        self.assertIsNone(self.build())
        self.assertEqual(len(self.log.warnings), 1)


if __name__ == "__main__":
    unittest.main()
