#!/usr/bin/env python3
"""
Cinematic PBR material renderer using Blender + Cycles.

Renders a moody light-sweep reveal of a PBR material on a displaced plane.
Designed for Patina materials but works with any PBR map set.

Usage:
    blender --background --python render_material.py -- \
        --basecolor ./maps/basecolor.png \
        --normal ./maps/normal.png \
        --roughness ./maps/roughness.png \
        --metalness ./maps/metalness.png \
        --height ./maps/height.png \
        --output ./renders/material_showcase \
        --frames 180 \
        --resolution 3840 2160

    # Batch mode — render multiple materials:
    blender --background --python render_material.py -- \
        --batch ./materials_dir/ \
        --output ./renders/ \
        --frames 180

Requirements:
    - Blender 3.6+ (tested with 4.x)
    - GPU recommended (CUDA/OptiX/HIP)
    - Optional: HDRI file for environment reflections
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import bpy  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Camera
DEFAULT_RESOLUTION = (3840, 2160)
DEFAULT_FRAMES = 180  # 6 seconds at 30fps
DEFAULT_FPS = 30
DOF_FSTOP = 2.8

# Camera motion presets — each defines a different cinematic feel
# All distances/angles are starting values; animation interpolates from start→end
CAMERA_PRESETS = {
    "drift": {
        # Original gentle drift — subtle, contemplative
        "description": "Gentle forward drift with slight lateral sway",
        "distance_start": 1.8,
        "distance_end": 1.65,
        "angle_start": 55,  # degrees from horizontal
        "angle_end": 53,
        "orbit_start": 0,  # degrees around Y axis
        "orbit_end": 8,
        "lens": 85,
    },
    "orbit": {
        # Slow orbit — reveals material from multiple angles
        "description": "Slow orbit showing material from different angles",
        "distance_start": 1.6,
        "distance_end": 1.6,
        "angle_start": 50,
        "angle_end": 55,
        "orbit_start": -20,
        "orbit_end": 20,
        "lens": 85,
    },
    "push-in": {
        # Dramatic push toward surface — reveals micro detail
        "description": "Push in from wide to macro, revealing fine detail",
        "distance_start": 2.2,
        "distance_end": 1.2,
        "angle_start": 50,
        "angle_end": 60,
        "orbit_start": -5,
        "orbit_end": 5,
        "lens": 100,
    },
    "glide": {
        # Lateral glide across the surface — cinematic tracking shot feel
        "description": "Lateral glide across the surface at oblique angle",
        "distance_start": 1.5,
        "distance_end": 1.5,
        "angle_start": 65,
        "angle_end": 60,
        "orbit_start": -30,
        "orbit_end": 30,
        "lens": 70,
    },
    "reveal": {
        # Start close and oblique, pull back to reveal — dramatic opening
        "description": "Start tight at oblique angle, pull back to reveal",
        "distance_start": 1.0,
        "distance_end": 2.0,
        "angle_start": 70,
        "angle_end": 45,
        "orbit_start": 15,
        "orbit_end": -10,
        "lens": 65,
    },
}
DEFAULT_CAMERA_PRESET = "drift"

# Lighting — dramatic sweep
SWEEP_LIGHT_ENERGY = 500
SWEEP_LIGHT_SPOT_SIZE_DEG = 65  # wider cone — rich gradient from center to edges
SWEEP_LIGHT_SPOT_BLEND = 0.7  # smooth falloff for that gorgeous gradient
SWEEP_LIGHT_HEIGHT = 1.8
SWEEP_LIGHT_RADIUS = 2.5  # orbit radius
SWEEP_ARC_START_DEG = -70  # start position (off to the side)
SWEEP_ARC_END_DEG = 70  # end position
SWEEP_LIGHT_COLOR = (1.0, 0.95, 0.88)  # warm white

# Fill — barely there, just lifts black areas enough to hint at surface
FILL_LIGHT_ENERGY = 3
FILL_LIGHT_COLOR = (0.6, 0.7, 1.0)  # cool blue tint

# Rim — subtle edge definition
RIM_LIGHT_ENERGY = 5
RIM_LIGHT_COLOR = (0.85, 0.9, 1.0)

# Material plane
PLANE_SIZE = 2.0
PLANE_SUBDIVISIONS = 512  # for displacement quality
DISPLACEMENT_SCALE = 0.08
DISPLACEMENT_MIDLEVEL = 0.5
NORMAL_STRENGTH = 1.0
TEXTURE_REPEAT = 2.0  # how many times the texture tiles

# Render
RENDER_SAMPLES = 512
DENOISER = "OPENIMAGEDENOISE"  # or "OPTIX" if available
FILM_EXPOSURE = 0.65  # dark but readable — gradient does the drama
WORLD_STRENGTH = 0.003  # near-zero ambient — darkness is the default state


# ---------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------


def clear_scene() -> None:
    """Remove all default objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Clear orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)


def setup_render_settings(
    resolution: tuple[int, int],
    frames: int,
    fps: int,
    output_path: str,
    samples: int = RENDER_SAMPLES,
) -> None:
    """Configure Cycles render settings for maximum quality."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"

    # Device — prefer GPU
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.refresh_devices()

    # Try GPU compute devices in order of preference
    for compute_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = compute_type
            prefs.refresh_devices()
            devices = prefs.get_devices_for_type(compute_type)
            if devices:
                for d in devices:
                    d.use = True
                scene.cycles.device = "GPU"
                print(f"Render device: {compute_type} ({len(devices)} device(s))")
                break
        except Exception:
            continue
    else:
        scene.cycles.device = "CPU"
        print("Render device: CPU (no GPU found)")

    # Quality
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = DENOISER
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.005

    # Film
    scene.render.film_transparent = False
    scene.view_settings.exposure = FILM_EXPOSURE
    scene.view_settings.view_transform = "AgX"  # Blender 4.x, fallback below
    scene.view_settings.look = "None"

    # Resolution
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100

    # Frame range
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.fps = fps

    # Output
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "16"

    # Performance
    scene.render.use_persistent_data = True
    scene.cycles.max_bounces = 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 8
    scene.cycles.volume_bounces = 0
    scene.cycles.transparent_max_bounces = 8


def create_world(hdri_path: str | None = None) -> None:
    """Create a near-black world with optional HDRI for reflections."""
    world = bpy.data.worlds.new("MaterialShowcase")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (400, 0)

    if hdri_path and os.path.exists(hdri_path):
        # HDRI environment — very dim, just for reflections
        env_tex = nodes.new("ShaderNodeTexEnvironment")
        env_tex.location = (-400, 0)
        env_tex.image = bpy.data.images.load(hdri_path)

        bg = nodes.new("ShaderNodeBackground")
        bg.location = (0, 0)
        bg.inputs["Strength"].default_value = WORLD_STRENGTH

        links.new(env_tex.outputs["Color"], bg.inputs["Color"])
        links.new(bg.outputs["Background"], output.inputs["Surface"])
    else:
        # Solid very dark gray — not pure black (allows subtle ambient)
        bg = nodes.new("ShaderNodeBackground")
        bg.location = (0, 0)
        bg.inputs["Color"].default_value = (0.002, 0.002, 0.003, 1.0)
        bg.inputs["Strength"].default_value = WORLD_STRENGTH
        links.new(bg.outputs["Background"], output.inputs["Surface"])


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def create_material_plane(
    subdivisions: int = PLANE_SUBDIVISIONS,
) -> bpy.types.Object:
    """Create a subdivided plane for material display with displacement."""
    bpy.ops.mesh.primitive_plane_add(size=PLANE_SIZE, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "MaterialPlane"

    # Subdivision surface for adaptive displacement
    subsurf = plane.modifiers.new("Subdivision", "SUBSURF")
    subsurf.subdivision_type = "SIMPLE"
    subsurf.levels = 0  # viewport
    subsurf.render_levels = 6  # render — adaptive will handle actual level
    subsurf.use_limit_surface = True

    # Enable adaptive subdivision (Cycles experimental)
    bpy.context.scene.cycles.feature_set = "EXPERIMENTAL"
    plane.cycles.use_adaptive_subdivision = True
    plane.cycles.dicing_rate = 0.5  # fine tessellation

    # Smooth shading
    bpy.ops.object.shade_smooth()

    return plane


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------


def create_pbr_material(
    paths: dict[str, str],
    name: str = "CinematicPBR",
    texture_repeat: float = TEXTURE_REPEAT,
    displacement_scale: float = DISPLACEMENT_SCALE,
    normal_strength: float = NORMAL_STRENGTH,
) -> bpy.types.Material:
    """Build a full PBR material with proper node graph."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    # ── Shared texture coordinate + mapping ────────────────────────
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-1200, 0)

    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-1000, 0)
    mapping.inputs["Scale"].default_value = (texture_repeat, texture_repeat, 1.0)
    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    # ── Output ─────────────────────────────────────────────────────
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (600, 0)

    # ── Principled BSDF ────────────────────────────────────────────
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (200, 0)
    # Physical material properties for better realism
    principled.inputs["IOR"].default_value = 1.45
    principled.inputs["Coat Weight"].default_value = 0.0  # Blender 4.x
    principled.inputs["Specular IOR Level"].default_value = 0.5
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # ── Base Color ─────────────────────────────────────────────────
    if "basecolor" in paths:
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-600, 300)
        tex.image = bpy.data.images.load(paths["basecolor"])
        tex.image.name = f"{name}_basecolor"
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], principled.inputs["Base Color"])

    # ── Roughness ──────────────────────────────────────────────────
    if "roughness" in paths:
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-600, 50)
        tex.image = bpy.data.images.load(paths["roughness"])
        tex.image.name = f"{name}_roughness"
        tex.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], principled.inputs["Roughness"])

    # ── Metalness ──────────────────────────────────────────────────
    if "metalness" in paths:
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-600, -200)
        tex.image = bpy.data.images.load(paths["metalness"])
        tex.image.name = f"{name}_metalness"
        tex.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        links.new(tex.outputs["Color"], principled.inputs["Metallic"])

    # ── Normal Map ─────────────────────────────────────────────────
    if "normal" in paths:
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-900, -400)
        tex.image = bpy.data.images.load(paths["normal"])
        tex.image.name = f"{name}_normal"
        tex.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])

        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-600, -400)
        normal_map.inputs["Strength"].default_value = normal_strength
        links.new(tex.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

    # ── Height → Displacement ──────────────────────────────────────
    if "height" in paths:
        tex = nodes.new("ShaderNodeTexImage")
        tex.location = (-900, -650)
        tex.image = bpy.data.images.load(paths["height"])
        tex.image.name = f"{name}_height"
        tex.image.colorspace_settings.name = "Non-Color"
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])

        disp = nodes.new("ShaderNodeDisplacement")
        disp.location = (200, -400)
        disp.inputs["Scale"].default_value = displacement_scale
        disp.inputs["Midlevel"].default_value = DISPLACEMENT_MIDLEVEL
        links.new(tex.outputs["Color"], disp.inputs["Height"])
        links.new(disp.outputs["Displacement"], output.inputs["Displacement"])

        mat.cycles.displacement_method = "BOTH"  # true displacement + bump
    else:
        mat.cycles.displacement_method = "BUMP"

    return mat


# ---------------------------------------------------------------------------
# Lighting
# ---------------------------------------------------------------------------


def create_sweep_light(frames: int) -> bpy.types.Object:
    """Create a spot light that sweeps a tight pool across the material."""
    bpy.ops.object.light_add(type="SPOT", location=(0, 0, SWEEP_LIGHT_HEIGHT))
    light = bpy.context.active_object
    light.name = "SweepLight"
    light.data.name = "SweepLight"
    light.data.energy = SWEEP_LIGHT_ENERGY
    light.data.spot_size = math.radians(SWEEP_LIGHT_SPOT_SIZE_DEG)
    light.data.spot_blend = SWEEP_LIGHT_SPOT_BLEND
    light.data.shadow_soft_size = 0.15  # small source = sharp shadows on displacement
    light.data.color = SWEEP_LIGHT_COLOR
    light.data.cycles.use_multiple_importance_sampling = True

    # Animate sweep: arc from one side to the other
    for frame_i in range(frames + 1):
        t = frame_i / frames
        # Ease in/out for smooth motion
        t_ease = _ease_in_out(t)
        angle = math.radians(
            SWEEP_ARC_START_DEG + (SWEEP_ARC_END_DEG - SWEEP_ARC_START_DEG) * t_ease
        )

        x = SWEEP_LIGHT_RADIUS * math.sin(angle)
        y = -SWEEP_LIGHT_RADIUS * math.cos(angle)
        z = SWEEP_LIGHT_HEIGHT

        light.location = (x, y, z)
        light.keyframe_insert(data_path="location", frame=frame_i + 1)

        # Light always points at center of plane
        direction = (-x, -y, -z)
        rot = _direction_to_euler(direction)
        light.rotation_euler = rot
        light.keyframe_insert(data_path="rotation_euler", frame=frame_i + 1)

    # Smooth keyframe interpolation
    _smooth_fcurves(light)

    return light


def create_fill_light() -> bpy.types.Object:
    """Create a very subtle fill light from above — atmosphere only."""
    bpy.ops.object.light_add(type="AREA", location=(0, 0, 3.0))
    light = bpy.context.active_object
    light.name = "FillLight"
    light.data.name = "FillLight"
    light.data.energy = FILL_LIGHT_ENERGY
    light.data.size = 3.0  # large, soft
    light.data.color = FILL_LIGHT_COLOR
    light.rotation_euler = (0, 0, 0)  # pointing straight down
    return light


def create_rim_light() -> bpy.types.Object:
    """Create a subtle backlight for edge definition."""
    bpy.ops.object.light_add(type="AREA", location=(0, 2.5, 1.0))
    light = bpy.context.active_object
    light.name = "RimLight"
    light.data.name = "RimLight"
    light.data.energy = RIM_LIGHT_ENERGY
    light.data.size = 2.0
    light.data.color = RIM_LIGHT_COLOR
    # Point toward plane center
    light.rotation_euler = _direction_to_euler((0, -2.5, -1.0))
    return light


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------


def create_camera(
    frames: int,
    preset: str = DEFAULT_CAMERA_PRESET,
) -> bpy.types.Object:
    """Create camera with preset-driven cinematic motion and shallow DOF."""
    p = CAMERA_PRESETS[preset]
    print(f"  Camera preset: {preset} — {p['description']}")

    # Start position
    angle_s = math.radians(p["angle_start"])
    orbit_s = math.radians(p["orbit_start"])
    dist_s = p["distance_start"]

    cam_x = dist_s * math.cos(angle_s) * math.sin(orbit_s)
    cam_y = -dist_s * math.cos(angle_s) * math.cos(orbit_s)
    cam_z = dist_s * math.sin(angle_s)

    bpy.ops.object.camera_add(location=(cam_x, cam_y, cam_z))
    cam = bpy.context.active_object
    cam.name = "ShowcaseCamera"
    bpy.context.scene.camera = cam

    # Track constraint — always look at plane center
    focus_target = _get_or_create_empty(
        "CameraTarget", (0, 0, DISPLACEMENT_SCALE * 0.25)
    )
    track = cam.constraints.new("TRACK_TO")
    track.target = focus_target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    # DOF — use focus object so distance updates automatically as camera moves
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus_target
    cam.data.dof.aperture_fstop = DOF_FSTOP

    # Lens
    cam.data.lens = p["lens"]
    cam.data.sensor_width = 36  # full frame

    # Animate — interpolate all parameters from start to end
    for frame_i in range(frames + 1):
        t = frame_i / frames
        t_ease = _ease_in_out(t)

        dist = p["distance_start"] + (p["distance_end"] - p["distance_start"]) * t_ease
        angle = math.radians(
            p["angle_start"] + (p["angle_end"] - p["angle_start"]) * t_ease
        )
        orbit = math.radians(
            p["orbit_start"] + (p["orbit_end"] - p["orbit_start"]) * t_ease
        )

        x = dist * math.cos(angle) * math.sin(orbit)
        y = -dist * math.cos(angle) * math.cos(orbit)
        z = dist * math.sin(angle)

        cam.location = (x, y, z)
        cam.keyframe_insert(data_path="location", frame=frame_i + 1)

    _smooth_fcurves(cam)

    return cam


def _get_or_create_empty(
    name: str, location: tuple[float, float, float]
) -> bpy.types.Object:
    """Get or create an empty object as a tracking target."""
    empty = bpy.data.objects.get(name)
    if not empty:
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)
        empty = bpy.context.active_object
        empty.name = name
    return empty


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _ease_in_out(t: float) -> float:
    """Smooth ease-in-out curve (cubic)."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def _direction_to_euler(
    direction: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Convert a direction vector to Euler rotation (XYZ)."""
    import mathutils  # type: ignore[import-not-found]

    vec = mathutils.Vector(direction).normalized()
    # Point -Z axis along direction (Blender convention for lights/cameras)
    quat = vec.to_track_quat("-Z", "Y")
    return quat.to_euler("XYZ")


def _smooth_fcurves(obj: bpy.types.Object) -> None:
    """Set all keyframes to smooth interpolation."""
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def find_pbr_maps(directory: str) -> dict[str, str]:
    """Auto-detect PBR maps in a directory by filename convention."""
    maps: dict[str, str] = {}
    map_names = ("basecolor", "normal", "roughness", "metalness", "height")
    # Also check common aliases
    aliases = {
        "base_color": "basecolor",
        "albedo": "basecolor",
        "diffuse": "basecolor",
        "color": "basecolor",
        "rough": "roughness",
        "metal": "metalness",
        "metallic": "metalness",
        "displacement": "height",
        "disp": "height",
        "bump": "height",
        "norm": "normal",
    }

    for f in os.listdir(directory):
        f_lower = f.lower()
        # Check exact map names
        for name in map_names:
            if name in f_lower and f_lower.endswith(
                (".png", ".jpg", ".jpeg", ".exr", ".tiff", ".tif")
            ):
                maps[name] = os.path.join(directory, f)
                break
        else:
            # Check aliases
            for alias, canonical in aliases.items():
                if alias in f_lower and f_lower.endswith(
                    (".png", ".jpg", ".jpeg", ".exr", ".tiff", ".tif")
                ):
                    if canonical not in maps:  # don't override exact match
                        maps[canonical] = os.path.join(directory, f)
                    break

    return maps


def build_scene(
    pbr_paths: dict[str, str],
    material_name: str = "CinematicPBR",
    hdri_path: str | None = None,
    frames: int = DEFAULT_FRAMES,
    resolution: tuple[int, int] = DEFAULT_RESOLUTION,
    fps: int = DEFAULT_FPS,
    output_path: str = "/tmp/render_",
    samples: int = RENDER_SAMPLES,
    displacement_scale: float = DISPLACEMENT_SCALE,
    normal_strength: float = NORMAL_STRENGTH,
    texture_repeat: float = TEXTURE_REPEAT,
    camera_preset: str = DEFAULT_CAMERA_PRESET,
) -> None:
    """Build the complete cinematic scene."""
    print(f"Building scene: {material_name}")
    print(f"  Maps: {list(pbr_paths.keys())}")
    print(f"  Resolution: {resolution[0]}x{resolution[1]}")
    print(f"  Frames: {frames} ({frames / fps:.1f}s at {fps}fps)")
    print(f"  Camera: {camera_preset}")
    print(f"  Output: {output_path}")

    clear_scene()
    setup_render_settings(resolution, frames, fps, output_path, samples)
    create_world(hdri_path)

    # Geometry
    plane = create_material_plane()

    # Material
    mat = create_pbr_material(
        pbr_paths,
        name=material_name,
        texture_repeat=texture_repeat,
        displacement_scale=displacement_scale,
        normal_strength=normal_strength,
    )
    if plane.data.materials:
        plane.data.materials[0] = mat
    else:
        plane.data.materials.append(mat)

    # Lighting
    create_sweep_light(frames)
    create_fill_light()
    create_rim_light()

    # Camera
    create_camera(frames, preset=camera_preset)

    print("Scene built successfully!")


def render_animation() -> None:
    """Render the full animation."""
    print("Starting render...")
    bpy.ops.render.render(animation=True)
    print("Render complete!")


def render_still(frame: int = -1) -> None:
    """Render a single frame (useful for preview)."""
    if frame > 0:
        bpy.context.scene.frame_set(frame)
    else:
        # Render at the dramatic peak — when light is centered
        mid = (bpy.context.scene.frame_start + bpy.context.scene.frame_end) // 2
        bpy.context.scene.frame_set(mid)
    print(f"Rendering frame {bpy.context.scene.frame_current}...")
    bpy.ops.render.render(write_still=True)
    print("Still render complete!")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments (after Blender's --)."""
    # Find args after --
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Cinematic PBR material renderer")

    # Input — individual maps
    parser.add_argument("--basecolor", type=str, help="Path to basecolor map")
    parser.add_argument("--normal", type=str, help="Path to normal map")
    parser.add_argument("--roughness", type=str, help="Path to roughness map")
    parser.add_argument("--metalness", type=str, help="Path to metalness map")
    parser.add_argument("--height", type=str, help="Path to height/displacement map")

    # Input — directory auto-detect
    parser.add_argument(
        "--maps-dir",
        type=str,
        help="Directory containing PBR maps (auto-detected by name)",
    )

    # Input — batch mode
    parser.add_argument(
        "--batch",
        type=str,
        help="Directory of material directories (each rendered separately)",
    )

    # Scene
    parser.add_argument(
        "--name", type=str, default="CinematicPBR", help="Material name"
    )
    parser.add_argument("--hdri", type=str, help="HDRI environment map for reflections")
    parser.add_argument(
        "--displacement-scale",
        type=float,
        default=DISPLACEMENT_SCALE,
        help=f"Height displacement scale (default: {DISPLACEMENT_SCALE})",
    )
    parser.add_argument(
        "--normal-strength",
        type=float,
        default=NORMAL_STRENGTH,
        help=f"Normal map strength (default: {NORMAL_STRENGTH})",
    )
    parser.add_argument(
        "--texture-repeat",
        type=float,
        default=TEXTURE_REPEAT,
        help=f"Texture tiling repeat (default: {TEXTURE_REPEAT})",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/material_render_",
        help="Output path prefix (frames saved as prefix0001.png etc)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        nargs=2,
        default=list(DEFAULT_RESOLUTION),
        metavar=("W", "H"),
        help=f"Resolution (default: {DEFAULT_RESOLUTION[0]} {DEFAULT_RESOLUTION[1]})",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=DEFAULT_FRAMES,
        help=f"Number of frames (default: {DEFAULT_FRAMES})",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=f"Frames per second (default: {DEFAULT_FPS})",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=RENDER_SAMPLES,
        help=f"Render samples (default: {RENDER_SAMPLES})",
    )

    # Camera
    preset_names = list(CAMERA_PRESETS.keys())
    parser.add_argument(
        "--camera",
        type=str,
        default=DEFAULT_CAMERA_PRESET,
        choices=preset_names,
        help=f"Camera motion preset (default: {DEFAULT_CAMERA_PRESET}). "
        + ", ".join(f"{k}: {v['description']}" for k, v in CAMERA_PRESETS.items()),
    )

    # Mode
    parser.add_argument(
        "--still",
        action="store_true",
        help="Render single frame instead of animation",
    )
    parser.add_argument(
        "--still-frame",
        type=int,
        default=-1,
        help="Frame to render for --still (default: midpoint)",
    )
    parser.add_argument(
        "--scene-only",
        action="store_true",
        help="Build scene and save .blend file without rendering",
    )
    parser.add_argument(
        "--save-blend",
        type=str,
        help="Save .blend file after building scene (renders still proceed)",
    )

    return parser.parse_args(argv)


def collect_maps(args: argparse.Namespace) -> dict[str, str]:
    """Collect PBR map paths from arguments."""
    if args.maps_dir:
        maps = find_pbr_maps(args.maps_dir)
        if not maps:
            print(f"ERROR: No PBR maps found in {args.maps_dir}")
            sys.exit(1)
        return maps

    maps: dict[str, str] = {}
    for name in ("basecolor", "normal", "roughness", "metalness", "height"):
        path = getattr(args, name, None)
        if path:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                print(f"WARNING: {name} map not found: {path}")
            else:
                maps[name] = path
    return maps


def main() -> None:
    """Entry point."""
    args = parse_args()

    if args.batch:
        # Batch mode — render each subdirectory
        batch_dir = Path(args.batch)
        if not batch_dir.is_dir():
            print(f"ERROR: Batch directory not found: {args.batch}")
            sys.exit(1)

        output_base = Path(args.output)
        output_base.mkdir(parents=True, exist_ok=True)

        for material_dir in sorted(batch_dir.iterdir()):
            if not material_dir.is_dir():
                continue
            maps = find_pbr_maps(str(material_dir))
            if not maps:
                print(f"Skipping {material_dir.name} — no PBR maps found")
                continue

            mat_output = str(output_base / f"{material_dir.name}_")
            print(f"\n{'=' * 60}")
            print(f"Rendering: {material_dir.name}")
            print(f"{'=' * 60}\n")

            build_scene(
                pbr_paths=maps,
                material_name=material_dir.name,
                hdri_path=args.hdri,
                frames=args.frames,
                resolution=tuple(args.resolution),
                fps=args.fps,
                output_path=mat_output,
                samples=args.samples,
                displacement_scale=args.displacement_scale,
                normal_strength=args.normal_strength,
                texture_repeat=args.texture_repeat,
                camera_preset=args.camera,
            )

            if args.scene_only:
                blend_path = str(output_base / f"{material_dir.name}.blend")
                bpy.ops.wm.save_as_mainfile(filepath=blend_path)
                print(f"Saved: {blend_path}")
            elif args.still:
                render_still(args.still_frame)
            else:
                render_animation()

        print("\nBatch render complete!")
        return

    # Single material mode
    maps = collect_maps(args)
    if not maps:
        print("ERROR: No PBR maps provided. Use --basecolor/--normal/etc or --maps-dir")
        parser_help = "Run with --help for usage."
        print(parser_help)
        sys.exit(1)

    print(f"Found maps: {', '.join(maps.keys())}")

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    build_scene(
        pbr_paths=maps,
        material_name=args.name,
        hdri_path=args.hdri,
        frames=args.frames,
        resolution=tuple(args.resolution),
        fps=args.fps,
        output_path=args.output,
        samples=args.samples,
        displacement_scale=args.displacement_scale,
        normal_strength=args.normal_strength,
        texture_repeat=args.texture_repeat,
        camera_preset=args.camera,
    )

    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.save_blend)
        print(f"Saved blend file: {args.save_blend}")

    if args.scene_only:
        blend_path = args.save_blend or (args.output.rstrip("_") + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print(f"Scene saved: {blend_path}")
    elif args.still:
        render_still(args.still_frame)
    else:
        render_animation()


if __name__ == "__main__":
    main()
