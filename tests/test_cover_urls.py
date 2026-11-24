"""Tests for ``utils.cover_urls`` (Requirement 4.4)."""
import unittest

from calibre_plugins.comicvine import utils

from tests.mock_comicvine import MockComicvineMixin

SUPER = "http://mock.invalid/super.jpg"
MEDIUM = "http://mock.invalid/medium.jpg"
SMALL = "http://mock.invalid/small.jpg"


class CoverUrlsTest(MockComicvineMixin, unittest.TestCase):
    def issue_id(self):
        return self.cv.issues[0].id

    def test_all_urls_in_quality_order_without_best_cover(self):
        urls = list(utils.cover_urls(self.issue_id()))
        self.assertEqual(urls, [SUPER, MEDIUM, SMALL])

    def test_best_cover_yields_only_first_url(self):
        urls = list(utils.cover_urls(self.issue_id(), get_best_cover=True))
        self.assertEqual(urls, [SUPER])

    def test_best_cover_falls_back_to_next_available_size(self):
        self.cv.issues[0].image = {"medium_url": MEDIUM, "small_url": SMALL}
        urls = list(utils.cover_urls(self.issue_id(), get_best_cover=True))
        self.assertEqual(urls, [MEDIUM])

    def test_missing_sizes_are_skipped(self):
        self.cv.issues[0].image = {"small_url": SMALL}
        self.assertEqual(list(utils.cover_urls(self.issue_id())), [SMALL])

    def test_no_images_yields_nothing(self):
        self.cv.issues[0].image = {}
        self.assertEqual(list(utils.cover_urls(self.issue_id())), [])
        self.assertEqual(
            list(utils.cover_urls(self.issue_id(), get_best_cover=True)), []
        )

    def test_string_id_is_converted_to_int(self):
        urls = list(utils.cover_urls(str(self.issue_id())))
        self.assertEqual(urls, [SUPER, MEDIUM, SMALL])


if __name__ == "__main__":
    unittest.main()
