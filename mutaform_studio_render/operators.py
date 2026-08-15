"""The two top-level actions: Setup Render Scene and Restore."""

import os
import bpy

from . import common as C
from . import render as render_mod
from . import state


class MUTAFORM_OT_setup(bpy.types.Operator):
    bl_idname = "mutaform.studio_setup"
    bl_label = "Setup Render Scene"
    bl_description = "Snapshot the scene, then apply the studio render setup (non-destructive)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        if C.is_active(scene):
            self.report({'WARNING'}, "Studio setup already active. Restore first.")
            return {'CANCELLED'}
        if not os.path.exists(C.EXR_PATH):
            self.report({'ERROR'}, "HDRI missing: %s" % C.EXR_PATH)
            return {'CANCELLED'}
        render_mod.ensure_denoiser_supported(scene)
        state.apply_studio(context, scene)
        self.report({'INFO'}, "Studio render setup applied.")
        return {'FINISHED'}


class MUTAFORM_OT_restore(bpy.types.Operator):
    bl_idname = "mutaform.studio_restore"
    bl_label = "Restore"
    bl_description = "Revert everything to the pre-setup state and remove all added objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, msg = state.restore(context, context.scene)
        self.report({'INFO'} if ok else {'WARNING'}, msg)
        return {'FINISHED'} if ok else {'CANCELLED'}


classes = (MUTAFORM_OT_setup, MUTAFORM_OT_restore)
