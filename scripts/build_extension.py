#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 aesc silicon
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Build the BlenderGDS extension (.zip) for Blender 4.2+.

Downloads wheels for all supported platforms, writes blender_manifest.toml,
and packages the extension using `blender --command extension build`.

Usage:
    python build_extension.py [--blender /path/to/blender] [--skip-download]

The resulting .zip can be installed in Blender via:
    Preferences > Get Extensions > Install from Disk
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
ADDON_DIR = REPO_DIR / "import_gdsii"
WHEELS_DIR = ADDON_DIR / "wheels"
MANIFEST_PATH = ADDON_DIR / "blender_manifest.toml"

PACKAGES = ["gdstk", "klayout", "PyYAML"]

# Blender 4.2/4.3 uses Python 3.11, Blender 4.4+ uses Python 3.13.
# Downloading wheels for both ensures compatibility across all supported versions.
PYTHON_VERSIONS = ["3.11", "3.13"]

# Packages already bundled with Blender — exclude from the extension wheels.
BLENDER_PROVIDED = ["numpy"]

# One entry per (OS, architecture) combination that Blender supports.
PLATFORMS = [
    "manylinux_2_28_x86_64",   # Linux x86-64
    "win_amd64",                # Windows x86-64
    "macosx_11_0_arm64",        # macOS Apple Silicon
]

def get_version() -> tuple[str, bool]:
    """Return (version, is_dirty) derived from the latest git tag.

    Uses ``git describe --tags --long --match 'v*'`` which produces output like
    ``v1.0.2-3-gabcdef``.  If the commit distance is non-zero the build is
    considered dirty: the patch component is bumped by one and the caller
    should mark the artefacts accordingly.
    """
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--long", "--match", "v*"],
            cwd=REPO_DIR, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        print("Warning: no git tag found — falling back to version 0.0.0")
        return "0.0.0", True

    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)-(\d+)-g[0-9a-f]+", out)
    if not m:
        print(f"Warning: unexpected git describe output {out!r} — falling back to 0.0.0")
        return "0.0.0", True

    major, minor, patch, distance = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    dirty = distance > 0
    if dirty:
        patch += 1
    return f"{major}.{minor}.{patch}", dirty


MANIFEST_TEMPLATE = """\
# SPDX-FileCopyrightText: 2026 aesc silicon
#
# SPDX-License-Identifier: GPL-3.0-or-later

schema_version = "1.0.0"

id = "import_gdsii"
version = "{version}"
name = "GDSII Importer"
tagline = "GDSII importer with PDK layer stack support"
maintainer = "aesc silicon"
type = "add-on"

blender_version_min = "4.2.0"

license = ['SPDX:GPL-3.0-or-later']

platforms = ["linux-x64", "windows-x64", "macos-arm64"]

tags = ["Import-Export"]

wheels = [
{wheel_entries}
]
"""



def download_wheels() -> None:
    if WHEELS_DIR.exists():
        shutil.rmtree(WHEELS_DIR)
    WHEELS_DIR.mkdir()

    for python_version in PYTHON_VERSIONS:
        for platform in PLATFORMS:
            print(f"\nDownloading wheels for {platform} (Python {python_version})...")
            try:
                subprocess.run(
                    [
                        sys.executable, "-m", "pip", "download",
                        "--python-version", python_version,
                        "--only-binary=:all:",
                        "--platform", platform,
                        "--dest", str(WHEELS_DIR),
                        *PACKAGES,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError:
                print(f"  Warning: some packages could not be downloaded for {platform} (Python {python_version})")

    # Remove wheels for packages already provided by Blender.
    for pkg in BLENDER_PROVIDED:
        for whl in WHEELS_DIR.glob(f"{pkg}-*.whl"):
            whl.unlink()
            print(f"  Removed bundled-by-Blender wheel: {whl.name}")


def write_manifest(version: str) -> None:
    wheels = sorted(WHEELS_DIR.glob("*.whl"))
    if not wheels:
        sys.exit("No wheels found in import_gdsii/wheels/ — run without --skip-download first.")

    entries = "\n".join(f'  "./wheels/{w.name}",' for w in wheels)
    MANIFEST_PATH.write_text(
        MANIFEST_TEMPLATE.format(version=version, wheel_entries=entries),
        encoding="utf-8",
    )
    print(f"\nManifest written — version {version}, {len(wheels)} wheel(s).")


def build(blender_exe: str, version: str, dirty: bool) -> None:
    print(f"\nBuilding extension with: {blender_exe}")
    subprocess.run(
        [
            blender_exe, "--command", "extension", "build",
            "--source-dir", str(ADDON_DIR),
            "--output-dir", str(REPO_DIR),
            "--split-platforms",
        ],
        check=True,
    )

    if dirty:
        # Rename artefacts to make non-release builds clearly identifiable.
        # e.g. import_gdsii-1.0.3-linux-x64.zip → import_gdsii-1.0.3-dirty-linux-x64.zip
        for zip_path in REPO_DIR.glob(f"import_gdsii-{version}-*.zip"):
            stem = zip_path.stem                        # import_gdsii-1.0.3-linux-x64
            suffix = zip_path.suffix                    # .zip
            # Insert -dirty before the platform suffix (last dash-separated token)
            parts = stem.rsplit("-", 1)                 # ['import_gdsii-1.0.3', 'linux-x64']
            new_name = f"{parts[0]}-dirty-{parts[1]}{suffix}"
            zip_path.rename(zip_path.parent / new_name)
            print(f"  Renamed → {new_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--blender",
        default=shutil.which("blender") or "blender",
        help="Path to Blender executable (default: blender from PATH)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading wheels (reuse existing import_gdsii/wheels/ directory)",
    )
    args = parser.parse_args()

    version, dirty = get_version()
    if dirty:
        print(f"Warning: dirty build — patch bumped to {version}, output zips will be marked -dirty")
    else:
        print(f"Building release {version}")

    if not args.skip_download:
        download_wheels()
    write_manifest(version)
    build(args.blender, version, dirty)
    if WHEELS_DIR.exists():
        shutil.rmtree(WHEELS_DIR)
    MANIFEST_PATH.write_text(
        MANIFEST_TEMPLATE.format(version=version, wheel_entries="  # Populated by build_extension.py — do not edit by hand."),
        encoding="utf-8",
    )
    print("\nDone. Install the .zip via Blender > Preferences > Get Extensions > Install from Disk.")


if __name__ == "__main__":
    main()
