"""Builders for the studio 'look' datablocks (HDRI world, override material,
shadow-catcher ground, wireframe, colour management, compositor).

Each builder is idempotent (safe to call again) and every datablock is
PREFIX-named so restore can sweep it.  The apply_* helpers tweak the look live
without rebuilding node trees.  This package re-exports the whole public API so
callers can keep doing `from . import build; build.build_world(scene)`."""

from .world import get_or_load_image, build_world, apply_world_params
from .material import (
    build_material, record_object_materials, apply_material_mode,
    restore_object_materials, apply_material_params,
)
from .ground import build_shadow_catcher, sync_helper_transforms
from .wireframe import build_wireframe, apply_wireframe_params
from .color import (
    apply_color_management, apply_resolution, apply_quality, CYCLES_ATTRS,
    snapshot_perf, apply_perf, restore_perf,
)
from .compositor import build_compositor, apply_post_params, clear_compositor
from .eevee import (
    apply_eevee_quality, snapshot_eevee, restore_eevee, apply_engine,
)

__all__ = [
    "get_or_load_image", "build_world", "apply_world_params",
    "build_material", "record_object_materials", "apply_material_mode",
    "restore_object_materials", "apply_material_params",
    "build_shadow_catcher", "sync_helper_transforms",
    "build_wireframe", "apply_wireframe_params",
    "apply_color_management", "apply_resolution", "apply_quality", "CYCLES_ATTRS",
    "snapshot_perf", "apply_perf", "restore_perf",
    "build_compositor", "apply_post_params", "clear_compositor",
    "apply_eevee_quality", "snapshot_eevee", "restore_eevee", "apply_engine",
]
