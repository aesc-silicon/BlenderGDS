"""
Merge overlapping shapes on BlenderGDS layers for proper Cycles rendering.

Overlapping edges and vertices between separate mesh objects can cause
black artifacts when rendering with Cycles. This function merges shapes
on the relevant layers to eliminate these rendering issues.
"""
import sys
from pathlib import Path
import pya
import yaml

try:
    output_file
except NameError:
    print("Missing output_path argument. Please define '-rd output_file=<file-to-export>'")
    sys.exit(1)

configs = Path(__file__).resolve().parent.parent.parent / "import_gdsii/configs"
pdks = [item.stem for item in configs.iterdir()]

try:
    pdk  # pylint: disable=used-before-assignment
except NameError:
    print("Missing PDK argument. Please define '-rd pdk=<pdk_name>'")
    print(f"Available options: {', '.join(pdks)}")
    sys.exit(1)

if pdk not in pdks:
    print("Unknown PDK passed!")
    print(f"Available options: {', '.join(pdks)}")
    sys.exit(1)

layout = pya.CellView.active().layout()
top_cell = layout.top_cell()

merged_layout = pya.Layout()
merged_top_cell = merged_layout.create_cell(f"{top_cell.name}_merged")

config = (configs / f"{pdk}.yaml").read_text(encoding="utf-8")
for name, data in yaml.safe_load(config).items():
    layer = (data['index'], data['type'])
    drawing = pya.Region(top_cell.begin_shapes_rec(layout.layer(layer)))
    merged_top_cell.shapes(merged_layout.layer(layer)).insert(drawing.merged())
    print(f"Merged layer {name}")

merged_layout.write(output_file)
