"""Colour management, output resolution and Cycles quality (samples, adaptive
sampling, denoiser)."""

import math

import bpy

from .. import common as C

# Marmoset "Tone Mapping" -> Blender view transform
_TONE_MAP = {'Linear': 'Standard', 'Filmic': 'Filmic', 'AgX': 'AgX',
             'PBR': 'Khronos PBR Neutral'}

# Cycles attributes we touch (for snapshot/restore).
CYCLES_ATTRS = (
    "samples", "preview_samples", "device", "use_denoising", "denoiser",
    "denoising_input_passes", "denoising_prefilter", "denoising_use_gpu",
    "use_preview_denoising", "preview_denoiser", "preview_denoising_input_passes",
    "preview_denoising_start_sample", "preview_denoising_prefilter",
    "use_adaptive_sampling", "adaptive_threshold",
    "use_preview_adaptive_sampling", "preview_adaptive_threshold", "max_bounces",
)


def _set(obj, attr, value):
    try:
        setattr(obj, attr, value)
    except Exception:
        pass


def _cycles_prefs():
    return bpy.context.preferences.addons["cycles"].preferences


def snapshot_perf(scene):
    """Record the user's compute-device prefs + persistent-data flag so Restore
    can put them back exactly (prefs are global, not part of the scene)."""
    perf = {"persistent": scene.render.use_persistent_data}
    try:
        cprefs = _cycles_prefs()
        perf["cdt"] = cprefs.compute_device_type
        perf["devices"] = [[d.name, d.type, d.use] for d in cprefs.devices]
    except Exception:
        pass
    return perf


def apply_perf(scene):
    """Fastest safe compute config for THIS machine (benchmarked ~2x on RTX):
    best available backend, every GPU of that backend on, CPU off (hybrid
    CPU+GPU drags a fast GPU down), persistent data on (skips scene rebuild
    between renders).  Returns the chosen backend, or None = CPU-only box
    (prefs left untouched there)."""
    scene.render.use_persistent_data = True
    try:
        cprefs = _cycles_prefs()
        gpus = {}
        for d in cprefs.devices:
            if d.type != 'CPU':
                gpus.setdefault(d.type, set()).add(d.name)
        for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
            if gpus.get(backend):
                cprefs.compute_device_type = backend
                for d in cprefs.devices:
                    d.use = (d.type == backend)
                return backend
    except Exception:
        pass
    return None


def restore_perf(scene, perf):
    if not perf:
        return
    _set(scene.render, "use_persistent_data", perf.get("persistent", False))
    try:
        cprefs = _cycles_prefs()
        if perf.get("cdt") is not None:
            cprefs.compute_device_type = perf["cdt"]
        for d in cprefs.devices:
            for (n, t, u) in perf.get("devices") or []:
                if d.name == n and d.type == t:
                    d.use = u
                    break
    except Exception:
        pass


def _has_gpu():
    try:
        return any(d.use and d.type != 'CPU' for d in _cycles_prefs().devices)
    except Exception:
        return True   # assume GPU; Cycles falls back to CPU on its own


def apply_color_management(scene):
    cam = scene.mutaform_cam
    vs = scene.view_settings
    try:
        vs.view_transform = _TONE_MAP.get(cam.tone_mapping, 'Standard')
        vs.look = 'None'
        vs.exposure = math.log2(max(cam.exposure, 1e-3))   # multiplier -> EV stops
        vs.gamma = 1.0
    except Exception:
        pass


def apply_resolution(scene):
    r = scene.mutaform_render
    scene.render.resolution_x = r.render_x
    scene.render.resolution_y = r.render_y
    scene.render.resolution_percentage = 100


def apply_quality(scene):
    """Clean, fast defaults: denoise the final render (OptiX, GPU) with adaptive
    sampling.  Viewport denoise is off by default so the artist sees the true
    render noise in the preview."""
    cy = scene.cycles
    r = scene.mutaform_render
    cy.device = 'GPU' if _has_gpu() else 'CPU'
    cy.samples = r.samples
    # adaptive sampling -> converge fast, stop early where clean
    _set(cy, "use_adaptive_sampling", True)
    _set(cy, "adaptive_threshold", 0.01)
    _set(cy, "use_preview_adaptive_sampling", True)
    _set(cy, "preview_adaptive_threshold", 0.05)
    _set(cy, "preview_samples", 256)
    # final denoise
    cy.use_denoising = (r.denoiser != 'NONE')
    if r.denoiser != 'NONE':
        _set(cy, "denoiser", r.denoiser)
    _set(cy, "denoising_input_passes", 'RGB_ALBEDO_NORMAL')
    _set(cy, "denoising_use_gpu", True)
    # viewport denoise OFF by default; settings kept ready in case it is toggled on
    _set(cy, "use_preview_denoising", False)
    _set(cy, "preview_denoiser", 'OPTIX')
    _set(cy, "preview_denoising_input_passes", 'RGB_ALBEDO_NORMAL')
    _set(cy, "preview_denoising_start_sample", 1)
