"""
Tests for ``utils.normalised_title`` (Requirement 3.1).

``normalised_title(query, title)`` only uses ``query.get_title_tokens``, so a
small deterministic query stand-in is used for tokenisation.  Non-``str``
input is covered by the Expected_Failure tests in ``test_defects.py``.
"""
import random
import re
import unittest

from calibre_plugins.comicvine import utils

ARTICLES = {"the", "a", "an"}


class FakeQuery:
    """Tokenises on word characters and drops leading articles."""

    def get_title_tokens(self, title):
        tokens = re.findall(r"\w+", title)
        if tokens and tokens[0].lower() in ARTICLES:
            tokens = tokens[1:]
        return tokens


def norm(title):
    return utils.normalised_title(FakeQuery(), title)


class TestNormalisedTitleIssueNumbers(unittest.TestCase):
    def test_explicit_hash_issue_number(self):
        self.assertEqual(norm("Saga #12"), ("12", ["saga"]))

    def test_bare_trailing_number_is_issue_number(self):
        self.assertEqual(norm("Saga 12"), ("12", ["saga"]))

    def test_leading_zeros_stripped(self):
        self.assertEqual(norm("Saga #012"), ("12", ["saga"]))

    def test_text_after_issue_number_ignored(self):
        self.assertEqual(norm("Saga #12: Some Subtitle"), ("12", ["saga"]))

    def test_no_issue_number(self):
        self.assertEqual(norm("Saga"), (None, ["saga"]))

    def test_half_issue(self):
        self.assertEqual(norm("Wolverine #\xbd"), ("\xbd", ["wolverine"]))


class TestNormalisedTitleCleanup(unittest.TestCase):
    def test_parenthesised_text_removed(self):
        self.assertEqual(norm("Batman (2016) #45"), ("45", ["batman"]))

    def test_of_n_removed(self):
        self.assertEqual(norm("Watchmen #1 (of 12)"), ("1", ["watchmen"]))

    def test_volume_marker_removed(self):
        self.assertEqual(norm("batman vol 2 #5"), ("5", ["batman"]))

    def test_dotted_initials_collapsed(self):
        issue, tokens = norm("S.H.I.E.L.D. #3")
        self.assertEqual(issue, "3")
        self.assertEqual(tokens, ["shield"])

    def test_punctuation_not_in_tokens(self):
        issue, tokens = norm("Spider-Man: Homecoming #3")
        self.assertEqual(issue, "3")
        self.assertEqual(tokens, ["spider", "man", "homecoming"])

    def test_leading_article_dropped(self):
        self.assertEqual(norm("The Walking Dead #5"), ("5", ["walking", "dead"]))

    def test_tokens_lowercased(self):
        self.assertEqual(norm("SAGA #1")[1], ["saga"])


class TestNormalisedTitleEmpty(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(norm(""), (None, []))

    def test_whitespace_only(self):
        self.assertEqual(norm("   "), (None, []))


class TestNormalisedTitleProperties(unittest.TestCase):
    """Randomised checks over generated 'name #number' titles."""

    def test_generated_titles_roundtrip(self):
        rng = random.Random(3101)
        words = ["saga", "batman", "hawkeye", "monstress", "nimona", "paper"]
        for _ in range(100):
            name = rng.sample(words, rng.randint(1, 3))
            number = rng.randint(1, 999)
            title = " ".join(w.capitalize() for w in name) + " #%d" % number
            issue, tokens = norm(title)
            self.assertEqual(issue, str(number), title)
            self.assertEqual(tokens, name, title)
            self.assertTrue(all(t == t.lower() for t in tokens), title)


if __name__ == "__main__":
    unittest.main()
