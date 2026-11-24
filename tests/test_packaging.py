"""Packaging example tests (Requirements 6.1, 6.3, 6.4).

These tests read files as text only and never import calibre.
"""
import ast
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "MANIFEST")
SOURCE_PATH = os.path.join(REPO_ROOT, "source.py")


def read_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def plugin_class_attributes():
    """Return literal class attributes of the Source subclass in source.py."""
    with open(SOURCE_PATH, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=SOURCE_PATH)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = [
            getattr(base, "id", getattr(base, "attr", None)) for base in node.bases
        ]
        if "Source" not in base_names:
            continue
        attrs = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        attrs[target.id] = ast.literal_eval(stmt.value)
                    except ValueError:
                        pass
        return node.name, attrs
    raise AssertionError("no Source subclass found in source.py")


class ManifestTests(unittest.TestCase):
    def test_every_manifest_entry_exists(self):
        entries = read_manifest()
        self.assertTrue(entries, "MANIFEST is empty")
        missing = [e for e in entries if not os.path.isfile(os.path.join(REPO_ROOT, e))]
        self.assertEqual(missing, [], "MANIFEST lists missing files: %s" % missing)

    def test_import_name_file_listed(self):
        self.assertIn("plugin-import-name-comicvine.txt", read_manifest())


class PluginClassDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.class_name, self.attrs = plugin_class_attributes()

    def test_declares_name(self):
        self.assertIsInstance(self.attrs.get("name"), str)
        self.assertTrue(self.attrs["name"])

    def test_declares_version_tuple(self):
        version = self.attrs.get("version")
        self.assertIsInstance(version, tuple)
        self.assertTrue(version)
        self.assertTrue(all(isinstance(part, int) for part in version))

    def test_declares_minimum_calibre_version(self):
        minimum = self.attrs.get("minimum_calibre_version")
        self.assertIsInstance(minimum, tuple)
        self.assertTrue(minimum)
        self.assertTrue(all(isinstance(part, int) for part in minimum))


PLUGIN_PACKAGE = ["calibre_plugins", "comicvine"]


def _module_file(parts):
    """Map repo-relative module parts to an existing repo file, or None."""
    if not parts:
        candidates = ["__init__.py"]
    else:
        base = "/".join(parts)
        candidates = [base + ".py", base + "/__init__.py"]
    for candidate in candidates:
        if os.path.isfile(os.path.join(REPO_ROOT, candidate)):
            return candidate
    return None


def _ancestor_inits(parts):
    """Package __init__.py files that must exist for a module to import."""
    needed = ["__init__.py"] if _module_file([]) else []
    for i in range(1, len(parts)):
        init = "/".join(parts[:i]) + "/__init__.py"
        if os.path.isfile(os.path.join(REPO_ROOT, init)):
            needed.append(init)
    return needed


def in_repo_imports(rel_path):
    """Return repo files (relative paths) imported by the given plugin file."""
    with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=rel_path)
    pkg = rel_path.split("/")[:-1]  # package of this file, repo-relative
    found = set()

    def add(parts):
        target = _module_file(parts)
        if target:
            found.add(target)
            found.update(_ancestor_inits(parts))
            return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")
                if name[: len(PLUGIN_PACKAGE)] == PLUGIN_PACKAGE:
                    add(name[len(PLUGIN_PACKAGE):])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                base = base + (node.module.split(".") if node.module else [])
            else:
                mod = (node.module or "").split(".")
                if mod[: len(PLUGIN_PACKAGE)] != PLUGIN_PACKAGE:
                    continue
                base = mod[len(PLUGIN_PACKAGE):]
            add(base)
            for alias in node.names:  # `from pkg import submodule`
                add(base + [alias.name])
    found.discard(rel_path)
    return found


class ManifestImportCoverageTests(unittest.TestCase):
    """Property 6: Manifest covers every file it must (Requirements 6.1, 6.2)."""

    def test_manifest_covers_in_repo_imports(self):
        manifest = set(read_manifest())
        plugin_files = [e for e in manifest if e.endswith(".py")]
        self.assertTrue(plugin_files, "MANIFEST lists no Python files")
        missing = {}
        for rel in plugin_files:
            gone = sorted(in_repo_imports(rel) - manifest)
            if gone:
                missing[rel] = gone
        self.assertEqual(
            missing, {}, "files imported by plugin code but absent from MANIFEST"
        )

    def test_entry_points_covered(self):
        manifest = set(read_manifest())
        for required in ("__init__.py", "source.py", "config.py", "utils.py"):
            self.assertIn(required, manifest)

    def test_import_resolver_finds_known_imports(self):
        # Guards against the coverage test passing vacuously.
        self.assertIn("pycomicvine/error.py", in_repo_imports("utils.py"))
        self.assertIn("utils.py", in_repo_imports("source.py"))
        self.assertIn("config.py", in_repo_imports("source.py"))


if __name__ == "__main__":
    unittest.main()
