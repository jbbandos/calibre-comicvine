"""Tests for ``utils.find_volumes`` and ``utils.find_issues`` (Requirement 4.2)."""
import unittest
from unittest import mock

from calibre_plugins.comicvine import utils

from .fixtures import add_isolation
from .mock_comicvine import MockComicvineMixin, MockIssue, MockVolume


class FindVolumesTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.prefs, _ = add_isolation(self, max_volumes=2)
        self.log = mock.Mock()

    def test_title_query_returns_matching_volumes(self):
        volumes = utils.find_volumes("saga", self.log)
        self.assertEqual(volumes, self.cv.volumes)
        name, _args, kwargs = self.cv.calls[-1]
        self.assertEqual(name, "Volumes.search")
        self.assertEqual(kwargs["query"], "saga")

    def test_title_query_is_capped_at_max_volumes(self):
        self.cv.volumes = [MockVolume(id=i, name="Saga %d" % i) for i in range(1, 6)]
        volumes = utils.find_volumes("saga", self.log)
        self.assertEqual([v.id for v in volumes], [1, 2])

    def test_volume_identifier_looks_up_that_volume(self):
        volumes = utils.find_volumes("ignored title", self.log, volumeid=49104)
        self.assertEqual(volumes, [self.cv.volumes[0]])
        names = [call[0] for call in self.cv.calls]
        self.assertEqual(names, ["Volume"])

    def test_empty_result(self):
        self.cv.volumes = []
        self.assertEqual(utils.find_volumes("nothing", self.log), [])


class FindIssuesTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.log = mock.Mock()
        self.volume = self.cv.volumes[0]

    def test_title_query_with_issue_number(self):
        issues = utils.find_issues([self.volume], "1", self.log)
        self.assertEqual(issues, self.cv.issues)
        _name, _args, kwargs = self.cv.calls[-1]
        self.assertEqual(kwargs["filter"], "volume:49104,issue_number:1")

    def test_without_issue_number_returns_all_volume_issues(self):
        second = MockIssue(
            id=300002,
            name="Chapter Two",
            volume=self.volume,
            issue_number="2",
            person_credits=[],
        )
        self.cv.issues.append(second)
        issues = utils.find_issues([self.volume], None, self.log)
        self.assertEqual([i.id for i in issues], [300001, 300002])
        _name, _args, kwargs = self.cv.calls[-1]
        self.assertEqual(kwargs["filter"], "volume:49104")

    def test_volume_identifier_flow(self):
        volumes = utils.find_volumes("x", self.log, volumeid=self.volume.id)
        issues = utils.find_issues(volumes, "1", self.log)
        self.assertEqual([i.id for i in issues], [300001])

    def test_multiple_volumes_joined_in_filter(self):
        other = MockVolume(id=7, name="Other")
        utils.find_issues([self.volume, other], "1", self.log)
        _name, _args, kwargs = self.cv.calls[-1]
        self.assertEqual(kwargs["filter"], "volume:49104|7,issue_number:1")

    def test_empty_result(self):
        self.assertEqual(utils.find_issues([self.volume], "99", self.log), [])

    def test_no_volumes_is_empty(self):
        self.assertEqual(utils.find_issues([], "1", self.log), [])


if __name__ == "__main__":
    unittest.main()
