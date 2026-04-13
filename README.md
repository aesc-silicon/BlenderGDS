<!--
SPDX-FileCopyrightText: 2025 aesc-silicon

SPDX-License-Identifier: GPL-3.0-or-later
-->

# BlenderGDS

A Blender add-on for importing GDSII layout files with full 3D layer stack visualization and PDK support.

## Overview

BlenderGDS enables semiconductor layout visualization by importing GDSII files into Blender with accurate 3D representation of the layer stack. The add-on supports multiple Process Design Kits (PDKs) and provides comprehensive control over the import process, making it ideal for chip design visualization, documentation, and presentations.

## Features

* **Layer Stack Visualization**: Accurate 3D extrusion of all layers based on PDK specifications
* **Selective Import**: Crop specific chip regions by defining X, Y, width, and height coordinates
* **Automatic Scene Setup**: Optional initialization of camera, lighting, and chip base plane
* **Material System**: Realistic materials with proper colors and metallic properties for each layer type
* **Collection Organization**: Automatic grouping of imported layers into named collections
* **Custom Configurations**: Support for custom YAML layer stack configurations
* **Flexible Scaling**: Adjustable unit and Z-axis scaling for different visualization needs
* **Merge Layers**: Union overlapping shapes on each layer before building the mesh (enabled by default, eliminates black rendering artifacts in Cycles)

## Supported PDKs

* IHP Open PDK (SG13G2 & CMOS5L)
* SkyWater SKY130 PDK
* GlobalFoundries GF180MCU PDK

## Installation

BlenderGDS requires **Blender 4.2 or later**. All Python dependencies (`gdstk`, `klayout`, `numpy`, `PyYAML`) are bundled inside the extension and installed automatically — no pip or terminal required.

### Installing from Blender Extensions

1. In Blender, open **Edit → Preferences → Get Extensions**
2. Search for **BlenderGDS**
3. Click **Install**

The extension is now active. No restart needed.

### Installing from a release

1. Download the latest `import_gdsii-*.zip` from the [GitHub releases page](https://github.com/aesc-silicon/BlenderGDS/releases)
2. In Blender, open **Edit → Preferences → Get Extensions**
3. Click the dropdown in the top-right corner and choose **Install from Disk...**
4. Select the downloaded `.zip` file

The extension is now active. No restart needed.

### Building from source

1. Clone the repository and build the extension zip:

   ```bash
   git clone https://github.com/aesc-silicon/BlenderGDS
   cd BlenderGDS
   python scripts/build_extension.py
   ```

   This downloads wheels for all supported platforms (Linux, Windows, macOS) and produces `import_gdsii-*.zip` in the repo root.

   If `blender` is not on your `PATH`, pass it explicitly:

   ```bash
   python scripts/build_extension.py --blender /path/to/blender
   ```

2. Install the resulting `.zip` as described above.

### Updating the extension

To update to a newer version, install the new `.zip` via **Get Extensions → Install from Disk...** — Blender will replace the existing installation automatically.

## Usage

### Basic Import

1. Go to **File → Import → GDSII (.gds)**
2. Select your desired PDK (currently IHP Open PDK SG13G2)
3. Browse and select your GDSII file
4. Configure import options in the sidebar
5. Click **Import GDSII**

### Import Options

**Import Settings**

* **Unit Scale**: GDS database unit scale (default: 1e-6 for micrometers)
* **Z Scale**: Vertical scaling factor for layer heights
* **Create Collection**: Group imported layers in a named collection

**Scene Setup**

* **Setup Scene**: Automatically create camera, lighting, and chip base plane
  * Adds Sun light with soft shadows
  * Positions camera above the chip center
  * Creates a chip base plane with dark material
  * Configures world background

**Crop Region**

* **Crop to Region**: Import only a specific area of the chip
* **X, Y**: Lower-left corner coordinates in chip units
* **Width, Height**: Dimensions of the region to import

### Layer Configuration

Layer stacks are defined in YAML format:

```yaml
Metal1:
  index: 8
  type: 0
  z: 0.350
  height: 0.300
  color: [0.45, 0.45, 0.50, 1.0]

Via1:
  index: 19
  type: 0
  z: 0.650
  height: 0.350
  color: [0.90, 0.70, 0.20, 1.0]
```

Each layer requires:

* `index`: GDS layer number
* `type`: GDS datatype
* `z`: Z-position in micrometers
* `height`: Layer thickness in micrometers
* `color`: Layer RGBA values

#### Parameters

- `pdk` - Process Design Kit specification (e.g., `ihp-sg13g2`)
- `output_file` - Path for the merged output GDS file
- `input.gds` - Input GDS file to process

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues on the [GitHub repository](https://github.com/aesc-silicon/BlenderGDS).

## License

This project is licensed under the GNU General Public License v3.0 only. See the LICENSE file for details.

## Support

For issues, questions, or suggestions, please open an issue on the [GitHub repository](https://github.com/aesc-silicon/BlenderGDS).
