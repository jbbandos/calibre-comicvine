"""Tests for ``utils.find_authors`` (Requirement 4.3)."""
import unittest

from calibre_plugins.comicvine import utils

from .mock_comicvine import MockComicvineMixin, MockPerson


class StubLog:
    def __init__(self):
        self.messages = []

    def debug(self, *args):
        self.messages.append(" ".join(str(a) for a in args))

    info = warn = error = exception = debug


class StubQuery:
    """Stands in for the calibre ``Source`` that tokenises author names."""

    def get_author_tokens(self, authors, only_first_author=True):
        tokens = []
        for author in authors:
            tokens.extend(author.split())
        return tokens


class FindAuthorsTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.log = StubLog()
        self.query = StubQuery()

    def find(self, authors):
        return utils.find_authors(self.query, authors, self.log)

    def test_matching_author_returns_person(self):
        result = self.find(["Brian K. Vaughan"])
        self.assertEqual([p.name for p in result], ["Brian K. Vaughan"])

    def test_matching_author_searches_by_name_filter(self):
        self.find(["Brian K. Vaughan"])
        people_calls = [c for c in self.cv.calls if c[0] == "People"]
        self.assertEqual(len(people_calls), 1)
        self.assertEqual(people_calls[0][2]["filter"], "name:Brian K. Vaughan")

    def test_matching_author_fetches_person_by_id(self):
        self.find(["Brian K. Vaughan"])
        person_calls = [c for c in self.cv.calls if c[0] == "Person"]
        self.assertEqual(person_calls[0][1], (40439,))

    def test_non_matching_author_returns_empty(self):
        self.assertEqual(self.find(["Nobody Atall"]), [])

    def test_non_matching_author_does_not_fetch_person(self):
        self.find(["Nobody Atall"])
        self.assertFalse([c for c in self.cv.calls if c[0] == "Person"])

    def test_empty_author_list_returns_empty_without_api_calls(self):
        self.assertEqual(self.find([]), [])
        self.assertEqual(self.cv.calls, [])

    def test_unknown_author_is_skipped(self):
        self.assertEqual(self.find(["Unknown"]), [])
        self.assertEqual(self.cv.calls, [])

    def test_blank_author_is_skipped(self):
        self.assertEqual(self.find([""]), [])
        self.assertEqual(self.cv.calls, [])

    def test_mixed_authors_return_only_matches(self):
        fiona = MockPerson(id=40440, name="Fiona Staples")
        self.cv.people.append(fiona)
        result = self.find(["Brian K. Vaughan", "Nobody Atall", "Fiona Staples"])
        self.assertEqual(
            [p.name for p in result], ["Brian K. Vaughan", "Fiona Staples"]
        )

    def test_logs_match_count(self):
        self.find(["Brian K. Vaughan"])
        self.assertIn("1 matches found", self.log.messages)


if __name__ == "__main__":
    unittest.main()
