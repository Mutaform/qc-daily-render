"""Camera block: everything that shapes the *image* - the look property group,
the render-frame overlay, and the view-capture render operator.

Re-exports the names the rest of the addon uses so callers can keep doing
`from . import camera` and reach `camera.MutaformCameraProps`,
`camera.enable_overlay()`, `camera.disable_overlay()`."""

from .props import MutaformCameraProps
from .overlay import enable_overlay, disable_overlay, frame_rect
from .capture import MUTAFORM_OT_render, match_camera_to_view
from .ops import MUTAFORM_OT_curves, MUTAFORM_OT_reset_prop

# registration order: the property group first (the Scene PointerProperty needs it)
classes = (MutaformCameraProps, MUTAFORM_OT_render, MUTAFORM_OT_curves,
           MUTAFORM_OT_reset_prop)

__all__ = [
    "MutaformCameraProps", "enable_overlay", "disable_overlay", "frame_rect",
    "MUTAFORM_OT_render", "match_camera_to_view",
    "MUTAFORM_OT_curves", "MUTAFORM_OT_reset_prop", "classes",
]
