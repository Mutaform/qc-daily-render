"""Marmoset-style Color post via the compositor, applied to the saved render.

Blender 5.x: the scene compositor is a node group in scene.compositing_node_group.
Highlights/Midtones/Shadows, Clarity, Contrast, Saturation, Sharpen and Vignette
are all built here.  We do NOT enable the live viewport compositor here (state.py
enables it separately with a guard, since it can be unstable)."""

import bpy

from .. import common as C

COMP_GROUP = C.PREFIX + "Comp"


def _isock(node, identifier):
    return next((s for s in node.inputs if s.identifier == identifier), None)


def _osock(node, identifier):
    return next((s for s in node.outputs if s.identifier == identifier), None)


def _new_rgba_mix(ng, blend):
    m = ng.nodes.new("ShaderNodeMix")
    m.data_type = 'RGBA'
    m.blend_type = blend
    for attr in ("clamp_factor", "clamp_result"):
        if hasattr(m, attr):
            setattr(m, attr, False)
    return m


def build_compositor(scene):
    ng = (bpy.data.node_groups.get(COMP_GROUP)
          or bpy.data.node_groups.new(COMP_GROUP, "CompositorNodeTree"))
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')

    rl = ng.nodes.new("CompositorNodeRLayers")
    cb = ng.nodes.new("CompositorNodeColorBalance")           # highlights/midtones/shadows
    # Clarity's "low-frequency" reference uses an EDGE-AWARE Bilateral Blur, not a
    # plain Gaussian: a plain blur blends across hard seams/silhouettes and makes
    # (cb - blur) swing hugely negative there, crushing to a black outline once
    # added back.  Bilateral only blends pixels whose Determinator is within
    # Threshold, so it stops at real edges - fixing the halo at the root.
    blur = ng.nodes.new("CompositorNodeBilateralblur"); blur.name = C.PREFIX + "Blur"
    sub = _new_rgba_mix(ng, 'SUBTRACT'); sub.name = C.PREFIX + "ClaritySub"
    add = _new_rgba_mix(ng, 'ADD'); add.name = C.PREFIX + "ClarityAdd"
    if hasattr(add, "clamp_result"):
        add.clamp_result = True   # keep the recombined image in 0..1
    # Extra halo guard: clamp the detail signal to [-limit, +limit] before Clarity
    # scales it.  Color sockets clip negatives to 0, so the clamp is done as:
    # shift up by +limit -> floor at 0 -> cap at 2*limit -> shift back down.
    limit_shift = _new_rgba_mix(ng, 'ADD'); limit_shift.name = C.PREFIX + "ClarityLimitShift"
    limit_floor = _new_rgba_mix(ng, 'LIGHTEN'); limit_floor.name = C.PREFIX + "ClarityLimitFloor"
    limit_cap = _new_rgba_mix(ng, 'DARKEN'); limit_cap.name = C.PREFIX + "ClarityLimitCap"
    limit_unshift = _new_rgba_mix(ng, 'SUBTRACT'); limit_unshift.name = C.PREFIX + "ClarityLimitUnshift"
    for n in (limit_shift, limit_floor, limit_cap, limit_unshift):
        _isock(n, "Factor_Float").default_value = 1.0
    con = _new_rgba_mix(ng, 'MIX'); con.name = C.PREFIX + "Contrast"
    hs = ng.nodes.new("CompositorNodeHueSat")                 # saturation
    sblur = ng.nodes.new("CompositorNodeBlur"); sblur.name = C.PREFIX + "SharpBlur"
    ssub = _new_rgba_mix(ng, 'SUBTRACT'); ssub.name = C.PREFIX + "SharpSub"
    sadd = _new_rgba_mix(ng, 'ADD'); sadd.name = C.PREFIX + "SharpAdd"
    if hasattr(sadd, "clamp_result"):
        sadd.clamp_result = True  # same silhouette-edge overshoot guard as clarity
    ell = ng.nodes.new("CompositorNodeEllipseMask"); ell.name = C.PREFIX + "Ellipse"
    mblur = ng.nodes.new("CompositorNodeBlur"); mblur.name = C.PREFIX + "VigBlur"
    vdark = _new_rgba_mix(ng, 'MULTIPLY'); vdark.name = C.PREFIX + "VigDark"
    vmix = _new_rgba_mix(ng, 'MIX'); vmix.name = C.PREFIX + "VigMix"
    go = ng.nodes.new("NodeGroupOutput")
    for i, n in enumerate((rl, cb, blur, sub, add, con, hs, sblur, ssub, sadd,
                           ell, mblur, vdark, vmix, go)):
        n.location = (i * 190, 0)
    for i, n in enumerate((limit_shift, limit_floor, limit_cap, limit_unshift)):
        n.location = (140 + i * 190, -260)

    img = "Image"
    L = ng.links.new
    L(rl.outputs[img], cb.inputs[img])
    # clarity: cb + clamp(cb - bilateral_blur(cb), -limit, +limit) * clarity
    L(cb.outputs[img], blur.inputs[img])
    L(cb.outputs[img], blur.inputs["Determinator"])  # edge test against itself
    L(cb.outputs[img], _isock(sub, "A_Color")); L(blur.outputs[img], _isock(sub, "B_Color"))
    # clamp the raw detail signal to [-limit, +limit]
    L(_osock(sub, "Result_Color"), _isock(limit_shift, "A_Color"))
    L(_osock(limit_shift, "Result_Color"), _isock(limit_floor, "A_Color"))
    L(_osock(limit_floor, "Result_Color"), _isock(limit_cap, "A_Color"))
    L(_osock(limit_cap, "Result_Color"), _isock(limit_unshift, "A_Color"))
    L(cb.outputs[img], _isock(add, "A_Color"))
    L(_osock(limit_unshift, "Result_Color"), _isock(add, "B_Color"))
    # contrast around center
    L(_osock(add, "Result_Color"), _isock(con, "B_Color"))
    # saturation
    L(_osock(con, "Result_Color"), hs.inputs[img])
    # sharpen: hs + (hs - blur(hs))*strength
    L(hs.outputs[img], sblur.inputs[img])
    L(hs.outputs[img], _isock(ssub, "A_Color")); L(sblur.outputs[img], _isock(ssub, "B_Color"))
    L(hs.outputs[img], _isock(sadd, "A_Color")); L(_osock(ssub, "Result_Color"), _isock(sadd, "B_Color"))
    # vignette: darken corners = mix(dark, img, softMask)
    L(ell.outputs["Mask"], mblur.inputs[img])
    L(_osock(sadd, "Result_Color"), _isock(vdark, "A_Color"))
    L(_osock(sadd, "Result_Color"), _isock(vmix, "B_Color"))
    L(_osock(vdark, "Result_Color"), _isock(vmix, "A_Color"))
    L(mblur.outputs[img], _isock(vmix, "Factor_Float"))
    L(_osock(vmix, "Result_Color"), go.inputs[img])

    _isock(sub, "Factor_Float").default_value = 1.0
    _isock(ssub, "Factor_Float").default_value = 1.0
    _isock(vdark, "Factor_Float").default_value = 1.0
    # ellipse: large centred mask (1 inside, 0 at corners)
    for name, val in (("Position", (0.5, 0.5)), ("Size", (0.9, 0.9)), ("Value", 1.0)):
        s = ell.inputs.get(name)
        if s:
            try:
                s.default_value = val
            except Exception:
                pass
    scene.compositing_node_group = ng
    apply_post_params(scene)


def _set_lgg(node, name, v):
    """ColorBalance has duplicate socket names (a float factor + a colour); set
    the colour one."""
    if not node:
        return
    for inp in node.inputs:
        if inp.name != name:
            continue
        try:
            dv = inp.default_value
            if hasattr(dv, "__len__") and len(dv) >= 3:   # the colour socket
                inp.default_value = (v, v, v, 1.0)
                return
        except Exception:
            continue


def _set_blur(node, radius):
    if not node or "Size" not in node.inputs:
        return
    for val in ((radius, radius), radius):
        try:
            node.inputs["Size"].default_value = val
            return
        except Exception:
            continue


def apply_post_params(scene):
    ng = scene.compositing_node_group
    if not ng:
        return
    cam = scene.mutaform_cam
    cb = next((n for n in ng.nodes if n.bl_idname == 'CompositorNodeColorBalance'), None)
    hs = next((n for n in ng.nodes if n.bl_idname == 'CompositorNodeHueSat'), None)
    blur = ng.nodes.get(C.PREFIX + "Blur")
    add = ng.nodes.get(C.PREFIX + "ClarityAdd")
    con = ng.nodes.get(C.PREFIX + "Contrast")

    if cb:
        _set_lgg(cb, "Lift", 1.0 + cam.shadows * 0.30)              # shadows (0 = neutral)
        _set_lgg(cb, "Gamma", max(0.1, 1.0 - cam.midtones * 0.50))  # midtones (0 = neutral)
        _set_lgg(cb, "Gain", 1.0 + (cam.highlights - 0.5) * 0.60)   # highlights (0.5 = neutral)
    if con:                                                         # contrast around center
        a, f = _isock(con, "A_Color"), _isock(con, "Factor_Float")
        c = cam.contrast_center
        if a:
            a.default_value = (c, c, c, 1.0)
        if f:
            f.default_value = cam.contrast                          # 1.0 = neutral
    if add:                                                         # clarity amount
        f = _isock(add, "Factor_Float")
        if f:
            f.default_value = cam.clarity                           # 0 = neutral
    limit_shift = ng.nodes.get(C.PREFIX + "ClarityLimitShift")
    limit_floor = ng.nodes.get(C.PREFIX + "ClarityLimitFloor")
    limit_cap = ng.nodes.get(C.PREFIX + "ClarityLimitCap")
    limit_unshift = ng.nodes.get(C.PREFIX + "ClarityLimitUnshift")
    if limit_shift and limit_floor and limit_cap and limit_unshift:
        # halo-prevention limit: how far Clarity may push any single pixel - fixed,
        # not user-exposed, just enough headroom for normal texture detail.
        L_ = 0.12
        _isock(limit_shift, "B_Color").default_value = (L_, L_, L_, 1.0)
        _isock(limit_floor, "B_Color").default_value = (0.0, 0.0, 0.0, 1.0)
        _isock(limit_cap, "B_Color").default_value = (2 * L_, 2 * L_, 2 * L_, 1.0)
        _isock(limit_unshift, "B_Color").default_value = (L_, L_, L_, 1.0)
    # clarity radius + edge threshold: Bilateral Blur only blends within Threshold,
    # so its Size can be generous without re-introducing the black halo.  Its Size
    # is a scalar int-pixel socket, so set it directly (not via _set_blur's tuple).
    if blur and "Size" in blur.inputs:
        blur.inputs["Size"].default_value = int(round(max(3.0, scene.render.resolution_x * 0.004)))
    if blur and "Threshold" in blur.inputs:
        blur.inputs["Threshold"].default_value = 0.10
    if hs:
        hs.inputs["Saturation"].default_value = cam.saturation      # 1.0 = neutral

    # --- sharpen (unsharp, small radius) ---
    sadd = ng.nodes.get(C.PREFIX + "SharpAdd")
    if sadd:
        f = _isock(sadd, "Factor_Float")
        if f:
            f.default_value = cam.sharpen_strength                  # 0 = off
    _set_blur(ng.nodes.get(C.PREFIX + "SharpBlur"),
              1.0 + cam.sharpen_limit * 4.0)                        # limit -> radius

    # --- vignette (darken corners) ---
    vdark = ng.nodes.get(C.PREFIX + "VigDark")
    if vdark:
        g = 1.0 - cam.vignette_strength
        b = _isock(vdark, "B_Color")
        if b:
            b.default_value = (g, g, g, 1.0)
    _set_blur(ng.nodes.get(C.PREFIX + "VigBlur"),
              max(0.001, cam.vignette_softness) * scene.render.resolution_x * 0.25)


def clear_compositor(scene, restore_group_name=None):
    scene.compositing_node_group = (bpy.data.node_groups.get(restore_group_name)
                                    if restore_group_name else None)
    for ng in [g for g in bpy.data.node_groups if g.name.startswith(C.PREFIX)]:
        try:
            bpy.data.node_groups.remove(ng)
        except Exception:
            pass
