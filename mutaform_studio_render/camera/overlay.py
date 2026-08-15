"""The render-frame guide drawn in the free viewport (a GPU overlay that darkens
everything outside the render frame and outlines it), plus the depsgraph handler
that keeps the wireframe duplicates glued to their source objects."""

import gpu
from gpu_extras.batch import batch_for_shader
import bpy

from .. import common as C
from .. import build
from . import capture

_draw_handle = None
_last_draw_error = None


def frame_rect(region_w, region_h, aspect):
    """Render-aspect rectangle inscribed & centered in the viewport (pixels)."""
    reg_a = region_w / max(region_h, 1)
    if aspect >= reg_a:
        w, h = region_w, region_w / aspect
    else:
        h, w = region_h, region_h * aspect
    x0, y0 = (region_w - w) * 0.5, (region_h - h) * 0.5
    return x0, y0, x0 + w, y0 + h


def _draw():
    global _last_draw_error
    try:
        ctx = bpy.context
        scene = ctx.scene
        if not scene or not C.is_active(scene):
            return
        area, region = ctx.area, ctx.region
        space = ctx.space_data
        rv3d = space.region_3d if space and hasattr(space, "region_3d") else None
        if not area or area.type != 'VIEW_3D' or not region or region.type != 'WINDOW':
            return
        if rv3d and rv3d.view_perspective == 'CAMERA':
            return
        cam = scene.mutaform_cam
        W, H = region.width, region.height
        aspect = scene.mutaform_render.render_x / max(scene.mutaform_render.render_y, 1)
        x0, y0, x1, y1 = frame_rect(W, H, aspect)
        alpha = cam.frame_opacity

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        shader.bind()

        def rect(ax, ay, bx, by, color):
            shader.uniform_float("color", color)
            v = [(ax, ay), (bx, ay), (bx, by), (ax, ay), (bx, by), (ax, by)]
            batch_for_shader(shader, 'TRIS', {"pos": v}).draw(shader)

        if alpha > 0.0:
            d = (0.0, 0.0, 0.0, alpha)
            rect(0, 0, W, y0, d)
            rect(0, y1, W, H, d)
            rect(0, y0, x0, y1, d)
            rect(x1, y0, W, y1, d)

        gpu.state.line_width_set(2.0)
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.5))
        outline = [(x0, y0), (x1, y0), (x1, y0), (x1, y1),
                   (x1, y1), (x0, y1), (x0, y1), (x0, y0)]
        batch_for_shader(shader, 'LINES', {"pos": outline}).draw(shader)
        gpu.state.blend_set('NONE')
        _last_draw_error = None
    except Exception:
        import traceback
        _last_draw_error = traceback.format_exc()


# --------------------------------------------------------------------------- #
#  Live-track the wireframe duplicates when the artist transforms the
#  source object - a depsgraph_update_post handler keeps them glued to it.
# --------------------------------------------------------------------------- #
_depsgraph_handler = None
_syncing_transforms = False


def _on_depsgraph_update(scene, depsgraph):
    global _syncing_transforms
    if _syncing_transforms:
        return   # re-entrancy guard: our own writes below re-trigger this
    if not scene or not C.is_active(scene):
        return
    _syncing_transforms = True
    try:
        build.sync_helper_transforms(scene)
    finally:
        _syncing_transforms = False


def enable_overlay():
    global _draw_handle, _depsgraph_handler
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')
    if _depsgraph_handler is None:
        _depsgraph_handler = _on_depsgraph_update
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)
    C.tag_redraw()


def disable_overlay():
    global _draw_handle, _depsgraph_handler
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        except Exception:
            pass
        _draw_handle = None
    if _depsgraph_handler is not None:
        try:
            bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_handler)
        except Exception:
            pass
        _depsgraph_handler = None
    try:
        capture._unhook_render_handlers()
    except Exception:
        pass
    C.tag_redraw()
