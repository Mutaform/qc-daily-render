"""EEVEE (Next) render support.

The studio scene is built for Cycles.  Switching the engine to EEVEE reuses the
exact same look (HDRI world, materials, post compositor, wireframe, frame) but
renders it through EEVEE using the saved EEVEE_DEFAULTS preset (a fast alternative).

Two EEVEE limitations are handled here:
  * EEVEE ignores Cycles' is_shadow_catcher, so the ground plane would render as a
    solid lit floor - we hide it for the EEVEE render (model floats on the
    transparent background; the contact shadow stays a Cycles-only feature).
  * The EEVEE settings we raise for quality are snapshotted and restored so that
    exiting the studio leaves the scene clean.
"""

import bpy

from .. import common as C

# The EEVEE preset the addon applies when the engine is switched to EEVEE.
# Captured from denis's tuned scene (2026-08-02) as the saved defaults - re-run
# scratchpad/py_dump_eevee.py while the studio is active in EEVEE to refresh these.
EEVEE_DEFAULTS = {
    # sampling
    "taa_render_samples": 1024,
    "taa_samples": 256,
    "use_taa_reprojection": True,
    # shadows
    "use_shadows": True,
    "shadow_ray_count": 4,
    "shadow_step_count": 16,
    "shadow_resolution_scale": 1.0,
    "shadow_pool_size": "512",
    # ray tracing (reflections / refraction)
    "use_raytracing": True,
    "ray_tracing_method": "SCREEN",
    # fast GI (ambient) - off, matching the saved scene
    "use_fast_gi": False,
    "fast_gi_method": "GLOBAL_ILLUMINATION",
    "fast_gi_resolution": "2",
    "fast_gi_ray_count": 4,
    "fast_gi_step_count": 16,
    "fast_gi_quality": 1.0,
    "fast_gi_distance": 0.0,
    "fast_gi_thickness_near": 0.25,
    "fast_gi_bias": 0.05,
    # global illumination / probes
    "gi_diffuse_bounces": 8,
    "gi_cubemap_resolution": "512",
    "gi_visibility_resolution": "32",
    "gi_irradiance_pool_size": "16",
    "gi_glossy_clamp": 0.0,
    # clamps / light
    "clamp_surface_direct": 0.0,
    "clamp_surface_indirect": 10.0,
    "clamp_volume_direct": 0.0,
    "clamp_volume_indirect": 0.0,
    "light_threshold": 0.01,
    "direct_light_intensity": 1.0,
    "indirect_light_intensity": 1.0,
    # volumetrics (quality only; scene-scale ranges left untouched)
    "use_volumetric_shadows": True,
    "volumetric_samples": 64,
    "volumetric_shadow_samples": 16,
    "volumetric_ray_depth": 16,
    "volumetric_sample_distribution": 0.8,
    "volumetric_light_clamp": 0.0,
}
EEVEE_RTO_DEFAULTS = {
    "resolution_scale": "1",
    "use_backface_hit": False,
    "backface_radiance_scale": 0.0,
    "use_denoise": False,
    "denoise_spatial": True,
    "denoise_temporal": True,
    "denoise_bilateral": True,
    "screen_trace_thickness": 0.2,
    "trace_max_roughness": 1.0,
    "screen_trace_quality": 1.0,
}
# snapshot/restore exactly the keys the preset changes, so exiting the studio
# restores the artist's own EEVEE config
EEVEE_ATTRS = tuple(EEVEE_DEFAULTS)
RTO_ATTRS = tuple(EEVEE_RTO_DEFAULTS)


def _set(obj, attr, value):
    try:
        setattr(obj, attr, value)
    except Exception:
        pass


def snapshot_eevee(scene):
    ee = scene.eevee
    snap = {a: getattr(ee, a) for a in EEVEE_ATTRS if hasattr(ee, a)}
    rto = getattr(ee, "ray_tracing_options", None)
    if rto:
        snap["_rto"] = {a: getattr(rto, a) for a in RTO_ATTRS if hasattr(rto, a)}
    return snap


def restore_eevee(scene, snap):
    ee = scene.eevee
    for a, v in snap.items():
        if a == "_rto":
            continue
        _set(ee, a, v)
    rto = getattr(ee, "ray_tracing_options", None)
    if rto and "_rto" in snap:
        for a, v in snap["_rto"].items():
            _set(rto, a, v)


def apply_eevee_quality(scene):
    """Apply the saved EEVEE preset (EEVEE_DEFAULTS)."""
    ee = scene.eevee
    for attr, value in EEVEE_DEFAULTS.items():
        _set(ee, attr, value)
    rto = getattr(ee, "ray_tracing_options", None)
    if rto:
        for attr, value in EEVEE_RTO_DEFAULTS.items():
            _set(rto, attr, value)


def apply_engine(scene):
    """Set the live studio engine to mutaform_render.preview_engine, apply that
    engine's quality, and show/hide the shadow catcher accordingly - so the
    viewport preview matches the saved render (EEVEE can't do the shadow catcher,
    so its floor is hidden in both preview and render)."""
    from . import color   # local import: avoid a build.* import cycle at module load
    r = scene.mutaform_render
    eevee = (r.preview_engine == 'BLENDER_EEVEE')
    scene.render.engine = r.preview_engine
    floor = bpy.data.objects.get(C.FLOOR_NAME)
    if eevee:
        apply_eevee_quality(scene)
        if floor:
            floor.hide_render = floor.hide_viewport = True
    else:
        color.apply_quality(scene)
        if floor:
            floor.hide_render = floor.hide_viewport = False
