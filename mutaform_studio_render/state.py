"""Non-destructive core: snapshot the scene, apply the studio setup, and restore
everything exactly.  Nothing here changes the artist's own datablocks - we only
add PREFIX-named ones and record what we touch in a JSON backup on the scene.
"""

import json
import bpy

from . import common as C
from . import build
from . import camera as cam_mod

def sync_render_visibility(scene, snap):
    """Match render visibility to viewport visibility for every artist mesh:
    an object hidden in the viewport (excluded/hidden collection, eye icon,
    H-hide) must not sneak into the render either."""
    rec = {ob.name: ob.hide_render for ob in C.all_mesh_objects(scene)}
    snap["obj_hide_render"] = rec
    for ob in C.all_mesh_objects(scene):
        ob.hide_render = not ob.visible_get()


def restore_render_visibility(snap):
    for name, v in (snap.get("obj_hide_render") or {}).items():
        ob = bpy.data.objects.get(name)
        if ob:
            ob.hide_render = v


def snapshot(context, scene):
    r, vs, cy = scene.render, scene.view_settings, scene.cycles
    space, _ = C.find_view3d(context)
    return {
        "engine": r.engine,
        "film_transparent": r.film_transparent,
        "resolution_x": r.resolution_x,
        "resolution_y": r.resolution_y,
        "resolution_percentage": r.resolution_percentage,
        "view_transform": vs.view_transform,
        "look": vs.look,
        "exposure": vs.exposure,
        "gamma": vs.gamma,
        "world": scene.world.name if scene.world else None,
        "material_override": (bpy.context.view_layer.material_override.name
                              if bpy.context.view_layer.material_override else None),
        "camera": scene.camera.name if scene.camera else None,
        "cycles": {a: getattr(cy, a) for a in build.CYCLES_ATTRS if hasattr(cy, a)},
        "eevee": build.snapshot_eevee(scene),
        "perf": build.snapshot_perf(scene),
        "viewport_shading": space.shading.type if space else None,
        "vp_scene_world_render": space.shading.use_scene_world_render if space else None,
        "vp_scene_lights_render": space.shading.use_scene_lights_render if space else None,
        "vp_use_compositor": space.shading.use_compositor if space else None,
        "vp_lens": space.lens if space else None,
        "comp_group": scene.compositing_node_group.name if scene.compositing_node_group else None,
        "owns_compositor": scene.compositing_node_group is None,
    }


def apply_studio(context, scene):
    cam, rprops = scene.mutaform_cam, scene.mutaform_render
    snap = snapshot(context, scene)
    scene[C.BACKUP_KEY] = json.dumps(snap)
    scene[C.ACTIVE_KEY] = True

    # film + technical.  Film is OPAQUE during preview so camera rays show the
    # solid backplate; the Render operator flips it to transparent for the saved
    # file only.  The engine (Cycles/EEVEE) is applied by build.apply_engine below,
    # once the ground exists (EEVEE can't do the shadow catcher, so it hides it).
    r = scene.render
    r.film_transparent = False
    build.apply_resolution(scene)
    sync_render_visibility(scene, snap)   # render only what the viewport shows

    # look
    build.apply_color_management(scene)
    build.build_world(scene)
    bpy.context.view_layer.material_override = None
    build.record_object_materials(scene, snap)  # remember originals (no change yet)
    scene[C.BACKUP_KEY] = json.dumps(snap)             # apply_material_mode reads this back
    build.apply_material_mode(scene)              # override or scene materials, per toggle
    if rprops.use_shadow_catcher:
        build.build_shadow_catcher(scene, C.mesh_objects(scene))
    build.build_wireframe(scene, C.mesh_objects(scene))   # no-op unless enabled
    build.apply_perf(scene)     # fastest compute config for this machine
    build.apply_engine(scene)   # engine + quality; hides the ground under EEVEE

    # Marmoset-style Color post -> applied to the saved render (not the live
    # viewport; the 5.2 viewport compositor is unstable).  Only if the artist
    # has no compositor of their own.
    if snap["owns_compositor"]:
        build.build_compositor(scene)

    # viewport: rendered shading using the SCENE world (our HDRI) so the preview
    # matches the final render and nothing else (studio light) leaks in.
    space, _ = C.find_view3d(context)
    if space is not None:
        space.shading.type = 'RENDERED'
        space.shading.use_scene_world_render = True
        space.shading.use_scene_lights_render = True
        # live preview of the Color post (viewport compositor) - stable with our
        # node group; lets the artist see Highlights/Contrast/Saturation/etc live.
        if snap["owns_compositor"]:
            try:
                space.shading.use_compositor = 'ALWAYS'
            except Exception:
                pass
        # apply the Field of View to the viewport lens
        space.lens = C.fov_to_lens(cam.cam_fov)
    cam_mod.enable_overlay()

    # re-persist the backup now that snap holds the per-object material record
    scene[C.BACKUP_KEY] = json.dumps(snap)


def restore(context, scene):
    raw = scene.get(C.BACKUP_KEY)
    if not raw:
        return False, "No backup found - nothing to restore."
    snap = json.loads(raw)
    r, vs, vl = scene.render, scene.view_settings, bpy.context.view_layer

    cam_mod.disable_overlay()

    if snap.get("owns_compositor"):
        build.clear_compositor(scene, snap.get("comp_group"))

    space, _ = C.find_view3d(context)
    if space is not None:
        try:
            if snap.get("viewport_shading"):
                space.shading.type = snap["viewport_shading"]
            if snap.get("vp_scene_world_render") is not None:
                space.shading.use_scene_world_render = snap["vp_scene_world_render"]
            if snap.get("vp_scene_lights_render") is not None:
                space.shading.use_scene_lights_render = snap["vp_scene_lights_render"]
            if snap.get("vp_use_compositor") is not None:
                space.shading.use_compositor = snap["vp_use_compositor"]
            if snap.get("vp_lens") is not None:
                space.lens = snap["vp_lens"]
        except Exception:
            pass

    # reassign originals before deleting ours
    vl.material_override = (bpy.data.materials.get(snap["material_override"])
                            if snap.get("material_override") else None)
    build.restore_object_materials(snap)   # put the artists' materials back
    restore_render_visibility(snap)               # put the artists' hide_render back
    scene.world = bpy.data.worlds.get(snap["world"]) if snap.get("world") else None
    scene.camera = bpy.data.objects.get(snap["camera"]) if snap.get("camera") else None

    # sweep-delete everything we created
    for ob in [o for o in bpy.data.objects if o.name.startswith(C.PREFIX)]:
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.materials,
                 bpy.data.worlds, bpy.data.images):
        for d in [x for x in coll if x.name.startswith(C.PREFIX)]:
            try:
                coll.remove(d)
            except Exception:
                pass

    # restore scalar settings
    r.engine = snap["engine"]
    r.film_transparent = snap["film_transparent"]
    r.resolution_x = snap["resolution_x"]
    r.resolution_y = snap["resolution_y"]
    r.resolution_percentage = snap["resolution_percentage"]
    try:
        vs.view_transform = snap["view_transform"]
        vs.look = snap["look"]
        vs.exposure = snap["exposure"]
        vs.gamma = snap["gamma"]
    except Exception:
        pass
    for a, v in (snap.get("cycles") or {}).items():
        try:
            setattr(scene.cycles, a, v)
        except Exception:
            pass
    if snap.get("eevee"):
        build.restore_eevee(scene, snap["eevee"])
    build.restore_perf(scene, snap.get("perf"))

    for k in (C.BACKUP_KEY, C.ACTIVE_KEY):
        if k in scene.keys():
            del scene[k]
    return True, "Restored original scene state."
