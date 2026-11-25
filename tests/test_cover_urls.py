"""Tests for ``utils.cover_urls`` (Requirement 4.4)."""
import unittest

from calibre_plugins.comicvine import utils

from tests.mock_comicvine import MockComicvineMixin

ORIGINAL = "http://mock.invalid/original.jpg"
SUPER = "http://mock.invalid/super.jpg"
MEDIUM = "http://mock.invalid/medium.jpg"
SMALL = "http://mock.invalid/small.jpg"


class CoverUrlsTest(MockComicvineMixin, unittest.TestCase):
    def issue_id(self):
        return self.cv.issues[0].id

    def test_original_then_super_without_best_cover(self):
        urls = list(utils.cover_urls(self.issue_id()))
        self.assertEqual(urls, [ORIGINAL, SUPER])

    def test_medium_and_small_are_never_yielded(self):
        urls = list(utils.cover_urls(self.issue_id()))
        self.assertNotIn(MEDIUM, urls)
        self.assertNotIn(SMALL, urls)

    def test_best_cover_yields_only_first_url(self):
        urls = list(utils.cover_urls(self.issue_id(), get_best_cover=True))
        self.assertEqual(urls, [ORIGINAL])

    def test_best_cover_falls_back_to_super_without_original(self):
        self.cv.issues[0].image = {"super_url": SUPER, "medium_url": MEDIUM}
        urls = list(utils.cover_urls(self.issue_id(), get_best_cover=True))
        self.assertEqual(urls, [SUPER])

    def test_only_medium_and_small_yields_nothing(self):
        self.cv.issues[0].image = {"medium_url": MEDIUM, "small_url": SMALL}
        self.assertEqual(list(utils.cover_urls(self.issue_id())), [])

    def test_no_images_yields_nothing(self):
        self.cv.issues[0].image = {}
        self.assertEqual(list(utils.cover_urls(self.issue_id())), [])
        self.assertEqual(
            list(utils.cover_urls(self.issue_id(), get_best_cover=True)), []
        )

    def test_string_id_is_converted_to_int(self):
        urls = list(utils.cover_urls(str(self.issue_id())))
        self.assertEqual(urls, [ORIGINAL, SUPER])


if __name__ == "__main__":
    unittest.main()
