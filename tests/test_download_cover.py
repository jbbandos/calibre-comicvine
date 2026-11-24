"""Tests for ``Comicvine.download_cover`` (Requirement 4.9)."""
import unittest
import unittest.mock
from queue import Queue

from calibre_plugins.comicvine.source import Comicvine

from tests.mock_comicvine import MockComicvineMixin

SUPER = "http://mock.invalid/super.jpg"
MEDIUM = "http://mock.invalid/medium.jpg"
SMALL = "http://mock.invalid/small.jpg"


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


class FakeBrowser:
    """Stub browser: returns ``b"data:<url>"`` unless the url is in ``fail``."""

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.opened = []

    def open_novisit(self, url, timeout=None):
        self.opened.append((url, timeout))
        if url in self.fail:
            raise IOError("boom")
        return FakeResponse(b"data:" + url.encode())


class FakeLog:
    def __init__(self):
        self.messages = []
        self.exceptions = []

    def __call__(self, *args):
        self.messages.append(args)

    def exception(self, *args):
        self.exceptions.append(args)


class DownloadCoverTest(MockComicvineMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.source = Comicvine(None)
        self.browser = FakeBrowser()
        patcher = unittest.mock.patch.object(
            Comicvine,
            "browser",
            new_callable=unittest.mock.PropertyMock,
            return_value=self.browser,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log = FakeLog()
        self.queue = Queue()
        self.issue_id = self.cv.issues[0].id

    def drain(self):
        items = []
        while not self.queue.empty():
            items.append(self.queue.get())
        return items

    def download(self, **kwargs):
        kwargs.setdefault("identifiers", {"comicvine": self.issue_id})
        return self.source.download_cover(
            self.log, self.queue, None, **kwargs
        )

    def test_all_covers_put_on_queue_with_source(self):
        self.download()
        self.assertEqual(
            self.drain(),
            [
                (self.source, b"data:" + SUPER.encode()),
                (self.source, b"data:" + MEDIUM.encode()),
                (self.source, b"data:" + SMALL.encode()),
            ],
        )

    def test_best_cover_queues_only_first(self):
        self.download(get_best_cover=True)
        self.assertEqual(self.drain(), [(self.source, b"data:" + SUPER.encode())])
        self.assertEqual([u for u, _ in self.browser.opened], [SUPER])

    def test_timeout_passed_to_browser(self):
        self.download(timeout=7, get_best_cover=True)
        self.assertEqual(self.browser.opened, [(SUPER, 7)])

    def test_no_comicvine_identifier_queues_nothing(self):
        self.download(identifiers={"isbn": "123"})
        self.download(identifiers=None)
        self.assertEqual(self.drain(), [])
        self.assertEqual(self.browser.opened, [])

    def test_failed_download_is_logged_and_next_url_still_tried(self):
        self.browser.fail.add(SUPER)
        self.download()
        self.assertEqual(len(self.log.exceptions), 1)
        self.assertEqual(
            self.drain(),
            [
                (self.source, b"data:" + MEDIUM.encode()),
                (self.source, b"data:" + SMALL.encode()),
            ],
        )

    def test_issue_without_images_queues_nothing(self):
        self.cv.issues[0].image = {}
        self.download()
        self.assertEqual(self.drain(), [])


if __name__ == "__main__":
    unittest.main()
