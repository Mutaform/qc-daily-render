"""Ground = Marmoset-style "Indirect Shadows": a real Cycles shadow catcher plane
(is_shadow_catcher=True).  It is invisible where lit, so only the contact shadow
goes into the alpha - no visible ground disc, and the shadow composites onto ANY
background (green screen, transparent PNG).

Also keeps the wireframe duplicates glued to their source objects live via
sync_helper_transforms (called from the depsgraph handler in camera.overlay)."""

import bpy

from .. import common as C


def build_shadow_catcher(scene, targets):
    mins, maxs = C.scene_bounds(targets)
    center = (mins + maxs) * 0.5
    floor_z = mins.z
    _build_catcher_plane(scene, center, mins, maxs, floor_z)
    return bpy.data.objects.get(C.FLOOR_NAME)


def _build_catcher_plane(scene, center, mins, maxs, floor_z):
    """A transparent shadow-catcher plane, sized to the objects' footprint plus a
    margin so cast shadows never run off the edge.  Being a shadow catcher it is
    invisible where lit (only the shadow shows) - the margin is scaled to the
    scene (not a fixed metre count) so it works from centimetre props to large
    sets, while staying small enough that 'View All' still frames sensibly."""
    mesh = bpy.data.meshes.get(C.FLOOR_MESH_NAME) or bpy.data.meshes.new(C.FLOOR_MESH_NAME)
    obj = bpy.data.objects.get(C.FLOOR_NAME)
    if obj is None:
        obj = bpy.data.objects.new(C.FLOOR_NAME, mesh)
        scene.collection.objects.link(obj)
    else:
        obj.data = mesh
    dx, dy, dz = maxs.x - mins.x, maxs.y - mins.y, maxs.z - mins.z
    margin = max(dx, dy, dz, 1.0)          # ~one object-size of shadow room per side
    hx, hy = dx * 0.5 + margin, dy * 0.5 + margin
    mesh.clear_geometry()
    mesh.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj.location = (center.x, center.y, floor_z)
    obj.is_shadow_catcher = True       # transparent + shadow only -> any background
    obj.hide_select = True
    obj.data.materials.clear()
    obj.data.materials.append(_build_catcher_material())
    return obj


def _build_catcher_material():
    """Diffuse on the top (front) face so the catcher receives shadow cleanly,
    but Transparent on the underside (back face) - so viewing the model from below
    the floor sees straight through the plane instead of hitting its underside."""
    mat = bpy.data.materials.get(C.FLOOR_MAT_NAME) or bpy.data.materials.new(C.FLOOR_MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    diff = nt.nodes.new("ShaderNodeBsdfPrincipled")
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    out.location, mix.location = (500, 0), (300, 0)
    diff.location, transp.location, geo.location = (60, 160), (60, -80), (60, -280)
    diff.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    diff.inputs["Metallic"].default_value = 0.0
    diff.inputs["Roughness"].default_value = 1.0
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])   # 0 front, 1 back
    nt.links.new(diff.outputs["BSDF"], mix.inputs[1])            # front -> catches shadow
    nt.links.new(transp.outputs["BSDF"], mix.inputs[2])         # back  -> see-through
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def sync_helper_transforms(scene):
    """Keep the wireframe duplicates glued to their source object when the artist
    moves/rotates/scales it.  Called from a depsgraph_update_post handler (see
    camera.overlay.enable_overlay); only writes a matrix when it actually changed,
    to skip needless work and avoid re-triggering the same handler."""
    for o in bpy.data.objects:
        if o.name.startswith(C.WIRE_PREFIX):
            orig = bpy.data.objects.get(o.name[len(C.WIRE_PREFIX):])
            if orig and o.matrix_world != orig.matrix_world:
                o.matrix_world = orig.matrix_world.copy()
