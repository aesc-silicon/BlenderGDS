<!--
SPDX-FileCopyrightText: 2025 aesc-silicon

SPDX-License-Identifier: Apache-2.0
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

## Supported PDKs

* IHP Open PDK (SG13G2)
* SkyWater SKY130 PDK
* GlobalFoundries GF180MCU PDK

## Installation

### Prerequisites

BlenderGDS requires the following Python packages:

* `gdstk` - GDSII file handling
* `numpy` - Numerical operations
* `PyYAML` - Configuration file parsing

Check your installed Blender versions. If this directory doesn't exist, make sure you have started Blender at least once.

```bash
ls ~/.config/blender/
```

> [!Note]
> This guide is for Blender 5.0. If you're using a different version, adjust the path accordingly.

Install these packages into Blender's module directory using pip:

```bash
pip install --target=$HOME/.config/blender/5.0/scripts/addons/modules/ gdstk numpy pyyaml
```

### Installing the Add-on

1. Download the latest release from the [GitHub repository](https://github.com/aesc-silicon/BlenderGDS)

   ```bash
   git clone https://github.com/aesc-silicon/BlenderGDS
   ```

2. Copy all files from `import_gdsii/` to `$HOME/.config/blender/5.0/scripts/addons/`

   ```bash
   cp -r BlenderGDS/import_gdsii/ $HOME/.config/blender/5.0/scripts/addons/
   ```

3. Start Blender
4. In Blender, go to **Edit → Preferences → Add-ons**
5. Enable the add-on by checking the box next to "Import-Export: GDSII Importer with PDK Support"

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

## Scripts

### merge.py

Merges shapes on relevant BlenderGDS layers to ensure proper rendering with Cycles Render Engine. When using Cycles, overlapping edges and vertices between unmerged shapes can produce black artifacts in the rendered output.

#### Usage
```bash
klayout -zz -r scripts/klayout/merge.py -rd pdk=ihp-sg13g2 -rd output_file=output.gds input.gds
```

#### Parameters

- `pdk` - Process Design Kit specification (e.g., `ihp-sg13g2`)
- `output_file` - Path for the merged output GDS file
- `input.gds` - Input GDS file to process

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues on the [GitHub repository](https://github.com/aesc-silicon/BlenderGDS).

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Support

For issues, questions, or suggestions, please open an issue on the [GitHub repository](https://github.com/aesc-silicon/BlenderGDS).
