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
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
ADDON_DIR = REPO_DIR / "import_gdsii"
WHEELS_DIR = ADDON_DIR / "wheels"
MANIFEST_PATH = ADDON_DIR / "blender_manifest.toml"

PACKAGES = ["gdstk", "numpy", "klayout", "PyYAML"]
PYTHON_VERSION = "3.11"

# One entry per (OS, architecture) combination that Blender supports.
PLATFORMS = [
    "manylinux_2_28_x86_64",   # Linux x86-64
    "win_amd64",                # Windows x86-64
    "macosx_11_0_arm64",        # macOS Apple Silicon
    "macosx_10_9_x86_64",       # macOS Intel
]

MANIFEST_TEMPLATE = """\
# SPDX-FileCopyrightText: 2026 aesc silicon
#
# SPDX-License-Identifier: GPL-3.0-or-later

schema_version = "1.0.0"

id = "import_gdsii"
version = "1.0.0"
name = "BlenderGDS"
tagline = "GDSII importer with PDK layer stack support"
maintainer = "aesc silicon"
type = "add-on"

blender_version_min = "4.2.0"

license = ['SPDX:GPL-3.0-or-later']

tags = ["Import-Export"]

wheels = [
{wheel_entries}
]
"""



def download_wheels() -> None:
    if WHEELS_DIR.exists():
        shutil.rmtree(WHEELS_DIR)
    WHEELS_DIR.mkdir()

    for platform in PLATFORMS:
        print(f"\nDownloading wheels for {platform}...")
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "download",
                    "--python-version", PYTHON_VERSION,
                    "--only-binary=:all:",
                    "--platform", platform,
                    "--dest", str(WHEELS_DIR),
                    *PACKAGES,
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            print(f"  Warning: some packages could not be downloaded for {platform}")


def write_manifest() -> None:
    wheels = sorted(WHEELS_DIR.glob("*.whl"))
    if not wheels:
        sys.exit("No wheels found in import_gdsii/wheels/ — run without --skip-download first.")

    entries = "\n".join(f'  "./wheels/{w.name}",' for w in wheels)
    MANIFEST_PATH.write_text(MANIFEST_TEMPLATE.format(wheel_entries=entries), encoding="utf-8")
    print(f"\nManifest written with {len(wheels)} wheel(s).")


def build(blender_exe: str) -> None:
    print(f"\nBuilding extension with: {blender_exe}")
    subprocess.run(
        [
            blender_exe, "--command", "extension", "build",
            "--source-dir", str(ADDON_DIR),
            "--output-dir", str(REPO_DIR),
        ],
        check=True,
    )


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

    if not args.skip_download:
        download_wheels()
    write_manifest()
    build(args.blender)
    MANIFEST_PATH.write_text(MANIFEST_TEMPLATE.format(wheel_entries="  # Populated by build_extension.py — do not edit by hand."), encoding="utf-8")
    print("\nDone. Install the .zip via Blender > Preferences > Get Extensions > Install from Disk.")


if __name__ == "__main__":
    main()
