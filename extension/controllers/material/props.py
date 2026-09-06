import bpy  # type: ignore[import-not-found]

from ...models import (
    MaterialExtractionModel,
    MaterialGenerationModel,
    PBREstimationModel,
    TilingTextureModel,
)
from ..advanced_params import with_advanced_params


@with_advanced_params
class FalMaterialPropertyGroup(bpy.types.PropertyGroup):
    """Property group for material generation settings."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("FULL", "Full Pipeline", "Generate tileable texture and extract PBR maps"),
            ("EXTRACT", "Extract from Photo", "Extract a seamless tileable material with PBR maps from a photo"),
            ("PBR_ONLY", "PBR from Image", "Extract PBR maps from an existing image"),
            ("TILING_ONLY", "Tiling Texture", "Generate a tileable texture only"),
        ],
        default="FULL",
    )

    # ── Endpoint selectors ─────────────────────────────────────────────

    full_endpoint: bpy.props.EnumProperty(
        name="Model",
        items=MaterialGenerationModel.enumerate()
        or [("NONE", "No Models Available", "")],
        description="Model for full material generation pipeline",
    )

    tiling_endpoint: bpy.props.EnumProperty(
        name="Tiling Model",
        items=TilingTextureModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Model for seamless tiling texture generation",
    )

    pbr_endpoint: bpy.props.EnumProperty(
        name="PBR Model",
        items=PBREstimationModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Model for PBR material map estimation",
    )

    extract_endpoint: bpy.props.EnumProperty(
        name="Extract Model",
        items=MaterialExtractionModel.enumerate()
        or [("NONE", "No Models Available", "")],
        description="Model for extracting a tileable material from a photo",
    )

    # ── Generation parameters ──────────────────────────────────────────

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the material to generate",
        default="",
    )

    enable_prompt_expansion: bpy.props.BoolProperty(
        name="Prompt Expansion",
        description="Let the AI model expand and enhance your prompt",
        default=True,
    )

    width: bpy.props.IntProperty(
        name="W",
        default=1024,
        min=512,
        max=2048,
        step=16,
        description="Texture width in pixels",
    )

    height: bpy.props.IntProperty(
        name="H",
        default=1024,
        min=512,
        max=2048,
        step=16,
        description="Texture height in pixels",
    )

    tiling_mode: bpy.props.EnumProperty(
        name="Tiling",
        items=[
            ("both", "All Directions", "Seamless tiling in both directions"),
            ("horizontal", "Horizontal", "Tile left-right only"),
            ("vertical", "Vertical", "Tile top-bottom only"),
        ],
        default="both",
        description="Which directions the texture should tile seamlessly",
    )

    seed: bpy.props.IntProperty(
        name="Seed",
        default=-1,
        min=-1,
        max=2147483647,
        description="Random seed (-1 for random)",
    )

    output_format: bpy.props.EnumProperty(
        name="Format",
        items=[
            ("png", "PNG", "Lossless"),
            ("jpeg", "JPEG", "Lossy, smaller"),
            ("webp", "WebP", "Modern format"),
        ],
        default="png",
    )

    upscale_factor: bpy.props.EnumProperty(
        name="Upscale Factor",
        items=[
            ("NONE", "None", "No upscale"),
            ("2", "2x", "2x"),
            ("4", "4x", "4x"),
        ],
        default="NONE",
    )

    strength: bpy.props.FloatProperty(
        name="Strength",
        description="How much to transform the input photo (higher = more stylized)",
        default=0.6,
        min=0.0,
        max=1.0,
        step=5,
    )

    # ── PBR-only image source ──────────────────────────────────────────

    image_source: bpy.props.EnumProperty(
        name="Source",
        items=[
            ("FILE", "File", "Load from disk"),
            ("TEXTURE", "Blender Texture", "Use an existing Blender image"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="Image Path",
        subtype="FILE_PATH",
        description="Path to the input texture image",
    )

    texture: bpy.props.PointerProperty(
        name="Texture",
        description="Blender image to use as input",
        type=bpy.types.Image,
    )
