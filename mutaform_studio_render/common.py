"""Shared constants and small helpers used across the whole addon.

Keep this module dependency-free (only bpy / mathutils) so every other module
can import it without creating import cycles.
"""

import os
import math
import bpy
from mathutils import Vector

# --- names of everything we create (all prefixed so restore can sweep them) ---
PREFIX = "MUTAFORM_"
IMG_NAME = PREFIX + "WhiteContainers"
WORLD_NAME = PREFIX + "World"
MAT_NAME = PREFIX + "OverrideMat"
CAM_NAME = PREFIX + "Camera"
CAM_DATA_NAME = PREFIX + "CameraData"
FLOOR_NAME = PREFIX + "ShadowCatcher"
FLOOR_MESH_NAME = PREFIX + "ShadowCatcherMesh"
FLOOR_MAT_NAME = PREFIX + "FloorMat"
WIRE_PREFIX = PREFIX + "Wire_"        # wireframe-overlay instances
WIRE_MAT_NAME = PREFIX + "WireMat"

# per-scene custom properties that hold our state
BACKUP_KEY = "mutaform_studio_backup"   # JSON snapshot of the pre-setup scene
ACTIVE_KEY = "mutaform_studio_active"   # bool: studio setup currently applied

ADDON_DIR = os.path.dirname(__file__)
EXR_PATH = os.path.join(ADDON_DIR, "assets", "white_containers_4k.exr")

# calibrated defaults for the WhiteContainers HDRI (match Marmoset setup)
DEFAULT_ENV_STRENGTH = 2.8
DEFAULT_ENV_YAW = math.radians(253.0)   # HDRI rotation

VERSION = (1, 5, 10)
VERSION_STR = "ver %d.%d.%d" % VERSION


def is_active(scene):
    return bool(scene.get(ACTIVE_KEY))


def fov_to_lens(fov_deg):
    """Viewport focal length for a vertical field of view, based on a full-frame
    24mm sensor height (matches Marmoset).  37.85 deg == 35mm."""
    return 12.0 / max(math.tan(math.radians(fov_deg) * 0.5), 1e-4)


def mesh_objects(scene):
    """Artist mesh objects visible in the viewport (excludes anything we
    created, and anything hidden - hidden/excluded collection or the eye
    icon / H-hide - so a hidden object gets no studio material or wireframe,
    matching what the artist actually sees)."""
    return [o for o in scene.objects if o.type == 'MESH' and not o.name.startswith(PREFIX)
            and o.visible_get()]


def all_mesh_objects(scene):
    """Every artist mesh object regardless of visibility - used to sync
    render visibility to the viewport (see state.sync_render_visibility)."""
    return [o for o in scene.objects if o.type == 'MESH' and not o.name.startswith(PREFIX)]


def scene_bounds(objects):
    """World-space (min, max) bounding box of the given objects."""
    mins = Vector((float('inf'),) * 3)
    maxs = Vector((float('-inf'),) * 3)
    found = False
    for ob in objects:
        for corner in ob.bound_box:
            wc = ob.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], wc[i])
                maxs[i] = max(maxs[i], wc[i])
            found = True
    if not found:
        return Vector((-1, -1, 0)), Vector((1, 1, 1))
    return mins, maxs


def find_view3d(context):
    """Return (space, region_3d) of a 3D viewport, preferring the active area."""
    area = getattr(context, "area", None)
    if area and area.type == 'VIEW_3D':
        s = area.spaces.active
        return s, s.region_3d
    for win in context.window_manager.windows:
        for a in win.screen.areas:
            if a.type == 'VIEW_3D':
                s = a.spaces.active
                return s, s.region_3d
    return None, None


def find_view3d_full(context):
    """Return (area, region, space, region_3d) for a 3D viewport, or Nones."""
    pref = getattr(context, "area", None)
    areas = ([pref] if pref and pref.type == 'VIEW_3D' else [])
    for win in context.window_manager.windows:
        for a in win.screen.areas:
            if a.type == 'VIEW_3D' and a not in areas:
                areas.append(a)
    for a in areas:
        region = next((r for r in a.regions if r.type == 'WINDOW'), None)
        space = a.spaces.active
        if region and space:
            return a, region, space, space.region_3d
    return None, None, None, None


def tag_redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
