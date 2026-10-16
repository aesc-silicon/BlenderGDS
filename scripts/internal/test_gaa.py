# SPDX-FileCopyrightText: 2026 BlenderGDS contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""GAA geometry/import regressions; run inside Blender with the add-on dependencies.

blender --background --factory-startup -noaudio --python-exit-code 1 \
    --python scripts/internal/test_gaa.py
"""

from pathlib import Path
import sys
import tempfile
import unittest

import bmesh
import bpy
from klayout import db
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import import_gdsii as addon  # noqa: E402  pylint: disable=wrong-import-position


def volume(obj):
    """Signed mesh volume catches missing caps and overlapping channel solids."""
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    result = mesh.calc_volume(signed=True)
    mesh.free()
    return result


class GAAImportTests(unittest.TestCase):
    """Exercise actual KLayout booleans, Blender meshes and the import operator."""

    @classmethod
    def setUpClass(cls):
        addon.register()

    @classmethod
    def tearDownClass(cls):
        addon.unregister()

    def setUp(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    def make_layout(self, config):
        """Nested cell with all drawing layers, including GT2N backside wiring."""
        layout = db.Layout()
        layout.dbu = 0.001
        leaf = layout.create_cell('device')
        for data in config.values():
            index = layout.layer(data['index'], data['type'])
            if leaf.shapes(index).is_empty():
                leaf.shapes(index).insert(db.Box(0, 0, 100, 20))
        gate = layout.layer(3, 0)
        leaf.shapes(gate).clear()
        leaf.shapes(gate).insert(db.Box(40, -10, 60, 30))
        cut = layout.layer(5, 0)
        leaf.shapes(cut).clear()
        leaf.shapes(cut).insert(db.Box(40, 25, 60, 30))
        top = layout.create_cell('top')
        top.insert(db.CellInstArray(leaf.cell_index(), db.Trans()))
        return layout

    def import_fixture(self, pdk, **options):
        config = yaml.safe_load((addon.CONFIGS_DIR / f'{pdk}.yaml').read_text())
        config.pop('pdk_config')
        layout = self.make_layout(config)
        bpy.context.scene.gdsii_pdk_selection = pdk.upper()
        bpy.context.scene.gdsii_use_custom_config = False
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / 'fixture.gds')
            layout.write(path)
            result = bpy.ops.import_scene.gdsii(
                filepath=path, color_scheme='realistic', setup_scene=False, **options)
        self.assertEqual(result, {'FINISHED'})
        return config

    def test_presets_and_gate_volume(self):
        for pdk in ('gt3', 'gt2n'):
            with self.subTest(pdk=pdk):
                self.setUp()
                config = self.import_fixture(pdk)
                expected = {'L' + name for name, data in config.items()
                            if data.get('purpose') != 'mask'}
                self.assertEqual(set(bpy.data.objects.keys()), expected)
                # 20*35*65 gate minus three 20*20*5 sheet intersections, in nm³.
                self.assertAlmostEqual(volume(bpy.data.objects['LGATE']), 39500e-9, places=10)
                for name, data in config.items():
                    if data.get('purpose') == 'mask':
                        continue
                    obj = bpy.data.objects['L' + name]
                    self.assertAlmostEqual(min(v.co.z for v in obj.data.vertices),
                                           data['z'], places=6)
                    self.assertAlmostEqual(max(v.co.z for v in obj.data.vertices),
                                           data['z'] + data['height'], places=6)
                    self.assertGreater(volume(obj), 0)

    def test_crop_scale_and_unmerged_import(self):
        self.import_fixture('gt2n', use_crop=True, crop_x=.05, crop_y=0,
                            crop_width=.1, crop_height=.1, z_scale=2,
                            merge_layers=False)
        gate = bpy.data.objects['LGATE']
        # Crop leaves 10*25 nm gate and 10*20 nm channel intersections.
        self.assertAlmostEqual(volume(gate), (10*25*65 - 3*10*20*5)*2e-9, places=10)
        self.assertAlmostEqual(min(v.co.x for v in gate.data.vertices), 0, places=6)
        self.assertAlmostEqual(max(v.co.z for v in gate.data.vertices), .15, places=6)
        self.assertAlmostEqual(min(v.co.z for v in bpy.data.objects['LBRDL'].data.vertices),
                               -3.618, places=6)

    def test_gate_without_active_geometry(self):
        region = db.Region(db.Box(0, 0, 10, 10))
        slabs = addon._gaa_slabs(region, 0, 10, [(db.Region(), 2, 3)])
        self.assertEqual(len(slabs), 1)
        self.assertEqual(slabs[0][0].area(), 100)
        self.assertEqual(slabs[0][1:], (0, 10))

    def test_overlapping_and_clipped_references(self):
        region = db.Region(db.Box(0, 0, 10, 10))
        reference = db.Region(db.Box(0, 0, 5, 10))
        slabs = addon._gaa_slabs(
            region, 0, 10, [(reference, -2, 4), (reference, 2, 6), (reference, 20, 21)])
        self.assertEqual(sum(shape.area() * height for shape, _, height in slabs), 700)
        self.assertEqual(region.area(), 100)  # Cached inputs must remain intact.
        self.assertEqual(reference.area(), 50)

    def test_legacy_fin_wrap(self):
        layout = db.Layout()
        layout.dbu = .001
        top = layout.create_cell('fin')
        top.shapes(layout.layer(3, 0)).insert(db.Box(0, 0, 100, 100))
        reference = db.Region(db.Box(40, 0, 60, 100))
        obj = addon.create_extruded_layer(
            lambda *_: None, layout, [top], .03, .02, (3, 0), 'legacy', {},
            wrap_region=reference, wrap_z_bottom=0)
        self.assertAlmostEqual(volume(obj), .01*.02 + .008*.03, places=10)

    def test_scene_base_below_backside(self):
        addon.setup_chip_scene(0, 0, .1, .1, base_z=-2.809)
        self.assertTrue(all(v.co.z < -1.809
                            for v in bpy.data.objects['ChipBase'].data.vertices))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GAAImportTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise RuntimeError('GAA regression tests failed')
