"""Wireframe overlay (Marmoset "Wireframe" visibility).

The Cycles Wireframe shader node triangulates quads (diagonals), so instead we
mirror the ZBrush approach: a duplicate of each mesh with a WIREFRAME MODIFIER
(respects the real quad topology) and a flat emission material.  Real geometry ->
it shows identically in the viewport and the final render (WYSIWYG)."""

import bpy

from .. import common as C


def _wire_thickness(scene, targets):
    mins, maxs = C.scene_bounds(targets)
    size = max(maxs.x - mins.x, maxs.y - mins.y, maxs.z - mins.z, 1.0)
    return size * 0.0006 * scene.mutaform_cam.wireframe_thickness


def _scale_factor(ob):
    """Average magnitude of the object's scale.  The Wireframe modifier's
    thickness is a LOCAL-space (mesh) value that gets shrunk/grown again by the
    object's own transform - an asset modelled at 100x and scaled down to 0.01
    would otherwise render a wire 100x thinner than intended.  Divide by this to
    compensate."""
    s = ob.scale
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-6)


def build_wireframe(scene, targets):
    for o in [o for o in bpy.data.objects if o.name.startswith(C.WIRE_PREFIX)]:
        bpy.data.objects.remove(o, do_unlink=True)
    if not scene.mutaform_cam.wireframe_on:
        wm = bpy.data.materials.get(C.WIRE_MAT_NAME)
        if wm:
            bpy.data.materials.remove(wm)
        return

    mat = _build_wire_material(scene)
    thick = _wire_thickness(scene, targets)
    for ob in targets:
        w = bpy.data.objects.new(C.WIRE_PREFIX + ob.name, ob.data)
        scene.collection.objects.link(w)
        w.matrix_world = ob.matrix_world.copy()
        w.hide_select = True
        w.is_shadow_catcher = False
        m = w.modifiers.new("MUTAFORM_Wire", 'WIREFRAME')
        m.thickness = thick / _scale_factor(ob)
        m.use_replace = True
        m.use_boundary = True
        m.use_even_offset = False
        if len(w.material_slots) == 0:
            w.data.materials.append(mat)
        else:
            for s in w.material_slots:
                s.link = 'OBJECT'
                s.material = mat
    apply_wireframe_params(scene)


def _build_wire_material(scene):
    mat = bpy.data.materials.get(C.WIRE_MAT_NAME) or bpy.data.materials.new(C.WIRE_MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.name = "WireMix"
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    emis = nt.nodes.new("ShaderNodeEmission"); emis.name = "WireEmis"
    out.location, mix.location = (400, 0), (200, 0)
    transp.location, emis.location = (0, 120), (0, -80)
    nt.links.new(transp.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emis.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def apply_wireframe_params(scene):
    cam = scene.mutaform_cam
    mat = bpy.data.materials.get(C.WIRE_MAT_NAME)
    if mat and mat.use_nodes:
        emis = mat.node_tree.nodes.get("WireEmis")
        mix = mat.node_tree.nodes.get("WireMix")
        if emis:
            c = cam.wireframe_color
            emis.inputs["Color"].default_value = (c[0], c[1], c[2], 1.0)
        if mix:
            mix.inputs[0].default_value = cam.wireframe_opacity   # 0 -> transparent, 1 -> solid
    thick = _wire_thickness(scene, C.mesh_objects(scene))
    for o in [o for o in bpy.data.objects if o.name.startswith(C.WIRE_PREFIX)]:
        orig = bpy.data.objects.get(o.name[len(C.WIRE_PREFIX):])
        factor = _scale_factor(orig) if orig else 1.0
        for m in o.modifiers:
            if m.type == 'WIREFRAME':
                m.thickness = thick / factor
