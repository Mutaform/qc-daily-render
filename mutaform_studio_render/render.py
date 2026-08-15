"""Render block - the technical side of the render: output resolution, save
path, sample count and denoiser.  (Look / image controls live in camera.py.)
"""

import os
import re
import bpy
from bpy.props import IntProperty, StringProperty, EnumProperty

from . import common as C
from . import build


# --------------------------------------------------------------------------- #
#  Live-apply helpers
# --------------------------------------------------------------------------- #
def optix_available():
    """True when Cycles has an OptiX device (NVIDIA GPU present)."""
    try:
        import _cycles
        return any(d[1] == 'OPTIX' for d in _cycles.available_devices('OPTIX'))
    except Exception:
        return False


def ensure_denoiser_supported(scene):
    """Silently fall back OptiX -> OpenImageDenoise on machines without an
    NVIDIA GPU, so the final render never fails on the denoise pass."""
    r = scene.mutaform_render
    if r.denoiser == 'OPTIX' and not optix_available():
        r.denoiser = 'OPENIMAGEDENOISE'


def apply_denoise(scene):
    r = scene.mutaform_render
    cy = scene.cycles
    if r.denoiser == 'NONE':
        cy.use_denoising = False
    else:
        cy.use_denoising = True
        try:
            cy.denoiser = r.denoiser
        except Exception:
            pass


def _res_update(self, context):
    scene = context.scene
    if C.is_active(scene):
        build.apply_resolution(scene)
        C.tag_redraw()


def _samples_update(self, context):
    scene = context.scene
    if C.is_active(scene):
        try:
            scene.cycles.samples = self.samples
        except Exception:
            pass


def _denoise_update(self, context):
    scene = context.scene
    if C.is_active(scene):
        apply_denoise(scene)


def _engine_update(self, context):
    scene = context.scene
    if C.is_active(scene):
        build.apply_engine(scene)   # switch the live preview engine + quality + ground
        C.tag_redraw()


# --------------------------------------------------------------------------- #
#  Output path (auto-numbered)
# --------------------------------------------------------------------------- #
def resolved_output_dir(scene):
    """The folder renders actually land in (resolves the empty-field default)."""
    r = scene.mutaform_render
    d = bpy.path.abspath(r.output_dir) if r.output_dir else ""
    if not d:
        d = (os.path.join(os.path.dirname(bpy.data.filepath), "renders")
             if bpy.data.filepath else
             os.path.join(os.path.expanduser("~"), "MutaformRenders"))
    return d


def next_output_path(scene):
    r = scene.mutaform_render
    base = (r.output_base or "shot").strip() or "shot"
    d = resolved_output_dir(scene)
    os.makedirs(d, exist_ok=True)
    rx = re.compile(r"^%s_(\d+)\.png$" % re.escape(base), re.IGNORECASE)
    n = max([int(m.group(1)) for f in os.listdir(d) for m in [rx.match(f)] if m], default=0)
    return os.path.join(d, "%s_%03d.png" % (base, n + 1))


# --------------------------------------------------------------------------- #
#  Properties
# --------------------------------------------------------------------------- #
class MutaformRenderProps(bpy.types.PropertyGroup):
    preview_engine: EnumProperty(
        name="Engine", default='CYCLES', update=_engine_update,
        description="Render engine for both the live preview and the saved render",
        items=[('CYCLES', "Cycles", "Ray-traced: ground shadow, best quality"),
               ('BLENDER_EEVEE', "EEVEE", "Fast real-time (no ground shadow)")])
    render_x: IntProperty(name="X", default=3840, min=16, max=16384,
                          description="Render width (also sets aspect ratio)",
                          update=_res_update)
    render_y: IntProperty(name="Y", default=2160, min=16, max=16384,
                          description="Render height (also sets aspect ratio)",
                          update=_res_update)
    samples: IntProperty(name="Samples", default=128, min=1, soft_max=1024,
                         description="Cycles render samples", update=_samples_update)
    denoiser: EnumProperty(
        name="Denoiser", default='OPTIX', update=_denoise_update,
        items=[('OPTIX', "OptiX", "NVIDIA OptiX AI denoiser (GPU)"),
               ('OPENIMAGEDENOISE', "OpenImageDenoise", "Intel OIDN (CPU/GPU)"),
               ('NONE', "None", "No denoising")])
    use_shadow_catcher: bpy.props.BoolProperty(
        name="Ground Shadow", default=True,
        description="Transparent shadow catcher: the contact shadow composites "
                    "onto any background (green screen, transparent PNG)")
    output_dir: StringProperty(name="Output Folder", subtype='DIR_PATH', default="",
                               description="Where renders are saved "
                                           "(empty = a 'renders' folder next to the .blend)")
    output_base: StringProperty(name="Name", default="shot",
                                description="Base name for saved renders (auto-numbered)")


# --------------------------------------------------------------------------- #
#  Operators
# --------------------------------------------------------------------------- #
class MUTAFORM_OT_res_scale(bpy.types.Operator):
    bl_idname = "mutaform.res_scale"
    bl_label = "Scale Resolution"
    bl_description = "Halve or double the render resolution"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    factor: bpy.props.FloatProperty(default=2.0)

    def execute(self, context):
        r = context.scene.mutaform_render
        r.render_x = max(16, min(16384, int(round(r.render_x * self.factor))))
        r.render_y = max(16, min(16384, int(round(r.render_y * self.factor))))
        return {'FINISHED'}


class MUTAFORM_OT_open_output(bpy.types.Operator):
    bl_idname = "mutaform.open_output"
    bl_label = "Open Folder"
    bl_description = "Open the render output folder in the system file browser"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        d = resolved_output_dir(context.scene)
        os.makedirs(d, exist_ok=True)
        bpy.ops.wm.path_open(filepath=d)
        return {'FINISHED'}


classes = (MutaformRenderProps, MUTAFORM_OT_res_scale, MUTAFORM_OT_open_output)
