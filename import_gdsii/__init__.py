# SPDX-FileCopyrightText: 2025 aesc silicon
#
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "GDSII Importer",
    "author": "aesc silicon",
    "version": (1, 0, 1),
    "blender": (3, 4, 0),
    "location": "File > Import",
    "description": "Import GDSII files with PDK layer stack support",
    "doc_url": "",
    "category": "Import-Export",
}

import math
import os
from pathlib import Path
import bpy
import bmesh
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper
import numpy as np
import klayout.db as db
import yaml


# ============================================================================
# PDK DEFINITIONS
# ============================================================================

# Directory holding the PDK layer stacks and their color schemes
CONFIGS_DIR = Path(__file__).parent / "configs"

# Config file listing the PDKs in the order they appear in the user interface
PDK_ORDER_FILE = "_config_order"

# PDK configs read from CONFIGS_DIR, refreshed whenever the import dialog opens
_pdk_configs = {}


def _pdk_key(file_name):
    """Convert a config file name into the identifier used for its PDK"""
    return file_name.upper().replace('-', '_')


def _sort_pdk_configs(pdks, order):
    """Sort PDKs as listed in the order file

    Entries are config file names. PDKs missing from the list are appended
    in alphabetical order.
    """
    sorted_pdks = {}
    for entry in order:
        key = _pdk_key(entry)
        if key in pdks:
            sorted_pdks[key] = pdks[key]
    sorted_pdks.update({key: pdks[key] for key in sorted(pdks)
                        if key not in sorted_pdks})

    return sorted_pdks


def load_pdk_configs(configs_dir=CONFIGS_DIR):
    """Read all PDK configs from configs_dir and cache them"""
    global _pdk_configs

    pdks = {}
    order = []
    for config_path in sorted(configs_dir.iterdir()):
        if not config_path.is_file() or config_path.suffix.lower() not in ('.yaml', '.yml'):
            continue

        try:
            config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        except yaml.YAMLError as error:
            print(f"⚠ Ignoring malformed config {config_path.name}: {error}")
            continue

        if config_path.stem == PDK_ORDER_FILE:
            order = config or []
            continue

        if not isinstance(config, dict):
            print(f"⚠ Ignoring config without layers: {config_path.name}")
            continue

        # Optional metadata describing the PDK itself instead of one of its layers
        metadata = config.get('pdk_config') or {}
        key = _pdk_key(config_path.stem)
        pdks[key] = {
            'config_path': config_path,
            'color_path': configs_dir / 'colors' / config_path.stem,
            'name': metadata.get('name', key),
            'description': metadata.get('description', key),
            'def_color': metadata.get('def_color', ''),
        }

    _pdk_configs = _sort_pdk_configs(pdks, order)
    return _pdk_configs


def get_pdk_configs():
    """Return the known PDK configs and read them from disk on first use"""
    if not _pdk_configs:
        load_pdk_configs()
    return _pdk_configs


# ============================================================================
# SCENE SETUP FUNCTIONS
# ============================================================================

def setup_chip_scene(x_min, y_min, x_max, y_max, collection=None):
    """Initialize scene with camera, light, and chip base"""
    # Determine which collection to use
    target_collection = collection if collection is not None else bpy.context.collection

    # --------------------------
    # RENDER ENGINE: CYCLES + GPU
    # --------------------------
    bpy.context.scene.render.engine = 'CYCLES'

    cycles_prefs = bpy.context.preferences.addons['cycles'].preferences
    gpu_activated = False
    for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
        try:
            cycles_prefs.compute_device_type = backend
            cycles_prefs.get_devices()
            devices = [d for d in cycles_prefs.devices if d.type != 'CPU']
            if devices:
                for d in cycles_prefs.devices:
                    d.use = True
                bpy.context.scene.cycles.device = 'GPU'
                gpu_activated = True
                print(f"✓ Cycles GPU: {backend} ({len(devices)} device(s))")
                break
        except Exception:
            continue

    if not gpu_activated:
        bpy.context.scene.cycles.device = 'CPU'
        print("⚠ Cycles GPU: no compatible device found, falling back to CPU")

    # --------------------------
    # SETUP WORLD
    # --------------------------
    world = bpy.data.worlds.new("ChipWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.05, 0.08, 1.0)  # Dark bluish background
    bg.inputs[1].default_value = 1.0

    # --------------------------
    # SETUP LIGHTING
    # --------------------------
    # Add a Sun light
    sun = bpy.data.lights.new(name="Sun", type='SUN')
    sun_obj = bpy.data.objects.new("Sun", sun)
    target_collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (0.8, 0.0, 0.8)  # Slight angle
    sun.energy = 3.0

    # Add soft shadows
    if bpy.app.version < (4, 0, 0):
        # Blender 3.x - use global setting
        bpy.context.scene.eevee.use_soft_shadows = True
    else:
        # Blender 4.0+ - soft shadows are default in EEVEE Next
        # Set shadow properties on the light instead
        sun.use_shadow = True

    # --------------------------
    # SETUP CAMERA
    # --------------------------
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    target_collection.objects.link(cam)
    bpy.context.scene.camera = cam

    # Position camera above the chip center
    cam.location = ((x_min + x_max) / 2, (y_min + y_max) / 2, 200)
    cam.rotation_euler = (0, 0, 0)

    # --------------------------
    # CREATE CHIP BASE
    # --------------------------
    mesh = bpy.data.meshes.new("ChipBaseMesh")
    chip_base = bpy.data.objects.new("ChipBase", mesh)
    target_collection.objects.link(chip_base)

    # Define vertices for a fixed 40x40mm plane centered on the chip for shadow casting
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    extent = 20000  # 20mm in micrometers
    verts = [(cx - extent, cy - extent, -1),
             (cx - extent, cy + extent, -1),
             (cx + extent, cy + extent, -1),
             (cx + extent, cy - extent, -1)]
    faces = [(0, 1, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # Assign material
    mat = bpy.data.materials.new(name="ChipBaseMat")
    if bpy.app.version >= (4, 0, 0):
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (0.05, 0.07, 0.1, 1)
    else:
        mat.diffuse_color = (0.05, 0.07, 0.1, 1)
    chip_base.data.materials.append(mat)

    print("✓ Chip scene setup complete!")

# ============================================================================
# MATERIAL AND MESH CREATION FUNCTIONS
# ============================================================================

def create_material(name, color):
    """Create a material with given color"""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    # Create new material
    mat = bpy.data.materials.new(name=name)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    # Create nodes
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.location = (400.0, 0.0)

    # Set color and properties
    for key,value in color.items():
        # Try using Blender's input names
        if key in node_bsdf.inputs:
            node_bsdf.inputs[key].default_value = value
            if key == "Base Color" and len(value)>3 and not "Alpha" in color:
                # Copy alpha channel of "Base Color" to "Alpha" property if not explicitly set
                node_bsdf.inputs["Alpha"].default_value = value[3]

        elif key == "Specular Type":
            # Handle exceptional property
            try:
                node_bsdf.distribution = value
            except:
                print(f"Unknown Specular Type: {value}")
        elif key == "Subsurface Type":
            # Handle exceptional property
            try:
                node_bsdf.subsurface_method = value
            except:
                print(f"Unknown Subsurface Type: {value}")
        else:
            print(f"Unknown input name: {key}")

    # Link nodes
    mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])

    return mat


# KLayout prints polygons as "(x,y;x,y;...);(x,y;...)"
_POLYGON_CHARS = str.maketrans({'(': None, ')': None, ';': ','})

# Number of vertices above which a single layer slows down Blender noticeably
VERTEX_WARN_LIMIT = 1000000


def _read_coordinates(text):
    """Convert KLayout's polygon string into an array of integer coordinates"""
    return np.fromstring(text.translate(_POLYGON_CHARS), sep=',',
                         dtype=np.int64).reshape(-1, 2)


def _triangles_to_mesh(region):
    """Convert a region of triangles into welded vertices and triangle faces"""
    text = region.to_s(-1)
    if not text:
        return np.empty((0, 2), dtype=np.int64), np.empty((0, 3), dtype=np.int64)

    # Neighbouring triangles share their corners, so the vertices are welded
    coords, inverse = np.unique(_read_coordinates(text), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)

    # A triangle whose corners fall onto the same vertex has no area
    keep = ((faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2])
            & (faces[:, 0] != faces[:, 2]))
    return coords, faces[keep]


def _polygons_to_mesh(region):
    """Convert a region of hole-free polygons into vertices and n-gon faces"""
    text = region.to_s(-1)
    if not text:
        return np.empty((0, 2), dtype=np.int64), []

    coords = _read_coordinates(text)
    faces = []
    start = 0
    for polygon in text.split(');('):
        end = start + polygon.count(';') + 1
        faces.append(list(range(start, end)))
        start = end
    return coords, faces


def create_extruded_layer(report, layout, top_cells, z, height, layer, name, color,
                          mat_name=None, unit=1e-6, crop_box=None, offset=None,
                          merge=True):
    """Create extruded geometry for a specific GDS layer"""
    dbu = layout.dbu * 1e-6 / unit

    # Collect the layer from all top cells, including their sub cells
    region = db.Region()
    layer_index = layout.layer(*layer)
    for cell in top_cells:
        region.insert(cell.begin_shapes_rec(layer_index))

    if crop_box is not None:
        x_min, y_min, x_max, y_max = crop_box
        region &= db.Region(db.Box(
            math.floor(x_min / dbu),
            math.floor(y_min / dbu),
            math.ceil(x_max / dbu),
            math.ceil(y_max / dbu),
        ))

    # Merging avoids overlapping faces, which Cycles renders as artifacts.
    # Without it the polygons have to be taken as they are in the GDS, since
    # KLayout otherwise merges them on the fly for every operation below.
    if merge:
        region.merge()
    else:
        region.merged_semantics = False

    polygon_count = region.count()
    if polygon_count == 0:
        print(f"⚠ Layer {name}: No geometry found")
        return None

    # Blender cannot fill a face with a hole, so KLayout triangulates those
    # polygons. All others are kept as they are and triangulated further down.
    tri_coords, tri_faces = _triangles_to_mesh(region.with_holes(0, True).delaunay())
    poly_coords, poly_faces = _polygons_to_mesh(region.with_holes(0, False))

    coords = np.concatenate((tri_coords, poly_coords))
    if offset is not None:
        coords = coords - np.array([round(offset[0] / dbu), round(offset[1] / dbu)])

    verts = np.empty((len(coords), 3), dtype=np.float64)
    verts[:, :2] = coords * dbu
    verts[:, 2] = z

    faces = tri_faces.tolist()
    faces.extend([index + len(tri_coords) for index in face] for face in poly_faces)

    if len(verts) > VERTEX_WARN_LIMIT:
        report({'WARNING'}, f"{name}: {len(verts)} vertices may slow down Blender")

    # -----------------------------
    # BUILD MESH
    # -----------------------------
    mesh = bpy.data.meshes.new(name=f"M{name}")
    mesh.from_pydata(verts.tolist(), [], faces)
    if mesh.validate(verbose=False):
        print(f"⚠ Layer {name}: Removed invalid geometry")

    obj = bpy.data.objects.new(name=f"L{name}", object_data=mesh)
    bpy.context.collection.objects.link(obj)

    # -----------------------------
    # EXTRUDE
    # -----------------------------
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Blender renders triangles and quads better than large n-gons
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.join_triangles(bm, faces=bm.faces[:],
                             angle_face_threshold=math.pi / 4,
                             angle_shape_threshold=math.pi)

    extruded = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    bmesh.ops.translate(
        bm,
        verts=[v for v in extruded['geom'] if isinstance(v, bmesh.types.BMVert)],
        vec=(0, 0, height),
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # Apply material
    mat = create_material(name if mat_name is None else mat_name, color)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    print(f"✓ {name}: {polygon_count} polygons, {len(verts)} vertices")
    report({'INFO'}, f"✓ {name}: {polygon_count} polygons, {len(verts)} vertices")
    return obj


# ============================================================================
# PRE-IMPORT PDK SELECTION DIALOG
# ============================================================================

def get_pdk_list(self, context):
    """Dynamically generate PDK list based on the available configs"""
    return [(key, pdk['name'], pdk['description'])
            for key, pdk in get_pdk_configs().items()]


def get_color_schemes(self, context):
    """Dynamically generate color scheme list based on selected PDK"""
    pdk_configs = get_pdk_configs()
    pdk = getattr(context.scene, 'gdsii_pdk_selection', next(iter(pdk_configs), ''))
    pdk_info = pdk_configs.get(pdk)
    if pdk_info is None:
        return []

    schemes = []
    for file in sorted(pdk_info['color_path'].glob('*.yaml')):
        color_file = yaml.safe_load(file.read_text(encoding='utf-8'))
        scheme = (file.stem, color_file.get('name', file.stem),
                  color_file.get('description', file.stem))
        # Make sure the PDK's default scheme is the first choice
        if file.stem == pdk_info['def_color']:
            schemes.insert(0, scheme)
        else:
            schemes.append(scheme)
    return schemes


class GDSIIPreImportDialog(bpy.types.Operator):
    """Select PDK before importing GDSII file"""
    bl_idname = "import_scene.gdsii_pdk_dialog"
    bl_label = "Select PDK for GDSII Import"
    bl_options = {'REGISTER'}

    pdk_selection: EnumProperty(
        name="PDK",
        description="Process Design Kit to use for layer stack",
        items=get_pdk_list,
    )

    use_custom_config: BoolProperty(
        name="Use Custom Config",
        description="Use a custom YAML config file instead of built-in PDK",
        default=False,
    )

    custom_config_path: StringProperty(
        name="Config Path",
        description="Path to PDK YAML configuration file",
        default="",
        subtype='FILE_PATH',
    )

    custom_color_path: StringProperty(
        name="Color Schema",
        description="Color schema YAML file to use with the custom layer config",
        default="",
        subtype='FILE_PATH',
    )

    def invoke(self, context, event):
        # Pick up PDKs added since the last import
        load_pdk_configs()
        # Set default config path based on PDK selection
        self.update_config_path()
        return context.window_manager.invoke_props_dialog(self, width=400)

    def update_config_path(self):
        """Update config path based on selected PDK"""
        pdk_info = get_pdk_configs().get(self.pdk_selection)
        if self.use_custom_config or pdk_info is None:
            return

        if pdk_info['config_path'].exists():
            self.custom_config_path = str(pdk_info['config_path'])
        if not pdk_info['def_color']:
            return
        default_color = pdk_info['color_path'] / f"{pdk_info['def_color']}.yaml"
        if default_color.exists():
            self.custom_color_path = str(default_color)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Process Design Kit Selection", icon='PRESET')
        row = box.row()
        row.enabled = not self.use_custom_config
        row.prop(self, "pdk_selection")

        box = layout.box()
        box.label(text="Configuration File", icon='FILE')
        box.prop(self, "use_custom_config")
        if self.use_custom_config:
            row = box.row()
            row.alert = not Path(self.custom_config_path).is_file()
            row.prop(self, "custom_config_path")
            row = box.row()
            row.alert = not Path(self.custom_color_path).is_file()
            row.prop(self, "custom_color_path")
            if not Path(self.custom_config_path).is_file() or not Path(self.custom_color_path).is_file():
                box.label(text="Fix highlighted paths before importing", icon='ERROR')
        else:
            pdk_info = get_pdk_configs().get(self.pdk_selection, {})
            config_path = pdk_info.get('config_path')
            box.label(text=f"Using: {config_path.name if config_path else 'N/A'}", icon='INFO')

    def execute(self, context):
        # Store PDK settings in scene for the importer to use
        context.scene.gdsii_pdk_selection = self.pdk_selection
        context.scene.gdsii_use_custom_config = self.use_custom_config
        context.scene.gdsii_custom_config_path = self.custom_config_path
        context.scene.gdsii_custom_color_path = self.custom_color_path

        # Open the file browser for GDSII import
        bpy.ops.import_scene.gdsii('INVOKE_DEFAULT')
        return {'FINISHED'}


# ============================================================================
# GDSII IMPORTER
# ============================================================================

class ImportGDSII(bpy.types.Operator, ImportHelper):
    """Import GDSII Layout File"""
    bl_idname = "import_scene.gdsii"
    bl_label = "Import GDSII"
    bl_options = {'PRESET', 'UNDO'}

    # File browser filter
    filename_ext = ".gds"
    filter_glob: StringProperty(
        default="*.gds;*.gdsii",
        options={'HIDDEN'},
    )

    # Import options
    unit_scale: FloatProperty(
        name="Unit Scale",
        description="GDS database unit scale (typically 1e-6 for micrometers)",
        default=1e-6,
        min=1e-12,
        max=1.0,
    )

    z_scale: FloatProperty(
        name="Z Scale",
        description="Scale factor for layer heights",
        default=1.0,
        min=0.001,
        max=1000.0,
    )

    create_collection: BoolProperty(
        name="Create Collection",
        description="Import layers into a new collection",
        default=True,
    )

    # Scene setup
    setup_scene: BoolProperty(
        name="Setup Scene",
        description="Initialize scene with camera, light, and chip base",
        default=True,
    )

    # Color schemes
    color_scheme: EnumProperty(
        name="Color Scheme",
        description="Select color scheme for the PDK",
        items=get_color_schemes
    )

    # Crop region options
    use_crop: BoolProperty(
        name="Crop to Region",
        description="Import only a specific region of the chip",
        default=False,
    )

    # Merge overlapping shapes per layer
    merge_layers: BoolProperty(
        name="Merge Layers",
        description="Merge overlapping shapes on each layer to avoid Cycles rendering artifacts",
        default=True,
    )

    # Add metal dummy fill
    add_fill: BoolProperty(
        name="Metal dumm fill",
        description="Include metal dummy fill",
        default=False,
    )

    crop_x: FloatProperty(
        name="X",
        description="X coordinate of crop region (lower-left corner)",
        default=0.0,
    )

    crop_y: FloatProperty(
        name="Y",
        description="Y coordinate of crop region (lower-left corner)",
        default=0.0,
    )

    crop_width: FloatProperty(
        name="Width",
        description="Width of crop region",
        default=1000.0,
        min=0.1,
    )

    crop_height: FloatProperty(
        name="Height",
        description="Height of crop region",
        default=1000.0,
        min=0.1,
    )

    def draw(self, context):
        """Custom layout for the file browser sidebar"""
        layout = self.layout

        box = layout.box()
        box.label(text="Import Settings:", icon='IMPORT')
        box.prop(self, "unit_scale")
        box.prop(self, "z_scale")
        box.prop(self, "create_collection")
        box.prop(self, "merge_layers")

        # Scene setup
        box = layout.box()
        box.label(text="Scene Setup:", icon='SCENE_DATA')
        box.prop(self, "setup_scene")

        # Color scheme (only for built-in PDK configs; custom config selects a file directly)
        use_custom = getattr(context.scene, 'gdsii_use_custom_config', False)
        if not use_custom:
            box = layout.box()
            box.label(text="Color Scheme:", icon='SCENE_DATA')
            box.prop(self, "color_scheme")

        # Add metal dummy fill
        box = layout.box()
        box.label(text="Metal Dummy Fill:", icon='SCENE_DATA')
        box.prop(self, "add_fill")

        # Crop region
        box = layout.box()
        box.label(text="Crop Region:", icon='BORDERMOVE')
        box.prop(self, "use_crop")
        if self.use_crop:
            row = box.row(align=True)
            row.prop(self, "crop_x")
            row.prop(self, "crop_y")
            row = box.row(align=True)
            row.prop(self, "crop_width")
            row.prop(self, "crop_height")

        # Show selected PDK
        box = layout.box()
        box.label(text="Selected PDK:", icon='PRESET')
        if not use_custom:
            pdk_configs = get_pdk_configs()
            pdk = getattr(context.scene, 'gdsii_pdk_selection', next(iter(pdk_configs), ''))
            pdk_name = pdk_configs.get(pdk, {}).get('name', pdk)
        else:
            pdk_name = "Custom"
        box.label(text=pdk_name)

    def execute(self, context):
        return self.import_gdsii(context, self.filepath)

    def import_gdsii(self, context, filepath):
        """Main import function"""
        try:
            # Get PDK settings from scene
            pdk_configs = get_pdk_configs()
            pdk_selection = getattr(context.scene, 'gdsii_pdk_selection',
                                    next(iter(pdk_configs), ''))
            use_custom = getattr(context.scene, 'gdsii_use_custom_config', False)
            custom_config_path = getattr(context.scene, 'gdsii_custom_config_path', '')
            custom_color_path = getattr(context.scene, 'gdsii_custom_color_path', '')

            # Determine config file path
            if use_custom:
                yamlfile = Path(custom_config_path)
            else:
                # Use built-in PDK config
                pdk_info = pdk_configs.get(pdk_selection)
                if pdk_info is None:
                    self.report({'ERROR'}, f"Unknown PDK: {pdk_selection}")
                    return {'CANCELLED'}
                yamlfile = pdk_info['config_path']

            # Load layer stack configuration
            if not yamlfile.is_file():
                self.report({'ERROR'}, f"Layer stack file not found: {yamlfile}")
                return {'CANCELLED'}

            layerstack = yaml.safe_load(yamlfile.read_text(encoding='utf-8'))
            # PDK metadata describes the file itself and is not a layer
            layerstack.pop('pdk_config', None)

            # Read the layout once and extract every layer from it
            gds_layout = db.Layout()
            gds_layout.read(filepath)
            top_cells = gds_layout.top_cells()
            if not top_cells:
                self.report({'ERROR'}, f"No cell found in {Path(filepath).name}")
                return {'CANCELLED'}
            dbu = gds_layout.dbu * 1e-6 / self.unit_scale

            # Setup crop box if enabled
            crop_box = None
            crop_offset = None
            if self.use_crop:
                # Convert to GDS units (typically micrometers)
                crop_box = (
                    self.crop_x,
                    self.crop_y,
                    self.crop_x + self.crop_width,
                    self.crop_y + self.crop_height
                )
                crop_offset = (self.crop_x, self.crop_y)
                # Cropped polygons are shifted so the lower-left sits at the origin.
                bbox_min = (0.0, 0.0)
                bbox_max = (self.crop_width, self.crop_height)
                print(f"Cropping to region: X={self.crop_x}, Y={self.crop_y}, W={self.crop_width}, H={self.crop_height}")
            else:
                # Determine chip dimensions for scene setup
                bbox = db.Box()
                for cell in top_cells:
                    bbox += cell.bbox()
                bbox_min = (bbox.left * dbu, bbox.bottom * dbu)
                bbox_max = (bbox.right * dbu, bbox.top * dbu)

            # Create collection for imported layers
            collection = None
            if self.create_collection:
                col_name = Path(filepath).stem
                collection = bpy.data.collections.new(col_name)
                context.scene.collection.children.link(collection)
                # Make it active
                layer_collection = context.view_layer.layer_collection.children[collection.name]
                context.view_layer.active_layer_collection = layer_collection

            # Setup scene if requested
            if self.setup_scene:
                setup_chip_scene(bbox_min[0], bbox_min[1], bbox_max[0], bbox_max[1], collection)

            if use_custom:
                colorfile = Path(custom_color_path)
            else:
                colorfile = pdk_info['color_path'] / f"{self.color_scheme}.yaml"
            if not colorfile.is_file():
                self.report({'ERROR'}, f"Color schema file not found: {colorfile}")
                return {'CANCELLED'}
            color_file = yaml.safe_load(colorfile.read_text(encoding='utf-8'))

            print(f"Starting GDS import from: {filepath}")
            print(f"Using PDK: {pdk_selection}")
            print(f"Layer stack config: {yamlfile}")

            # Import each layer from the stack
            imported_count = 0
            for layer_name, data in layerstack.items():
                z = data['z'] * self.z_scale
                height = data['height'] * self.z_scale
                layer_index = (data['index'], data['type'])
                if data.get('purpose', 'drawing') == 'filler' and not self.add_fill:
                    continue

                layer_cfg = color_file.get('layers', {}).get(layer_name, {})
                mat_name = None
                if isinstance(layer_cfg, str):
                    mat_name = layer_cfg
                    layer_cfg = color_file.get('materials', {}).get(layer_cfg, {})
                obj = create_extruded_layer(
                    self.report,
                    gds_layout,
                    top_cells,
                    z,
                    height,
                    layer_index,
                    layer_name,
                    layer_cfg,
                    mat_name=mat_name,
                    unit=self.unit_scale,
                    crop_box=crop_box,
                    offset=crop_offset,
                    merge=self.merge_layers,
                )

                if obj is not None:
                    imported_count += 1

            self.report({'INFO'}, f"Imported {imported_count} layers from {Path(filepath).name}")
            print(f"✓ Import complete! {imported_count} layers imported.")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


# ============================================================================
# MENU INTEGRATION
# ============================================================================

def menu_func_import(self, context):
    self.layout.operator(GDSIIPreImportDialog.bl_idname, 
                        text="GDSII (.gds)")


# ============================================================================
# REGISTRATION
# ============================================================================

# Properties to store PDK settings in scene
def register_properties():
    bpy.types.Scene.gdsii_pdk_selection = StringProperty(
        default=next(iter(get_pdk_configs()), ''))
    bpy.types.Scene.gdsii_use_custom_config = BoolProperty(default=False)
    bpy.types.Scene.gdsii_custom_config_path = StringProperty(default='')
    bpy.types.Scene.gdsii_custom_color_path = StringProperty(default='')

def unregister_properties():
    del bpy.types.Scene.gdsii_pdk_selection
    del bpy.types.Scene.gdsii_use_custom_config
    del bpy.types.Scene.gdsii_custom_config_path
    del bpy.types.Scene.gdsii_custom_color_path

classes = (
    GDSIIPreImportDialog,
    ImportGDSII,
)

def register():
    register_properties()

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    unregister_properties()

if __name__ == "__main__":
    register()
