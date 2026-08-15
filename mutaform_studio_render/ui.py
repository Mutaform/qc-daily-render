"""Sidebar UI (View3D > N > QC Render).

One panel: the always-on-top actions (Setup / Render + Restore), then a tab bar
that switches between the Camera (image) block and the Render (technical) block.
"""

import bpy

from . import common as C
from . import render as render_mod

CATEGORY = "QC Render"

# tab bar backing property (registered on Scene from __init__)
TAB_ITEMS = [
    ('CAMERA', "Camera Settings", "Image: lighting, colour, material, frame guide, background", 'IMAGE', 0),
    ('RENDER', "Render Settings", "Technical: engine, resolution, samples, denoiser, output", 'OUTPUT', 1),
]


def _fold(layout, cam, key, title):
    """A collapsible section box; returns (box, expanded)."""
    box = layout.box()
    row = box.row(align=True)
    row.prop(cam, key, text="",
             icon='TRIA_DOWN' if getattr(cam, key) else 'TRIA_RIGHT', emboss=False)
    row.label(text=title)
    return box, getattr(cam, key)


def _rrow(layout, cam, prop, text=None, slider=False):
    """A value row with a small reset-to-default button on the right."""
    row = layout.row(align=True)
    kw = {"slider": slider}
    if text is not None:
        kw["text"] = text
    row.prop(cam, prop, **kw)
    row.operator("mutaform.reset_prop", text="", icon='LOOP_BACK').prop = prop


def _draw_material(layout, cam):
    box = layout.box()
    row = box.row(align=True)
    row.prop(cam, "use_default_material")
    if cam.use_default_material:
        _rrow(box, cam, "mat_base_color")
        _rrow(box, cam, "mat_roughness")
        _rrow(box, cam, "mat_metallic")


def _draw_camera(layout, cam):
    box = layout.box()
    box.label(text="Camera", icon='CAMERA_DATA')
    _rrow(box, cam, "cam_fov")

    box = layout.box()
    box.label(text="Lighting", icon='WORLD')
    _rrow(box, cam, "env_strength")
    _rrow(box, cam, "env_yaw")

    # --- Post Effect (collapsible) ---
    box, open_ = _fold(layout, cam, "show_posteffect", "Post Effect")
    if open_:
        row = box.row(align=True)
        row.label(text="Tone Mapping")
        row.prop(cam, "tone_mapping", text="")
        row.operator("mutaform.curves", text="Curves...")
        col = box.column(align=True)
        col.scale_y = 1.15
        for p in ("exposure", "highlights", "midtones", "shadows",
                  "clarity", "contrast", "contrast_center", "saturation"):
            _rrow(col, cam, p, slider=True)

    # --- Sharpen (collapsible) ---
    box, open_ = _fold(layout, cam, "show_sharpen", "Sharpen")
    if open_:
        col = box.column(align=True)
        col.scale_y = 1.15
        _rrow(col, cam, "sharpen_strength", slider=True)
        _rrow(col, cam, "sharpen_limit", slider=True)

    # --- Vignette (collapsible) ---
    box, open_ = _fold(layout, cam, "show_vignette", "Vignette")
    if open_:
        col = box.column(align=True)
        col.scale_y = 1.15
        _rrow(col, cam, "vignette_strength", slider=True)
        _rrow(col, cam, "vignette_softness", slider=True)

    # Frame Guide + Background share one row: frame opacity on the left half,
    # the preview backplate colour on the right half.
    box = layout.box()
    split = box.split(factor=0.667, align=True)   # frame opacity 2/3, background 1/3
    left = split.column(align=True)
    left.label(text="Frame Guide", icon='CAMERA_DATA')
    _rrow(left, cam, "frame_opacity", slider=True)
    right = split.column(align=True)
    right.label(text="Background", icon='WORLD')
    _rrow(right, cam, "background_color", text="")


def _draw_wireframe(layout, cam):
    box = layout.box()
    row = box.row(align=True)
    row.prop(cam, "wireframe_on")
    if cam.wireframe_on:
        _rrow(box, cam, "wireframe_color", text="")
        _rrow(box, cam, "wireframe_thickness", slider=True)
        _rrow(box, cam, "wireframe_opacity", slider=True)


def _draw_render(layout, scene, r):
    row = layout.row(align=True)
    row.scale_y = 1.2
    row.prop(r, "preview_engine", expand=True)

    box = layout.box()
    box.label(text="Resolution", icon='OUTPUT')
    row = box.row(align=True)
    row.operator("mutaform.res_scale", text="", icon='TRIA_LEFT').factor = 0.5
    row.prop(r, "render_x", text="")
    row.prop(r, "render_y", text="")
    row.operator("mutaform.res_scale", text="", icon='TRIA_RIGHT').factor = 2.0

    box = layout.box()
    box.label(text="Quality", icon='SETTINGS')
    box.prop(r, "samples")
    box.prop(r, "denoiser")
    box.prop(r, "use_shadow_catcher")

    box = layout.box()
    box.label(text="Output", icon='FILE_IMAGE')
    box.prop(r, "output_dir")
    box.prop(r, "output_base")
    if not r.output_dir:
        sub = box.row()
        sub.active = False
        sub.label(text=render_mod.resolved_output_dir(scene), icon='FILE_FOLDER')


class MUTAFORM_PT_main(bpy.types.Panel):
    bl_label = "Daily Render by Mutaform"
    bl_idname = "MUTAFORM_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # version, right-aligned and muted (a separator_spacer() in draw_header
        # instead corrupts the panel's body-width calc and shifts every row
        # right off the plate - keep it in the body)
        vrow = layout.row()
        vrow.alignment = 'RIGHT'
        vrow.label(text=C.VERSION_STR)

        # --- always-on-top actions ---
        if not C.is_active(scene):
            col = layout.column()
            col.scale_y = 1.4
            col.operator("mutaform.studio_setup", icon='RENDER_STILL')
        else:
            split = layout.split(factor=0.667, align=True)
            split.scale_y = 1.5
            split.operator("mutaform.studio_render", icon='RENDER_STILL')
            split.operator("mutaform.open_output", text="Open Folder", icon='FILE_FOLDER')
            layout.operator("mutaform.studio_restore", text="Restore (exit)", icon='LOOP_BACK')
            layout.label(text="Navigate the viewport, then Render.", icon='INFO')

        layout.separator()

        # --- tab bar + selected block ---
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.prop(scene, "mutaform_tab", expand=True)

        # tab content is inert until Setup builds the studio scene - grey it out
        body = layout.column()
        body.enabled = C.is_active(scene)
        if scene.mutaform_tab == 'CAMERA':
            _draw_material(body, scene.mutaform_cam)
            box, open_ = _fold(body, scene.mutaform_cam, "show_camera_block", "Camera Settings")
            if open_:
                _draw_camera(box, scene.mutaform_cam)
            _draw_wireframe(body, scene.mutaform_cam)
        else:
            _draw_render(body, scene, scene.mutaform_render)


classes = (MUTAFORM_PT_main,)
