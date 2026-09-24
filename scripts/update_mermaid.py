"""Vendor a Mermaid release into src/akceo/assets/vendor/mermaid.

    uv run python scripts/update_mermaid.py 12.0.0

Downloads the npm tarball, checks it against npm's published integrity hash, and writes
mermaid.min.js, Mermaid's LICENSE, THIRD_PARTY_NOTICES and manifest.json. The notices come from
Mermaid's production dependency tree, so this step needs npm. Nothing else in akceo does.

The one change made to mermaid.min.js: a raw control character inside a string literal is replaced
with its \\xNN escape, which JavaScript reads the same way but an HTML page can carry safely.
"""

import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REGISTRY = "https://registry.npmjs.org/mermaid"
VENDOR = Path(__file__).parents[1] / "src" / "akceo" / "assets" / "vendor" / "mermaid"
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
    (VENDOR / "THIRD_PARTY_NOTICES").write_text(_notices(version), encoding="utf-8")
    manifest = {
        "version": version,
        "source": meta["dist"]["tarball"],
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


def _notices(version: str) -> str:
    """Every package in Mermaid's production dependency tree, sorted by name, with its license
    text. The tree can hold a package the bundle leaves out, which errs toward too many notices."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text('{"private": true}', encoding="utf-8")
        subprocess.run(
            ["npm", "install", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"]
            + [f"mermaid@{version}"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        packages = sorted(_packages(root / "node_modules"), key=lambda p: (p[0].lower(), p[1]))

    sections = [
        f"Third-party software in mermaid.min.js (Mermaid {version})\n"
        "==========================================================\n\n"
        "mermaid.min.js bundles the packages below. Each is used under the license named with it.\n\n"
        "elkjs (the Eclipse Layout Kernel) is licensed under the Eclipse Public License 2.0. Its source\n"
        "code is available at https://github.com/kieler/elkjs and https://github.com/eclipse/elk.\n\n"
        "DOMPurify is dual licensed under MPL-2.0 or Apache-2.0; it is used here under Apache-2.0.\n"
    ]
    for name, package_version, license_name, text in packages:
        if name == "mermaid":
            continue
        heading = f"{name} {package_version}\nLicense: {license_name}"
        sections.append(f"\n{'-' * 72}\n{heading}\n\n{text.strip()}\n")
    return "".join(sections)


def _packages(node_modules: Path) -> list[tuple[str, str, str, str]]:
    found: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    for manifest in node_modules.rglob("package.json"):
        package = manifest.parent
        scoped = package.parent.name.startswith("@") and package.parent.parent.name == "node_modules"
        if package.parent.name != "node_modules" and not scoped:
            continue  # a package.json inside a package's own folders, not a package root
        data = json.loads(manifest.read_text(encoding="utf-8"))
        name, package_version = data.get("name"), data.get("version")
        if not name or not package_version or name.startswith(SKIP_PREFIXES):
            continue
        text = _license_text(package)
        license_name = data.get("license") or ("see license text" if text else "not stated")
        text = text or "(no license file)"
        found[(name, package_version)] = (name, package_version, str(license_name), text)
    return list(found.values())


def _license_text(package: Path) -> str:
    """The package's license files and any NOTICE file, which Apache-2.0 asks to be passed on."""
    texts = [
        path.read_text(encoding="utf-8", errors="replace").strip()
        for path in sorted(package.iterdir())
        if path.is_file() and path.name.upper().startswith(LICENSE_NAMES)
    ]
    return "\n\n".join(texts)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: update_mermaid.py VERSION")
    main(sys.argv[1])
