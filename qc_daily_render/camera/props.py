"""The camera 'look' property group and its live-apply callbacks: HDRI lighting,
override-material colour, colour management, Marmoset-style Post Effect, wireframe
overlay, backplate colour and the frame-guide opacity."""

import bpy
from bpy.props import (FloatProperty, FloatVectorProperty, EnumProperty, BoolProperty)

from .. import common as C
from .. import build


# --------------------------------------------------------------------------- #
#  Live-apply callbacks (only act while the studio setup is active)
# --------------------------------------------------------------------------- #
def _world_update(self, context):
    if C.is_active(context.scene):
        build.apply_world_params(context.scene)


def _material_update(self, context):
    if C.is_active(context.scene):
        build.apply_material_params(context.scene)


def _material_mode_update(self, context):
    if C.is_active(context.scene):
        build.apply_material_mode(context.scene)


def _color_update(self, context):
    if C.is_active(context.scene):
        build.apply_color_management(context.scene)


def _post_update(self, context):
    if C.is_active(context.scene):
        build.apply_post_params(context.scene)
        C.tag_redraw()


def _frame_update(self, context):
    C.tag_redraw()


def _wire_toggle_update(self, context):
    """Turning the overlay on/off adds or removes the wireframe instances."""
    if C.is_active(context.scene):
        build.build_wireframe(context.scene, C.mesh_objects(context.scene))
        C.tag_redraw()


def _wire_param_update(self, context):
    if C.is_active(context.scene):
        build.apply_wireframe_params(context.scene)
        C.tag_redraw()


def _fov_update(self, context):
    if not C.is_active(context.scene):
        return
    space, _ = C.find_view3d(context)
    if space is not None:
        space.lens = C.fov_to_lens(self.cam_fov)
    C.tag_redraw()


def _yaw_get(self):
    """Read the real world-mapping rotation so the UI always shows the truth,
    even when an external tool rotates the HDRI."""
    w = bpy.data.worlds.get(C.WORLD_NAME)
    if w and w.use_nodes:
        mp = next((n for n in w.node_tree.nodes if n.type == 'MAPPING'), None)
        if mp:
            return mp.inputs["Rotation"].default_value[2]
    return self.get("_env_yaw", C.DEFAULT_ENV_YAW)


def _yaw_set(self, value):
    self["_env_yaw"] = value      # remembered so it survives Setup/Restore cycles
    w = bpy.data.worlds.get(C.WORLD_NAME)
    if w and w.use_nodes:
        mp = next((n for n in w.node_tree.nodes if n.type == 'MAPPING'), None)
        if mp:
            mp.inputs["Rotation"].default_value[2] = value


# --------------------------------------------------------------------------- #
#  Property group
# --------------------------------------------------------------------------- #
class MutaformCameraProps(bpy.types.PropertyGroup):
    # lighting
    env_strength: FloatProperty(name="HDRI Brightness", default=C.DEFAULT_ENV_STRENGTH,
                                min=0.0, soft_max=20.0,
                                description="World lighting strength", update=_world_update)
    env_yaw: FloatProperty(name="HDRI Rotation", subtype='ANGLE',
                           description="Environment rotation (live-synced to the world node)",
                           get=_yaw_get, set=_yaw_set)
    # override material
    use_default_material: BoolProperty(
        name="Use Default Material", default=True,
        description="On: render every mesh with one unified studio material. "
                    "Off: render each mesh with the material(s) already in the scene",
        update=_material_mode_update)
    mat_base_color: FloatVectorProperty(name="Base Color", subtype='COLOR', size=3,
                                        min=0.0, max=1.0, default=(0.148784, 0.148784, 0.148784),
                                        update=_material_update)
    mat_roughness: FloatProperty(name="Roughness", default=0.30, min=0.0, max=1.0,
                                 update=_material_update)
    mat_metallic: FloatProperty(name="Metallic", default=0.4, min=0.0, max=1.0,
                                update=_material_update)
    # --- Color (Marmoset Post Effect > Color).  Tone Mapping + Exposure show in
    #     the preview (view pipeline); the tonal/saturation controls are applied
    #     to the saved render via the compositor. ---
    tone_mapping: EnumProperty(
        name="Tone Mapping", default='Linear', update=_color_update,
        items=[('Linear', "Linear", "Plain sRGB (Marmoset Linear)"),
               ('Filmic', "Filmic", "Filmic"),
               ('AgX', "AgX", "AgX wide-gamut"),
               ('PBR', "PBR Neutral", "Khronos PBR Neutral")])
    exposure: FloatProperty(name="Exposure", default=1.0, min=0.0, soft_max=8.0,
                            description="Exposure multiplier", update=_color_update)
    highlights: FloatProperty(name="Highlights", default=0.5, min=0.0, max=1.0, update=_post_update)
    midtones: FloatProperty(name="Midtones", default=0.0, min=-1.0, max=1.0, update=_post_update)
    shadows: FloatProperty(name="Shadows", default=0.0, min=-1.0, max=1.0, update=_post_update)
    clarity: FloatProperty(name="Clarity", default=0.096774, min=0.0, max=1.0, update=_post_update)
    contrast: FloatProperty(name="Contrast", default=1.0, min=0.0, soft_max=2.0, update=_post_update)
    contrast_center: FloatProperty(name="Contrast Center", default=0.5, min=0.0, max=1.0,
                                   update=_post_update)
    saturation: FloatProperty(name="Saturation", default=1.146628, min=0.0, max=2.0, update=_post_update)
    # Sharpen
    sharpen_strength: FloatProperty(name="Strength", default=2.0, min=0.0, soft_max=5.0,
                                    update=_post_update)
    sharpen_limit: FloatProperty(name="Limit", default=0.15, min=0.0, max=1.0, update=_post_update)
    # Vignette
    vignette_strength: FloatProperty(name="Strength", default=0.0, min=0.0, max=1.0, update=_post_update)
    vignette_softness: FloatProperty(name="Softness", default=0.0, min=0.0, max=1.0, update=_post_update)
    # camera
    cam_fov: FloatProperty(name="Field of View", default=15.0, min=1.0, max=170.0,
                           description="Vertical field of view (degrees)", update=_fov_update)
    # wireframe overlay (real geometry -> WYSIWYG; clean quad topology via the
    # Wireframe modifier, shown both in the viewport and the final render)
    wireframe_on: BoolProperty(
        name="Wireframe", default=False,
        description="Overlay a wireframe of the model's topology (clean quads)",
        update=_wire_toggle_update)
    wireframe_color: FloatVectorProperty(
        name="Color", subtype='COLOR', size=3, min=0.0, max=1.0,
        default=(1.0, 0.574079, 0.002715),
        description="Wireframe colour", update=_wire_param_update)
    wireframe_thickness: FloatProperty(
        name="Thickness", default=1.0, min=0.0, max=1.0,
        description="Wireframe line thickness", update=_wire_param_update)
    wireframe_opacity: FloatProperty(
        name="Opacity", default=1.0, min=0.0, max=1.0,
        description="Wireframe opacity over the shaded model", update=_wire_param_update)
    # collapsible section toggles
    show_camera_block: BoolProperty(default=False)
    show_posteffect: BoolProperty(default=True)
    show_sharpen: BoolProperty(default=True)
    show_vignette: BoolProperty(default=False)
    # backplate (preview only; final render stays transparent)
    background_color: FloatVectorProperty(
        name="Background", subtype='COLOR', size=3, min=0.0, max=1.0,
        default=(0.009134, 0.010960, 0.010330),
        description="Solid background shown behind the model in the preview "
                    "(the saved render stays transparent)",
        update=_world_update)
    # frame guide
    frame_opacity: FloatProperty(name="Frame Opacity", default=0.75, min=0.0, max=1.0,
                                 description="Darken everything outside the render frame",
                                 update=_frame_update)
