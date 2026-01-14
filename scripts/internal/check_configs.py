"""Script to validate YAML files in this project."""
from pathlib import Path
import json
import yaml
from jsonschema import validate

script_dir = Path(__file__).resolve().parent
with open(script_dir / 'layer-config.schema.json', encoding='utf-8') as f:
    pdk_schema = json.load(f)

with open(script_dir / 'color-schema.schema.json', encoding='utf-8') as f:
    color_schema = json.load(f)


project_dir = script_dir.parent.parent
pdks = project_dir / "import_gdsii/configs"
for process in pdks.glob('*yaml'):
    print(f"Found process: {process.stem}")

    pdk_file = yaml.safe_load(process.read_text(encoding='utf-8'))
    validate(pdk_file, pdk_schema)
    pdk_layers = set(pdk_file.keys())

    for color in (pdks / f"colors/{process.stem}").glob('*yaml'):
        print(f"  Found color schema: {color.stem}")

        color_file = yaml.safe_load(color.read_text(encoding='utf-8'))

        color_layers = set(color_file['layers'].keys())
        assert pdk_layers == color_layers, \
            f"Layer definitions do not match for process \"{process.stem}\" with color " \
            f"schema \"{color.stem}\".\nThe following layer is inconsistent or " \
            f"missing: {', '.join(pdk_layers - color_layers)}."
