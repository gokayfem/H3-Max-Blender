import bpy

from ...models import ImageTo3DModel, TextTo3DModel
from ..advanced_params import with_advanced_params


@with_advanced_params
class FalGenerate3DPropertyGroup(bpy.types.PropertyGroup):
    """Properties for text-to-3D and image-to-3D generation."""

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TEXT", "Text-to-3D", "Generate 3D model from text prompt"),
            ("IMAGE", "Image-to-3D", "Generate 3D model from an image"),
        ],
        default="TEXT",
    )

    text_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=TextTo3DModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for text-to-3D",
    )

    image_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=ImageTo3DModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for image-to-3D",
    )

    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the 3D model you want to generate",
        default="",
    )

    image_source: bpy.props.EnumProperty(
        name="Image Source",
        items=[
            ("FILE", "File", "Load image from disk"),
            ("RENDER", "Render Result", "Use the current render result"),
        ],
        default="FILE",
    )

    image_path: bpy.props.StringProperty(
        name="Image",
        description="Path to the source image",
        subtype="FILE_PATH",
        default="",
    )

    generate_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Generate materials for the 3D model",
        default=True,
    )

    # ── Endpoint-specific controls ────────────────────────────────────────
    # These are declared once on the PropertyGroup and conditionally shown
    # based on the selected endpoint's ``ui_parameter_map``. Only values for
    # fields the endpoint declares are forwarded — everything else is
    # silently dropped on submit.

    # Shared: polygon budget. The UI range is the union of every endpoint's
    # range; the model clamps per-endpoint at submit time.
    face_count: bpy.props.IntProperty(
        name="Face Count",
        description=(
            "Target polygon budget. Clamped to the selected endpoint's "
            "valid range at submit time"
        ),
        default=30000,
        min=48,
        max=2_000_000,
    )

    # Shared: seed. -1 = leave unset (server picks randomly).
    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed for reproducibility (-1 = random)",
        default=-1,
        min=-1,
        max=2_147_483_647,
    )

    # Tripo H3.1 only: separate seed for texture synthesis.
    texture_seed: bpy.props.IntProperty(
        name="Texture Seed",
        description="Seed for texture synthesis (-1 = random)",
        default=-1,
        min=-1,
        max=2_147_483_647,
    )

    # Meshy-only: preview vs full-texture mode.
    meshy_mode: bpy.props.EnumProperty(
        name="Meshy Mode",
        description="Meshy pipeline stage",
        items=[
            ("full", "Full (textured)", "Generate geometry and textures"),
            ("preview", "Preview (geometry only)", "Untextured geometry"),
        ],
        default="full",
    )

    # Meshy-only: art style.
    art_style: bpy.props.EnumProperty(
        name="Art Style",
        description="Art style preset",
        items=[
            ("realistic", "Realistic", "Realistic rendering"),
            ("sculpture", "Sculpture", "Sculpture style"),
        ],
        default="realistic",
    )

    # Meshy-only: symmetry hint.
    symmetry_mode: bpy.props.EnumProperty(
        name="Symmetry",
        description="Enforce left/right symmetry",
        items=[
            ("auto", "Auto", "Detect from input"),
            ("on", "On", "Force symmetry"),
            ("off", "Off", "Disable symmetry"),
        ],
        default="auto",
    )

    # Meshy-only: character pose hint. 'NONE' sentinel is dropped at submit.
    pose_mode: bpy.props.EnumProperty(
        name="Pose Mode",
        description="Character pose hint (leave unset for non-characters)",
        items=[
            ("NONE", "Unset", "Do not hint a pose"),
            ("a-pose", "A-Pose", "Character A-pose"),
            ("t-pose", "T-Pose", "Character T-pose"),
        ],
        default="NONE",
    )

    # Meshy-only: optional separate texture prompt.
    texture_prompt: bpy.props.StringProperty(
        name="Texture Prompt",
        description="Extra prompt just for texture synthesis",
        default="",
    )

    # Hunyuan Pro only: geometry-only vs normal generation.
    hunyuan_generate_type: bpy.props.EnumProperty(
        name="Generation",
        description="Hunyuan output flavor",
        items=[
            ("Normal", "Normal (textured)", "Full textured output"),
            ("Geometry", "Geometry (white model)", "Untextured geometry only"),
        ],
        default="Normal",
    )

    # Hunyuan Rapid only: white-model-only toggle.
    enable_geometry: bpy.props.BoolProperty(
        name="Geometry Only",
        description="Generate only geometry (no textures)",
        default=False,
    )

    # Tripo H3.1: quad topology toggle.
    quad: bpy.props.BoolProperty(
        name="Quad Topology",
        description="Generate quad-dominant topology instead of triangles",
        default=False,
    )

    # Tripo H3.1: real-world scaling.
    auto_size: bpy.props.BoolProperty(
        name="Auto Size",
        description="Scale output to real-world meters",
        default=False,
    )

    # Tripo H3.1: geometry fidelity tier.
    geometry_quality: bpy.props.EnumProperty(
        name="Geometry Quality",
        description="Geometry detail level",
        items=[
            ("standard", "Standard", "Default geometry detail"),
            ("detailed", "Detailed", "Higher-detail geometry"),
        ],
        default="standard",
    )

    # Tripo H3.1: texture fidelity tier.
    texture_quality: bpy.props.EnumProperty(
        name="Texture Quality",
        description="Texture detail level",
        items=[
            ("standard", "Standard", "Default texture detail"),
            ("detailed", "Detailed", "Higher-detail textures"),
        ],
        default="standard",
    )

    # Tripo H3.1 text-to-3D only.
    negative_prompt: bpy.props.StringProperty(
        name="Negative Prompt",
        description="What to avoid in the generation",
        default="",
    )

    # Tripo H3.1 image-to-3D only.
    orientation: bpy.props.EnumProperty(
        name="Orientation",
        description="Output orientation",
        items=[
            ("default", "Default", "Standard orientation"),
            ("align_image", "Align to Image", "Rotate to match input view"),
        ],
        default="default",
    )

    # Tripo H3.1 image-to-3D only.
    texture_alignment: bpy.props.EnumProperty(
        name="Texture Alignment",
        description="How textures relate to the input image",
        items=[
            ("original_image", "Original Image", "Follow the input image"),
            ("geometry", "Geometry", "Follow the generated geometry"),
        ],
        default="original_image",
    )

    # ── Hyper3D Rodin v2.5 ─────────────────────────────────────────────────
    # Rodin exposes every control as a dedicated, prefixed property so it can
    # coexist with the shared knobs above. See ``RodinV25Model`` for how each
    # maps to the API.

    rodin_tier: bpy.props.EnumProperty(
        name="Tier",
        description=(
            "Generation tier. Higher tiers produce more detailed meshes but "
            "cost more. Extreme-High bills at double the base rate"
        ),
        items=[
            ("Gen-2.5-Extreme-Low", "Extreme Low", "Fastest, lowest detail"),
            ("Gen-2.5-Low", "Low", "Low detail"),
            ("Gen-2.5-Medium", "Medium", "Balanced detail (default)"),
            ("Gen-2.5-High", "High", "High detail"),
            (
                "Gen-2.5-Extreme-High",
                "Extreme High",
                "Highest detail (double cost)",
            ),
        ],
        default="Gen-2.5-Medium",
    )

    rodin_geometry_file_format: bpy.props.EnumProperty(
        name="File Format",
        description="Format of the generated geometry file",
        items=[
            ("glb", "GLB", "glTF binary (recommended for import)"),
            ("usdz", "USDZ", "Universal Scene Description"),
            ("fbx", "FBX", "Autodesk FBX"),
            ("obj", "OBJ", "Wavefront OBJ"),
            ("stl", "STL", "Stereolithography"),
        ],
        default="glb",
    )

    rodin_material: bpy.props.EnumProperty(
        name="Material",
        description=(
            "Material type. PBR: physically-based; Shaded: baked lighting; "
            "All: both; None: geometry only"
        ),
        items=[
            ("PBR", "PBR", "Physically-based materials"),
            ("Shaded", "Shaded", "Baked lighting, no PBR maps"),
            ("All", "All", "Both PBR and Shaded variants"),
            ("None", "None", "Geometry only, no textures"),
        ],
        default="All",
    )

    rodin_quality_mesh_option: bpy.props.EnumProperty(
        name="Quality / Mesh",
        description=(
            "Combined quality and topology. Quad = smooth surfaces, "
            "Triangle = detailed geometry. Valid face counts depend on tier"
        ),
        items=[
            ("4K Quad", "4K Quad", ""),
            ("8K Quad", "8K Quad", ""),
            ("18K Quad", "18K Quad", "Default"),
            ("50K Quad", "50K Quad", ""),
            ("100K Quad", "100K Quad", ""),
            ("200K Quad", "200K Quad", ""),
            ("2K Triangle", "2K Triangle", ""),
            ("20K Triangle", "20K Triangle", ""),
            ("150K Triangle", "150K Triangle", ""),
            ("500K Triangle", "500K Triangle", ""),
            ("1M Triangle", "1M Triangle", ""),
            ("2M Triangle", "2M Triangle", "High/Extreme-High tiers only"),
        ],
        default="18K Quad",
    )

    rodin_texture_mode: bpy.props.EnumProperty(
        name="Texture Mode",
        description=(
            "Texture generation quality. Leave on Auto to let the API pick a "
            "default appropriate for the tier"
        ),
        items=[
            ("NONE", "Auto", "Let the API choose"),
            ("legacy", "Legacy", ""),
            ("extreme-low", "Extreme Low", ""),
            ("low", "Low", ""),
            ("medium", "Medium", ""),
            ("high", "High", ""),
        ],
        default="NONE",
    )

    rodin_geometry_instruct_mode: bpy.props.EnumProperty(
        name="Geometry Mode",
        description=(
            "Faithful follows the prompt/input closely; creative permits more "
            "variation. Only effective on Medium and High tiers"
        ),
        items=[
            ("faithful", "Faithful", "Follow input closely"),
            ("creative", "Creative", "Allow more variation"),
        ],
        default="faithful",
    )

    rodin_is_symmetric: bpy.props.EnumProperty(
        name="Symmetry",
        description="Symmetry mode for the generated mesh",
        items=[
            ("symmetric", "Symmetric", "Force left-right symmetry"),
            ("balanced", "Balanced", "Favor symmetry without enforcing it"),
            ("asymmetric", "Asymmetric", "Allow freely asymmetric geometry"),
            ("unknown", "Auto", "Let the model decide"),
        ],
        default="unknown",
    )

    rodin_hd_texture: bpy.props.BoolProperty(
        name="HD Texture",
        description="Enhanced texture post-processing for higher visual fidelity",
        default=False,
    )

    rodin_texture_delight: bpy.props.BoolProperty(
        name="Texture Delight",
        description="Remove baked lighting/highlights from generated textures",
        default=False,
    )

    rodin_is_micro: bpy.props.BoolProperty(
        name="Micro Detail",
        description=(
            "Generate finer micro-scale geometric detail. Only effective with "
            "the Extreme-High tier"
        ),
        default=False,
    )

    rodin_tapose: bpy.props.BoolProperty(
        name="T/A-Pose",
        description=(
            "Generate characters in T-pose or A-pose, making them easier to "
            "rig and animate"
        ),
        default=False,
    )

    rodin_high_pack: bpy.props.BoolProperty(
        name="HighPack Add-on",
        description=(
            "4K resolution textures and high-poly geometry instead of the "
            "default 2K. Adds extra cost per generation"
        ),
        default=False,
    )

    # Rodin image-to-3D only.
    rodin_use_original_alpha: bpy.props.BoolProperty(
        name="Use Original Alpha",
        description="Preserve the transparency channel from input images",
        default=False,
    )

    # Rodin image-to-3D only.
    rodin_preview_render: bpy.props.BoolProperty(
        name="Preview Render",
        description="Generate a preview render image alongside the model files",
        default=False,
    )

    # Rodin: optional bounding-box conditioning. The toggle gates the three
    # dimension sliders below; ``RodinV25Model`` assembles them into the
    # ``bbox_condition`` [width, height, length] array on submit.
    rodin_use_bbox: bpy.props.BoolProperty(
        name="Bounding Box",
        description="Constrain output proportions to a bounding box",
        default=False,
    )

    rodin_bbox_width: bpy.props.IntProperty(
        name="BBox Width",
        description="Bounding box width",
        default=100,
        min=1,
        max=1000,
    )

    rodin_bbox_height: bpy.props.IntProperty(
        name="BBox Height",
        description="Bounding box height",
        default=100,
        min=1,
        max=1000,
    )

    rodin_bbox_length: bpy.props.IntProperty(
        name="BBox Length",
        description="Bounding box length",
        default=100,
        min=1,
        max=1000,
    )
