"""Vendor a Mermaid release into src/akceo/assets/vendor/mermaid.

    uv run python scripts/update_mermaid.py 12.0.0

Downloads the npm tarball, checks it against npm's published integrity hash, and writes
mermaid.min.js, Mermaid's LICENSE, THIRD_PARTY_NOTICES and manifest.json.

The notices come from the pnpm-lock.yaml in Mermaid's repository at the release tag: the lockfile
the bundle was built from. Resolving Mermaid's dependency ranges today would pick newer versions
than the ones in the bundle. Each locked package is downloaded from the npm registry, checked
against the lockfile's integrity hash, and its license files are read from the tarball.

The one change made to mermaid.min.js: a raw control character inside a string literal is replaced
with its \\xNN escape, which JavaScript reads the same way but an HTML page can carry safely.
"""

import base64
import hashlib
import io
import json
import posixpath
import re
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

NPM = "https://registry.npmjs.org"
REGISTRY = f"{NPM}/mermaid"
LOCKFILE = "https://raw.githubusercontent.com/mermaid-js/mermaid/{tag}/pnpm-lock.yaml"
IMPORTER = "packages/mermaid"
# A workspace package that Mermaid links to, such as @mermaid-js/parser, is built into its own
# output first, so some of its devDependencies end up in the bundle. Each one has to be sorted
# into one of these; an update that finds a new one stops until a person decides which it is.
BUNDLED_DEV_DEPENDENCIES = {"packages/parser": {"langium", "chevrotain"}}
BUILD_ONLY_DEV_DEPENDENCIES = {"packages/parser": {"@microsoft/api-extractor"}}
VENDOR = Path(__file__).parents[1] / "src" / "akceo" / "assets" / "vendor" / "mermaid"
# NOTICE files too: Apache-2.0 asks for them to be passed on.
LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE")
QUOTES = "\"'"
# Type definitions are never bundled into the JavaScript, so they need no notice.
SKIP_PREFIXES = ("@types/",)


def main(version: str) -> None:
    meta = json.loads(_fetch(f"{REGISTRY}/{version}"))
    tarball = _fetch(meta["dist"]["tarball"])
    algorithm, expected = meta["dist"]["integrity"].split("-", 1)
    if base64.b64encode(hashlib.new(algorithm, tarball).digest()).decode() != expected:
        sys.exit(f"the downloaded tarball doesn't match npm's {algorithm} integrity hash")

    with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
        script = _member(tar, "package/dist/mermaid.min.js").decode("utf-8")
        license_text = _member(tar, "package/LICENSE").decode("utf-8")

    script, escaped = _escape_control_characters(script)
    VENDOR.mkdir(parents=True, exist_ok=True)
    (VENDOR / "mermaid.min.js").write_text(script, encoding="utf-8", newline="")
    (VENDOR / "LICENSE").write_text(license_text, encoding="utf-8")
    lockfile = LOCKFILE.format(tag=urllib.parse.quote(f"mermaid@{version}"))
    (VENDOR / "THIRD_PARTY_NOTICES").write_text(_notices(version, lockfile), encoding="utf-8")
    manifest = {
        "version": version,
        "source": meta["dist"]["tarball"],
        "lockfile": lockfile,
        "integrity": meta["dist"]["integrity"],
        "sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "escaped_control_characters": escaped,
    }
    (VENDOR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"vendored mermaid {version}: {len(script) / 1e6:.1f} MB, {escaped} control characters escaped")
    print("now run: uv run pytest tests/test_mermaid.py")


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def _member(tar: tarfile.TarFile, name: str) -> bytes:
    member = tar.extractfile(name)
    if member is None:
        sys.exit(f"{name} is missing from the tarball")
    return member.read()


def _escape_control_characters(script: str) -> tuple[str, int]:
    """Replace each raw control character with its \\xNN escape. That is only the same program when
    the character sits inside a string literal, so stop on any other kind for a human to look at."""
    out: list[str] = []
    count = 0
    for i, c in enumerate(script):
        if ord(c) < 32 and c not in "\n\r\t":
            before, after = script[i - 1 : i], script[i + 1 : i + 2]
            if not (before in QUOTES and before == after):
                sys.exit(f"raw control character {hex(ord(c))} at offset {i} is not alone in a string")
            out.append(f"\\x{ord(c):02x}")
            count += 1
        else:
            out.append(c)
    return "".join(out), count


def _notices(version: str, lockfile_url: str) -> str:
    """Every package the release's lockfile resolves for Mermaid's production dependencies and the
    devDependencies its workspace packages bundle, sorted by name, with its license text. The set can
    hold a package the bundle leaves out, which errs toward too many notices, but every version is
    the one the bundle was built with."""
    lock = _Lockfile(_fetch(lockfile_url).decode("utf-8"))
    packages = sorted(map(_package_notice, lock.closure(IMPORTER)), key=lambda p: (p[0].lower(), p[1]))
    sections = [
        f"Third-party software in mermaid.min.js (Mermaid {version})\n"
        "==========================================================\n\n"
        "mermaid.min.js bundles the packages below. Each is used under the license named with it.\n"
        f"The versions are the ones pinned by the lockfile the release was built from:\n{lockfile_url}\n\n"
        "elkjs (the Eclipse Layout Kernel) is licensed under the Eclipse Public License 2.0. Its source\n"
        "code is available at https://github.com/kieler/elkjs and https://github.com/eclipse/elk.\n\n"
        "DOMPurify is dual licensed under MPL-2.0 or Apache-2.0; it is used here under Apache-2.0.\n"
    ]
    for name, package_version, license_name, text in packages:
        heading = f"{name} {package_version}\nLicense: {license_name}"
        sections.append(f"\n{'-' * 72}\n{heading}\n\n{text.strip()}\n")
    return "".join(sections)


class _Lockfile:
    """The parts of a pnpm v9 lockfile needed to list a workspace package's dependencies. The Python
    standard library has no YAML parser, and these sections only need their indentation read."""

    def __init__(self, text: str) -> None:
        if not text.startswith("lockfileVersion: '9."):
            sys.exit("expected a pnpm lockfile, version 9")
        # importer -> group -> {name: version}, "name@version" -> {name: version},
        # "name@version" -> integrity
        self.importers: dict[str, dict[str, dict[str, str]]] = {}
        self.snapshots: dict[str, dict[str, str]] = {}
        self.integrity: dict[str, str] = {}
        section = entry = group = ""
        dependency = ""
        for line in text.splitlines():
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            key, _, value = line.strip().partition(":")
            key, value = key.strip("'"), value.strip()
            if indent == 0:
                section = key
            elif indent == 2:
                entry, group = key, ""
            elif indent == 4:
                group = key
                if section == "packages" and key == "resolution":
                    found = re.search(r"integrity: ([^,}]+)", value)
                    if found:
                        self.integrity[entry] = found.group(1).strip()
            elif section == "importers" and group in ("dependencies", "devDependencies"):
                if indent == 6:
                    dependency = key
                elif indent == 8 and key == "version":
                    self.importers.setdefault(entry, {}).setdefault(group, {})[dependency] = value
            elif section == "snapshots" and group == "dependencies" and indent == 6:
                self.snapshots.setdefault(entry, {})[key] = value.strip("'")

    def closure(self, importer: str) -> list[tuple[str, str, str]]:
        """(name, version, integrity) for every package the importer depends on, directly or not.
        A workspace link (link:../parser) is part of Mermaid itself, so follow its dependencies and
        the devDependencies it bundles."""
        found: dict[str, tuple[str, str, str]] = {}
        pending = [(importer, n, v) for n, v in self._group(importer, "dependencies").items()]
        while pending:
            owner, name, version = pending.pop()
            if version.startswith("link:"):
                linked = posixpath.normpath(posixpath.join(owner, version.removeprefix("link:")))
                pending += [(linked, n, v) for n, v in self._linked(linked).items()]
                continue
            snapshot = f"{name}@{version}"
            exact = version.split("(")[0]  # drop the peer suffix, as in 2.2.0(cytoscape@3.34.0)
            if snapshot in found or name.startswith(SKIP_PREFIXES):
                continue
            integrity = self.integrity.get(f"{name}@{exact}")
            if integrity is None:
                sys.exit(f"the lockfile has no integrity hash for {name}@{exact}")
            found[snapshot] = (name, exact, integrity)
            pending += [(owner, n, v) for n, v in self.snapshots.get(snapshot, {}).items()]
        return sorted(set(found.values()))

    def _group(self, importer: str, group: str) -> dict[str, str]:
        return self.importers.get(importer, {}).get(group, {})

    def _linked(self, importer: str) -> dict[str, str]:
        """A linked workspace package's dependencies plus the devDependencies it bundles."""
        bundled = BUNDLED_DEV_DEPENDENCIES.get(importer, set())
        build_only = BUILD_ONLY_DEV_DEPENDENCIES.get(importer, set())
        dev = self._group(importer, "devDependencies")
        unsorted = sorted(set(dev) - bundled - build_only)
        if unsorted:
            sys.exit(
                f"{importer} has devDependencies that aren't sorted yet: {', '.join(unsorted)}. Check "
                "whether each ends up in mermaid.min.js, then add it to BUNDLED_DEV_DEPENDENCIES or "
                "BUILD_ONLY_DEV_DEPENDENCIES."
            )
        return {**self._group(importer, "dependencies"), **{n: v for n, v in dev.items() if n in bundled}}


def _package_notice(package: tuple[str, str, str]) -> tuple[str, str, str, str]:
    """Download one locked package, check it, and read its license from the tarball."""
    name, version, integrity = package
    tarball = _fetch(f"{NPM}/{name}/-/{name.split('/')[-1]}-{version}.tgz")
    algorithm, expected = integrity.split("-", 1)
    if base64.b64encode(hashlib.new(algorithm, tarball).digest()).decode() != expected:
        sys.exit(f"{name}@{version} doesn't match the lockfile's {algorithm} integrity hash")
    with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
        # Files at the top of the package; npm tarballs usually, but not always, use package/.
        top = [m for m in tar.getmembers() if m.isfile() and m.name.count("/") == 1]
        manifest = next((m for m in top if m.name.endswith("/package.json")), None)
        data = json.loads(_read(tar, manifest)) if manifest else {}
        texts = [
            _read(tar, m).strip()
            for m in sorted(top, key=lambda m: m.name)
            if m.name.split("/")[1].upper().startswith(LICENSE_NAMES)
        ]
    text = "\n\n".join(texts)
    license_name = data.get("license") or ("see license text" if text else "not stated")
    return name, version, str(license_name), text or "(no license file)"


def _read(tar: tarfile.TarFile, member: tarfile.TarInfo) -> str:
    """A file from a tarball, as text with \n line endings: the notices are embedded in pages,
    where a raw \r is unwanted."""
    handle = tar.extractfile(member)
    text = handle.read().decode("utf-8", errors="replace") if handle else ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: update_mermaid.py VERSION")
    main(sys.argv[1])
