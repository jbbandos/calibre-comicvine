"""Tests for ``Comicvine.download_cover`` (Requirement 4.9)."""
import struct
import unittest
import unittest.mock
import zlib
from queue import Queue

from calibre_plugins.comicvine.source import Comicvine

from tests.mock_comicvine import MockComicvineMixin

ORIGINAL = "http://mock.invalid/original.jpg"
SUPER = "http://mock.invalid/super.jpg"
MEDIUM = "http://mock.invalid/medium.jpg"
SMALL = "http://mock.invalid/small.jpg"


def png(width, height):
    """Tiny valid grayscale PNG of the given size (identify() reads the IHDR)."""

    def chunk(kind, data):
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# Different sizes by default, so both original and super are queued.
SIZES = {ORIGINAL: (20, 30), SUPER: (10, 15), MEDIUM: (6, 9), SMALL: (3, 4)}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


class FakeBrowser:
    """Stub browser: returns a PNG of ``sizes[url]`` unless the url is in ``fail``."""

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.sizes = dict(SIZES)
        self.opened = []

    def open_novisit(self, url, timeout=None):
        self.opened.append((url, timeout))
        if url in self.fail:
            raise IOError("boom")
        return FakeResponse(png(*self.sizes[url]))


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

    def test_original_and_super_queued_when_sizes_differ(self):
        self.download()
        self.assertEqual(
            self.drain(),
            [
                (self.source, png(*SIZES[ORIGINAL])),
                (self.source, png(*SIZES[SUPER])),
            ],
        )
        self.assertEqual([u for u, _ in self.browser.opened], [ORIGINAL, SUPER])

    def test_super_skipped_when_same_size_as_original(self):
        self.browser.sizes[SUPER] = SIZES[ORIGINAL]
        self.download()
        self.assertEqual(self.drain(), [(self.source, png(*SIZES[ORIGINAL]))])

    def test_super_queued_when_only_one_dimension_matches(self):
        self.browser.sizes[SUPER] = (SIZES[ORIGINAL][0], 99)
        self.download()
        self.assertEqual(len(self.drain()), 2)

    def test_medium_and_small_never_requested(self):
        self.download()
        self.assertEqual(
            [u for u, _ in self.browser.opened], [ORIGINAL, SUPER]
        )

    def test_best_cover_queues_only_original(self):
        self.download(get_best_cover=True)
        self.assertEqual(self.drain(), [(self.source, png(*SIZES[ORIGINAL]))])
        self.assertEqual([u for u, _ in self.browser.opened], [ORIGINAL])

    def test_best_cover_falls_back_to_super_when_original_fails(self):
        self.browser.fail.add(ORIGINAL)
        self.download(get_best_cover=True)
        self.assertEqual(self.drain(), [(self.source, png(*SIZES[SUPER]))])
        self.assertEqual([u for u, _ in self.browser.opened], [ORIGINAL, SUPER])
        self.assertEqual(len(self.log.exceptions), 1)

    def test_best_cover_all_fail_queues_nothing_and_logs(self):
        self.browser.fail.update({ORIGINAL, SUPER})
        self.download(get_best_cover=True)
        self.assertEqual(self.drain(), [])
        self.assertEqual(len(self.log.exceptions), 2)

    def test_timeout_passed_to_browser(self):
        self.download(timeout=7, get_best_cover=True)
        self.assertEqual(self.browser.opened, [(ORIGINAL, 7)])

    def test_no_comicvine_identifier_queues_nothing(self):
        self.download(identifiers={"isbn": "123"})
        self.download(identifiers=None)
        self.assertEqual(self.drain(), [])
        self.assertEqual(self.browser.opened, [])

    def test_failed_original_is_logged_and_super_still_queued(self):
        self.browser.fail.add(ORIGINAL)
        self.download()
        self.assertEqual(len(self.log.exceptions), 1)
        self.assertEqual(self.drain(), [(self.source, png(*SIZES[SUPER]))])

    def test_issue_without_images_queues_nothing(self):
        self.cv.issues[0].image = {}
        self.download()
        self.assertEqual(self.drain(), [])


if __name__ == "__main__":
    unittest.main()
