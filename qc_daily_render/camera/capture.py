"""Capture: place a camera on the current viewport view, render exactly what the
artist framed, save an auto-numbered PNG, then remove the camera.

The render runs MODAL (INVOKE_DEFAULT) so Blender shows its native progress bar
and the UI stays responsive.  Because the modal render returns immediately, the
settings/camera teardown happens in render_complete / render_cancel handlers
(state stashed in _render_ctx)."""

import bpy

from .. import common as C
from .. import render as render_mod


def match_camera_to_view(cam_data, r3d, region, scene):
    """Set lens/sensor so the render frame equals the inscribed frame the artist
    sees (same fit rule as overlay.frame_rect)."""
    render_aspect = scene.render.resolution_x / max(scene.render.resolution_y, 1)
    reg_aspect = region.width / max(region.height, 1)
    wm = r3d.window_matrix
    if r3d.is_perspective:
        cam_data.type = 'PERSP'
        tan_hx, tan_vy = 1.0 / wm[0][0], 1.0 / wm[1][1]
        if render_aspect >= reg_aspect:
            cam_data.sensor_fit = 'HORIZONTAL'
            cam_data.lens = 0.5 * cam_data.sensor_width / max(abs(tan_hx), 1e-6)
        else:
            cam_data.sensor_fit = 'VERTICAL'
            cam_data.lens = 0.5 * cam_data.sensor_height / max(abs(tan_vy), 1e-6)
    else:
        cam_data.type = 'ORTHO'
        half = 1.0 / (wm[0][0] if render_aspect >= reg_aspect else wm[1][1])
        cam_data.sensor_fit = 'HORIZONTAL' if render_aspect >= reg_aspect else 'VERTICAL'
        cam_data.ortho_scale = 2.0 * abs(half)


# --------------------------------------------------------------------------- #
#  Modal-render teardown (shared with overlay.disable_overlay via _unhook)
# --------------------------------------------------------------------------- #
_render_ctx = {}


def _unhook_render_handlers():
    for lst, fn in ((bpy.app.handlers.render_complete, _on_render_complete),
                    (bpy.app.handlers.render_cancel, _on_render_cancel)):
        if fn in lst:
            lst.remove(fn)


def _finish_render(scene):
    st = _render_ctx.pop("state", None)
    _unhook_render_handlers()
    if not st:
        return
    rs = scene.render
    (rs.filepath, rs.image_settings.file_format,
     rs.image_settings.color_mode, rs.film_transparent) = st["keep"]
    bpy.context.preferences.view.render_display_type = st["display_type"]
    if not st["use_scene_cam"]:
        scene.camera = st["prev_cam"]
        cam = bpy.data.objects.get(C.CAM_NAME)
        if cam:
            bpy.data.objects.remove(cam, do_unlink=True)
        cd = bpy.data.cameras.get(C.CAM_DATA_NAME)
        if cd:
            bpy.data.cameras.remove(cd)
    C.tag_redraw()


def _finish_timer():
    """Runs the teardown from a timer (safe main-loop context) - see _defer_finish."""
    scene = _render_ctx.pop("finish_scene", None) or bpy.context.scene
    _finish_render(scene)
    return None   # one-shot


def _defer_finish(scene):
    """Schedule the teardown instead of running it inline.

    The render_complete / render_cancel handlers fire from INSIDE Blender's render
    pipeline (BKE_callback_exec_id during RE_RenderFrame).  Removing a datablock
    there - the temp camera - triggers id_delete -> collection cache free ->
    depsgraph tag update against a half-torn-down depsgraph and crashes Blender
    with EXCEPTION_ACCESS_VIOLATION (reproduced on a heavy scene by an artist).
    A 0s timer defers the removal to the next main-loop tick, where deleting IDs
    is safe."""
    _render_ctx["finish_scene"] = scene
    if not bpy.app.timers.is_registered(_finish_timer):
        bpy.app.timers.register(_finish_timer, first_interval=0.0)


def _on_render_complete(*args):
    _defer_finish(args[0] if args else bpy.context.scene)


def _on_render_cancel(*args):
    _defer_finish(args[0] if args else bpy.context.scene)


class MUTAFORM_OT_render(bpy.types.Operator):
    bl_idname = "mutaform.studio_render"
    bl_label = "Render"
    bl_description = ("Place a camera on the current viewport view, render exactly what "
                      "you framed, save it, then remove the camera - the view is untouched")
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        if not C.is_active(scene):
            self.report({'WARNING'}, "Press 'Setup Render Scene' first.")
            return {'CANCELLED'}
        if _render_ctx.get("state"):
            self.report({'WARNING'}, "A render is already in progress.")
            return {'CANCELLED'}
        area, region, space, r3d = C.find_view3d_full(context)
        if r3d is None:
            self.report({'ERROR'}, "No 3D viewport found to capture.")
            return {'CANCELLED'}

        prev_cam = scene.camera
        # If the viewport is looking THROUGH a camera, render straight through it
        # at its real lens/sensor - an exact match (e.g. marmoset_cam @ 17.5mm).
        # Reconstructing from a camera-view viewport would nearly halve the FOV, so
        # only reconstruct for the FREE navigation view.
        use_scene_cam = (r3d.view_perspective == 'CAMERA'
                         and scene.camera is not None and scene.camera.type == 'CAMERA')
        if use_scene_cam:
            cam = scene.camera
        else:
            cam_data = bpy.data.cameras.get(C.CAM_DATA_NAME) or bpy.data.cameras.new(C.CAM_DATA_NAME)
            cam_data.sensor_width = cam_data.sensor_height = 36.0
            cam_data.clip_start, cam_data.clip_end = space.clip_start, space.clip_end
            cam = bpy.data.objects.get(C.CAM_NAME) or bpy.data.objects.new(C.CAM_NAME, cam_data)
            cam.data = cam_data
            if cam.name not in scene.collection.objects:
                try:
                    scene.collection.objects.link(cam)
                except RuntimeError:
                    pass
            cam.matrix_world = r3d.view_matrix.inverted()
            match_camera_to_view(cam_data, r3d, region, scene)
            scene.camera = cam

        path = render_mod.next_output_path(scene)
        rs = scene.render
        keep = (rs.filepath, rs.image_settings.file_format,
                rs.image_settings.color_mode, rs.film_transparent)
        rs.filepath = path
        rs.image_settings.file_format = 'PNG'
        rs.image_settings.color_mode = 'RGBA'
        rs.film_transparent = True   # saved file is transparent; preview stays opaque
        display_type = bpy.context.preferences.view.render_display_type
        bpy.context.preferences.view.render_display_type = 'NONE'   # no Render Result popup

        # stash teardown state, hook completion handlers, then render modally so
        # Blender draws its progress bar and the UI keeps updating
        _render_ctx["state"] = {"keep": keep, "use_scene_cam": use_scene_cam,
                                "prev_cam": prev_cam, "path": path, "display_type": display_type}
        _unhook_render_handlers()
        bpy.app.handlers.render_complete.append(_on_render_complete)
        bpy.app.handlers.render_cancel.append(_on_render_cancel)
        bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
        eng = "EEVEE" if scene.render.engine == 'BLENDER_EEVEE' else "Cycles"
        self.report({'INFO'}, "Rendering (%s) -> %s" % (eng, path))
        return {'FINISHED'}
