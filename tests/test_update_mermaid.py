"""The lockfile walk behind scripts/update_mermaid.py, on a small made-up lockfile. The rest of the
script talks to the network, so it's checked by running it and by the vendored files' tests."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "update_mermaid.py"


def load_script() -> Any:
    spec = importlib.util.spec_from_file_location("update_mermaid", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOCKFILE = """\
lockfileVersion: '9.0'

importers:

  packages/mermaid:
    dependencies:
      a:
        specifier: ^1.0.0
        version: 1.0.0
      '@mermaid-js/parser':
        specifier: workspace:^
        version: link:../parser
      '@types/d3':
        specifier: ^7.4.3
        version: 7.4.3
    optionalDependencies:
      opt:
        specifier: ^1.0.0
        version: 1.0.0
    devDependencies:
      tool:
        specifier: ^1.0.0
        version: 1.0.0

  packages/parser:
    dependencies:
      p:
        specifier: ^1.0.0
        version: 1.0.0
    devDependencies:
      langium:
        specifier: 4.2.1
        version: 4.2.1
      '@microsoft/api-extractor':
        specifier: ^7.0.0
        version: 7.0.0(@types/node@22.0.0)

packages:

  a@1.0.0:
    resolution: {integrity: sha512-A}

  b@2.0.0:
    resolution: {integrity: sha512-B}

  opt@1.0.0:
    resolution: {integrity: sha512-O}

  p@1.0.0:
    resolution: {integrity: sha512-P}

  langium@4.2.1:
    resolution: {integrity: sha512-L}

  vscode-uri@3.1.0:
    resolution: {integrity: sha512-V}

snapshots:

  a@1.0.0:
    dependencies:
      b: 2.0.0(peer@1.0.0)

  b@2.0.0(peer@1.0.0): {}

  opt@1.0.0: {}

  p@1.0.0: {}

  langium@4.2.1:
    dependencies:
      vscode-uri: 3.1.0
    optionalDependencies:
      '@types/node': 22.0.0

  vscode-uri@3.1.0: {}
"""


def test_the_walk_follows_links_optional_and_bundled_dev_dependencies():
    script = load_script()
    closure = script._Lockfile(LOCKFILE).closure("packages/mermaid")
    assert closure == [
        ("a", "1.0.0", "sha512-A"),
        ("b", "2.0.0", "sha512-B"),  # the peer suffix is dropped
        ("langium", "4.2.1", "sha512-L"),  # bundled by the linked parser package
        ("opt", "1.0.0", "sha512-O"),
        ("p", "1.0.0", "sha512-P"),
        ("vscode-uri", "3.1.0", "sha512-V"),
    ]
    # Not there: @types packages, Mermaid's own devDependency, and the parser's build tool.


def test_an_unsorted_dev_dependency_of_a_linked_package_stops_the_update():
    script = load_script()
    lockfile = LOCKFILE.replace("      langium:\n", "      newthing:\n", 1)
    with pytest.raises(
        SystemExit, match="packages/parser has devDependencies that aren't sorted yet: newthing"
    ):
        script._Lockfile(lockfile).closure("packages/mermaid")


def test_a_missing_integrity_hash_stops_the_update():
    script = load_script()
    lockfile = LOCKFILE.replace("    resolution: {integrity: sha512-B}\n", "")
    with pytest.raises(SystemExit, match="no integrity hash for b@2.0.0"):
        script._Lockfile(lockfile).closure("packages/mermaid")


def test_only_a_pnpm_9_lockfile_is_read():
    script = load_script()
    with pytest.raises(SystemExit, match="expected a pnpm lockfile, version 9"):
        script._Lockfile("lockfileVersion: '6.0'\n")
