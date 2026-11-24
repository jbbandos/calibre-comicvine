"""
Shared test fixtures: a controllable clock and isolated configuration stores.

Nothing here touches the real calibre configuration files on disk.
"""
import contextlib
import importlib
import types
import unittest.mock

PLUGIN_PACKAGE = "calibre_plugins.comicvine"
PREFS_MODULES = ("source", "utils", "config")


class FakeClock:
    """Controllable clock.  ``sleep`` advances time instead of blocking."""

    def __init__(self, start=1000.0):
        self._now = float(start)
        self.sleeps = []

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.advance(seconds)

    def as_time_module(self):
        """A stand-in for the ``time`` module (``time`` and ``sleep`` only)."""
        return types.SimpleNamespace(time=self.now, sleep=self.sleep)

    @contextlib.contextmanager
    def installed(self, module_names=("utils",)):
        """Patch the ``time`` name in the given plugin modules."""
        patchers = []
        for name in module_names:
            module = importlib.import_module("%s.%s" % (PLUGIN_PACKAGE, name))
            patchers.append(
                unittest.mock.patch.object(module, "time", self.as_time_module())
            )
        for patcher in patchers:
            patcher.start()
        try:
            yield self
        finally:
            for patcher in reversed(patchers):
                patcher.stop()


class DictConfig(dict):
    """Dict-backed stand-in for ``JSONConfig`` (``defaults``, ``refresh``)."""

    def __init__(self, name=None, defaults=None):
        super().__init__()
        self.name = name
        self.defaults = dict(defaults or {})

    def __missing__(self, key):
        return self.defaults[key]

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return self.defaults[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def refresh(self):
        pass


@contextlib.contextmanager
def isolated_jsonconfig(name=None):
    """Redirect ``utils.JSONConfig`` to in-memory stores.

    Yields a dict mapping each requested config name to its DictConfig, so a
    test can inspect or seed ``TokenBucket`` state.  The original
    ``JSONConfig`` is restored on exit, and nothing is written to disk.
    """
    from calibre_plugins.comicvine import utils

    stores = {}

    def factory(config_name):
        stores[config_name] = DictConfig(config_name)
        return stores[config_name]

    with unittest.mock.patch.object(utils, "JSONConfig", factory):
        yield stores


@contextlib.contextmanager
def isolated_prefs(**overrides):
    """Replace the module-level ``PREFS`` with an in-memory store.

    The store starts from the plugin's declared defaults (so any API key in
    the user's real Prefs is neither read nor modified), updated with
    ``overrides``.  The original PREFS objects are restored on exit, so
    mutations made during a test cannot leak into later tests or the user's
    calibre configuration.  Yields the stand-in store.
    """
    from calibre_plugins.comicvine import config

    store = DictConfig("plugins/comicvine", config.PREFS.defaults)
    store["api_key"] = ""
    store.update(overrides)
    patchers = []
    for name in PREFS_MODULES:
        module = importlib.import_module("%s.%s" % (PLUGIN_PACKAGE, name))
        patchers.append(unittest.mock.patch.object(module, "PREFS", store))
    for patcher in patchers:
        patcher.start()
    try:
        yield store
    finally:
        for patcher in reversed(patchers):
            patcher.stop()


def add_isolation(testcase, **prefs_overrides):
    """Enter both isolation fixtures for one test case via ``addCleanup``.

    Returns ``(prefs, json_stores)``.
    """
    stack = contextlib.ExitStack()
    testcase.addCleanup(stack.close)
    prefs = stack.enter_context(isolated_prefs(**prefs_overrides))
    stores = stack.enter_context(isolated_jsonconfig())
    return prefs, stores
