"""Small camera-block operators: toggle the tone curve, and reset a single look
property to its default (the LOOP_BACK button next to each slider)."""

import bpy
from bpy.props import StringProperty

from .. import common as C


class MUTAFORM_OT_curves(bpy.types.Operator):
    bl_idname = "mutaform.curves"
    bl_label = "Curves"
    bl_description = "Toggle the tone curve (edit it in Render Properties > Color Management)"

    def execute(self, context):
        vs = context.scene.view_settings
        vs.use_curve_mapping = not vs.use_curve_mapping
        self.report({'INFO'}, "Tone curve %s - edit in Color Management" %
                    ("ON" if vs.use_curve_mapping else "OFF"))
        return {'FINISHED'}


class MUTAFORM_OT_reset_prop(bpy.types.Operator):
    bl_idname = "mutaform.reset_prop"
    bl_label = "Reset to Default"
    bl_description = "Reset this value to its default"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    prop: StringProperty()

    def execute(self, context):
        cam = context.scene.mutaform_cam
        rna = cam.bl_rna.properties.get(self.prop)
        if rna is None:
            return {'CANCELLED'}
        if getattr(rna, "array_length", 0):
            setattr(cam, self.prop, tuple(rna.default_array))
        else:
            setattr(cam, self.prop, rna.default)
        C.tag_redraw()
        return {'FINISHED'}
