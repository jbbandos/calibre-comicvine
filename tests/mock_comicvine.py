"""
Mock_Comicvine: a test double for the ``pycomicvine`` module.

It offers the public surface the plugin touches (``Issue``, ``Issues``,
``Volume``, ``Volumes``, ``Person``, ``People``, ``hook_register``,
``hook_run`` and ``error``) backed by small in-memory fixture records.

Use ``with_mock_comicvine(testcase)`` (or ``MockComicvineMixin``) to swap the
mock into the plugin modules for the duration of a test.  The swap is undone
through ``addCleanup`` so it is restored even when the test body raises.
"""
import datetime
import socket
import unittest.mock
from dataclasses import dataclass, field

PLUGIN_PACKAGE = "calibre_plugins.comicvine"
# Plugin modules that hold a module-level ``pycomicvine`` name.
PATCHED_MODULES = ("source", "utils", "config")


# --------------------------------------------------------------------------
# Fixture records
# --------------------------------------------------------------------------
@dataclass
class MockPublisher:
    name: str = "Image"


@dataclass
class MockPerson:
    id: int
    name: str
    issues: list = field(default_factory=list)


@dataclass
class MockVolume:
    id: int
    name: str
    publisher: "MockPublisher | None" = None
    description: str = ""
    count_of_issues: int = 1


@dataclass
class MockIssue:
    id: int
    name: str
    volume: MockVolume
    issue_number: str
    person_credits: list  # list[MockPerson], or None to drive defect 9b
    description: str = ""
    store_date: "datetime.datetime | None" = None
    cover_date: "datetime.datetime | None" = None
    image: dict = field(default_factory=dict)

    # Issues are placed in sets by ``identify`` (author refinement).
    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, MockIssue) and other.id == self.id


def default_fixtures():
    """Build the default fixed data set: one volume, one issue, one person."""
    publisher = MockPublisher("Image")
    volume = MockVolume(
        id=49104,
        name="Saga",
        publisher=publisher,
        description="Volume description",
    )
    person = MockPerson(id=40439, name="Brian K. Vaughan")
    issue = MockIssue(
        id=300001,
        name="Chapter One",
        volume=volume,
        issue_number="1",
        person_credits=[person],
        description="Issue description",
        store_date=datetime.datetime(2012, 3, 14),
        cover_date=datetime.datetime(2012, 3, 1),
        image={
            "super_url": "http://mock.invalid/super.jpg",
            "medium_url": "http://mock.invalid/medium.jpg",
            "small_url": "http://mock.invalid/small.jpg",
        },
    )
    person.issues.append(issue)
    return {
        "volumes": [volume],
        "issues": [issue],
        "people": [person],
    }


# --------------------------------------------------------------------------
# The mock module
# --------------------------------------------------------------------------
class MockComicvine:
    """Module-shaped double for ``pycomicvine``.

    Attributes ``volumes``, ``issues`` and ``people`` hold the fixture records
    and may be replaced or extended by tests.  ``calls`` records every API call
    as ``(name, args, kwargs)``.  ``fail_with`` (an exception instance or
    class) makes every lookup raise, to drive error handling tests.
    """

    def __init__(self, fixtures=None):
        from calibre_plugins.comicvine.pycomicvine import error

        data = fixtures if fixtures is not None else default_fixtures()
        self.volumes = data["volumes"]
        self.issues = data["issues"]
        self.people = data["people"]
        self.error = error
        self.api_key = ""
        self.calls = []
        self.fail_with = None
        self.hooks = {}
        mock = self

        class _Base:
            def _enter(self, name, args, kwargs):
                mock._record(name, args, kwargs)

        class Volume(_Base):
            """Single volume lookup by id."""

            def __new__(cls, id, *args, **kwargs):
                mock._record("Volume", (id,) + args, kwargs)
                for volume in mock.volumes:
                    if volume.id == int(id):
                        return volume
                raise mock.error.ObjectNotFoundError("Volume %s" % id)

        class Volumes(_Base):
            """Volume search."""

            @classmethod
            def search(cls, query=None, field_list=None, **kwargs):
                mock._record("Volumes.search", (), dict(kwargs, query=query))
                return list(mock.volumes)

        class Issue(_Base):
            """Single issue lookup by id."""

            def __new__(cls, id, *args, **kwargs):
                mock._record("Issue", (id,) + args, kwargs)
                for issue in mock.issues:
                    if issue.id == int(id):
                        return issue
                raise mock.error.ObjectNotFoundError("Issue %s" % id)

        class Issues(_Base):
            """Issue listing filtered by ``volume:`` and ``issue_number:``."""

            def __new__(cls, filter=None, field_list=None, **kwargs):
                mock._record("Issues", (), dict(kwargs, filter=filter))
                volume_ids = None
                issue_number = None
                for part in (filter or "").split(","):
                    key, _, value = part.partition(":")
                    if key == "volume":
                        volume_ids = {int(v) for v in value.split("|") if v}
                    elif key == "issue_number":
                        issue_number = value
                return [
                    issue
                    for issue in mock.issues
                    if (volume_ids is None or issue.volume.id in volume_ids)
                    and (issue_number is None or issue.issue_number == issue_number)
                ]

        class Person(_Base):
            """Single person lookup by id."""

            def __new__(cls, id, *args, **kwargs):
                mock._record("Person", (id,) + args, kwargs)
                for person in mock.people:
                    if person.id == int(id):
                        return person
                raise mock.error.ObjectNotFoundError("Person %s" % id)

        class People(_Base):
            """Person listing filtered by ``name:``."""

            def __new__(cls, filter=None, field_list=None, **kwargs):
                mock._record("People", (), dict(kwargs, filter=filter))
                name = None
                for part in (filter or "").split(","):
                    key, _, value = part.partition(":")
                    if key == "name":
                        name = value.lower()
                return [
                    person
                    for person in mock.people
                    if name is None or name in person.name.lower()
                ]

        self.Volume = Volume
        self.Volumes = Volumes
        self.Issue = Issue
        self.Issues = Issues
        self.Person = Person
        self.People = People

    def _record(self, name, args, kwargs):
        self.calls.append((name, args, kwargs))
        if self.fail_with is not None:
            raise self.fail_with

    def hook_register(self, hook, function):
        self.hooks.setdefault(hook, []).append(function)

    def hook_run(self, hook, *args, **kwargs):
        for function in self.hooks.get(hook, []):
            function(*args, **kwargs)


# --------------------------------------------------------------------------
# Network guard
# --------------------------------------------------------------------------
def _refuse(address):
    if isinstance(address, tuple):
        host, port = address[0], address[1] if len(address) > 1 else None
    else:
        host, port = address, None
    raise AssertionError(
        "Offline test attempted a network connection to %s:%s" % (host, port)
    )


def install_socket_guard(testcase):
    """Make any socket connection attempt raise ``AssertionError``."""

    def guarded_connect(sock, address):
        _refuse(address)

    def guarded_create_connection(address, *args, **kwargs):
        _refuse(address)

    for patcher in (
        unittest.mock.patch.object(socket.socket, "connect", guarded_connect),
        unittest.mock.patch.object(socket.socket, "connect_ex", guarded_connect),
        unittest.mock.patch.object(
            socket, "create_connection", guarded_create_connection
        ),
    ):
        patcher.start()
        testcase.addCleanup(patcher.stop)


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------
def with_mock_comicvine(testcase, fixtures=None):
    """Swap ``pycomicvine`` for a MockComicvine for one test case.

    Patches the ``pycomicvine`` name in the plugin's ``source``, ``utils`` and
    ``config`` modules, installs the socket guard, and registers cleanups that
    restore everything unconditionally.  Returns the MockComicvine instance.
    """
    import importlib

    mock = MockComicvine(fixtures)
    for name in PATCHED_MODULES:
        module = importlib.import_module("%s.%s" % (PLUGIN_PACKAGE, name))
        patcher = unittest.mock.patch.object(module, "pycomicvine", mock)
        patcher.start()
        testcase.addCleanup(patcher.stop)
    install_socket_guard(testcase)
    return mock


class MockComicvineMixin:
    """TestCase mixin: ``self.cv`` is a fresh MockComicvine for every test."""

    def setUp(self):
        super().setUp()
        self.cv = with_mock_comicvine(self)
