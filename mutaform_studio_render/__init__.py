"""Mutaform Studio Render - non-destructive, Marmoset-style studio render for Blender.

Three top actions in the sidebar (View3D > N > QC Render):
  * Setup Render Scene : snapshot the scene, then apply the studio setup (HDRI
    world, single override material, shadow-catcher floor, transparent film,
    Cycles) and turn the viewport into a live preview with a render-frame guide.
    You keep navigating the normal viewport.
  * Render             : place a camera on the current view, render exactly what
    you framed, save an auto-numbered PNG, then remove the camera.
  * Restore            : put the scene back exactly as it was.

Module map:
  common.py       constants + shared helpers
  build/          the look: world, material, ground, wireframe, colour, compositor
  state.py        snapshot / apply / restore (the non-destructive engine)
  camera/         image block: look props, frame-guide overlay, view capture
  render.py       technical block: resolution, samples, denoiser, output paths
  operators.py    Setup / Restore operators
  ui.py           sidebar panel
"""

import bpy

from . import common, build, render, camera, state, operators, ui

bl_info = {
    "name": "Mutaform Studio Render",
    "author": "Mutaform",
    "version": common.VERSION,
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > QC Render",
    "description": "One-click non-destructive Marmoset-style studio render.",
    "category": "Render",
}

# modules that expose a `classes` tuple to (un)register
_modules = (render, camera, operators, ui)


def _all_classes():
    for m in _modules:
        for cls in getattr(m, "classes", ()):
            yield cls


def register():
    for cls in _all_classes():
        bpy.utils.register_class(cls)
    bpy.types.Scene.mutaform_cam = bpy.props.PointerProperty(type=camera.MutaformCameraProps)
    bpy.types.Scene.mutaform_render = bpy.props.PointerProperty(type=render.MutaformRenderProps)
    bpy.types.Scene.mutaform_tab = bpy.props.EnumProperty(
        name="Tab", default='CAMERA', items=ui.TAB_ITEMS)


def unregister():
    camera.disable_overlay()
    del bpy.types.Scene.mutaform_tab
    del bpy.types.Scene.mutaform_render
    del bpy.types.Scene.mutaform_cam
    for cls in reversed(list(_all_classes())):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
