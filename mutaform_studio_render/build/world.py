"""HDRI world: lights and reflects the scene, but camera rays see a solid
backplate colour so the viewport preview shows a clean background instead of the
transparency checker.  The final render re-enables transparent film."""

import os

import bpy

from .. import common as C


def get_or_load_image():
    img = bpy.data.images.get(C.IMG_NAME)
    if img is None:
        if not os.path.exists(C.EXR_PATH):
            raise FileNotFoundError("HDRI not found: %s" % C.EXR_PATH)
        img = bpy.data.images.load(C.EXR_PATH)
        img.name = C.IMG_NAME
    img.colorspace_settings.name = 'Non-Color'
    return img


def build_world(scene):
    world = bpy.data.worlds.get(C.WORLD_NAME) or bpy.data.worlds.new(C.WORLD_NAME)
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    env_bg = nt.nodes.new("ShaderNodeBackground"); env_bg.name = "EnvBackground"
    plate_bg = nt.nodes.new("ShaderNodeBackground"); plate_bg.name = "PlateBackground"
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    mapping = nt.nodes.new("ShaderNodeMapping")
    texco = nt.nodes.new("ShaderNodeTexCoord")
    lightpath = nt.nodes.new("ShaderNodeLightPath")
    env.image = get_or_load_image()

    out.location = (600, 0)
    mix.location = (400, 0)
    env_bg.location, plate_bg.location = (200, 120), (200, -120)
    env.location, mapping.location, texco.location = (-40, 160), (-260, 160), (-460, 160)
    lightpath.location = (200, 320)

    link = nt.links.new
    link(texco.outputs["Generated"], mapping.inputs["Vector"])
    link(mapping.outputs["Vector"], env.inputs["Vector"])
    link(env.outputs["Color"], env_bg.inputs["Color"])
    link(lightpath.outputs["Is Camera Ray"], mix.inputs["Fac"])
    link(env_bg.outputs["Background"], mix.inputs[1])    # fac 0 -> lighting/reflections
    link(plate_bg.outputs["Background"], mix.inputs[2])  # fac 1 -> camera sees backplate
    link(mix.outputs["Shader"], out.inputs["Surface"])

    scene.world = world
    apply_world_params(scene)
    return world


def apply_world_params(scene):
    world = bpy.data.worlds.get(C.WORLD_NAME)
    if not world or not world.use_nodes:
        return
    cam = scene.mutaform_cam
    nt = world.node_tree
    env_bg = nt.nodes.get("EnvBackground")
    plate_bg = nt.nodes.get("PlateBackground")
    mapping = next((n for n in nt.nodes if n.type == 'MAPPING'), None)
    if env_bg:
        env_bg.inputs["Strength"].default_value = cam.env_strength
    if plate_bg:
        c = cam.background_color
        plate_bg.inputs["Color"].default_value = (c[0], c[1], c[2], 1.0)
        plate_bg.inputs["Strength"].default_value = 1.0
    if mapping:
        # remembered yaw (not cam.env_yaw, whose getter reads the node)
        mapping.inputs["Rotation"].default_value[2] = cam.get("_env_yaw", C.DEFAULT_ENV_YAW)
