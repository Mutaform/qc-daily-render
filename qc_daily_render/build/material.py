"""Override material: one unified studio material applied per-object (object-level
slots, not view_layer.material_override, so the floor can keep its own look).
Also snapshots/restores each artist mesh's original material slots."""

import json

import bpy

from .. import common as C


def build_material(scene):
    mat = bpy.data.materials.get(C.MAT_NAME) or bpy.data.materials.new(C.MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out.location, bsdf.location = (300, 0), (0, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    apply_material_params(scene)
    return mat


def record_object_materials(scene, snap):
    """Record each artist mesh's original material slots into snap (without
    changing anything) so we can restore them, or switch to the override, later."""
    rec = {}
    for ob in C.mesh_objects(scene):
        slots = ob.material_slots
        if len(slots) == 0:
            rec[ob.name] = "APPEND"
        else:
            rec[ob.name] = [[s.link, s.material.name if s.material else ""] for s in slots]
    snap["obj_materials"] = rec
    return rec


def apply_material_mode(scene):
    """Switch every artist mesh between the single studio override material and
    its own scene materials, based on `mutaform_cam.use_default_material`."""
    cam = scene.mutaform_cam
    if cam.use_default_material:
        mat = build_material(scene)
        for ob in C.mesh_objects(scene):
            slots = ob.material_slots
            if len(slots) == 0:
                if mat.name not in {m.name for m in ob.data.materials if m}:
                    ob.data.materials.append(mat)
            else:
                for s in slots:
                    s.link = 'OBJECT'
                    s.material = mat
    else:
        raw = scene.get(C.BACKUP_KEY)
        if raw:
            restore_object_materials(json.loads(raw))


def restore_object_materials(snap):
    for name, data in (snap.get("obj_materials") or {}).items():
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        if data == "APPEND":
            if ob.data.materials:
                ob.data.materials.pop()
        else:
            for s, entry in zip(ob.material_slots, data):
                try:
                    s.link = entry[0]
                    s.material = bpy.data.materials.get(entry[1]) if entry[1] else None
                except Exception:
                    pass


def apply_material_params(scene):
    mat = bpy.data.materials.get(C.MAT_NAME)
    if not mat or not mat.use_nodes:
        return
    cam = scene.mutaform_cam
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    c = cam.mat_base_color
    bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1.0)
    bsdf.inputs["Metallic"].default_value = cam.mat_metallic
    bsdf.inputs["Roughness"].default_value = cam.mat_roughness
