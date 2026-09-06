from ...models import (
    MaterialExtractionModel,
    MaterialGenerationModel,
    PBREstimationModel,
    TilingTextureModel,
)
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalMaterialOperator
from .props import FalMaterialPropertyGroup


class FalMaterialController(FalController):
    """Controller for PBR material generation via fal.ai."""

    display_name = "Material"
    description = "Generate PBR materials using fal.ai"
    icon = "MATERIAL"
    operator_class = FalMaterialOperator
    properties_class = FalMaterialPropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "mode",
            "full_endpoint",
            "tiling_endpoint",
            "pbr_endpoint",
            "extract_endpoint",
            "prompt",
            "enable_prompt_expansion",
            "image_source",
            "image_path",
            "texture",
            "strength",
            "width",
            "height",
            "tiling_mode",
            "upscale_factor",
            "output_format",
            "seed",
        ],
        field_conditions={
            "full_endpoint": lambda ctx, props: props.mode == "FULL",
            "tiling_endpoint": lambda ctx, props: props.mode == "TILING_ONLY",
            "pbr_endpoint": lambda ctx, props: props.mode == "PBR_ONLY",
            "extract_endpoint": lambda ctx, props: props.mode == "EXTRACT",
            "prompt": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
            "enable_prompt_expansion": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
            "image_source": lambda ctx, props: props.mode in ("PBR_ONLY", "EXTRACT"),
            "image_path": lambda ctx, props: props.mode in ("PBR_ONLY", "EXTRACT")
            and props.image_source == "FILE",
            "texture": lambda ctx, props: props.mode in ("PBR_ONLY", "EXTRACT")
            and props.image_source == "TEXTURE",
            "strength": lambda ctx, props: props.mode == "EXTRACT",
            "width": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
            "height": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
            "tiling_mode": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
            "upscale_factor": lambda ctx, props: props.mode
            in ("FULL", "PBR_ONLY", "EXTRACT"),
            "seed": lambda ctx, props: props.mode
            in ("FULL", "TILING_ONLY", "EXTRACT"),
        },
        field_groupings=[
            {"width", "height"},
        ],
        field_separators=["mode"],
        endpoint_models={
            "full_endpoint": MaterialGenerationModel,
            "tiling_endpoint": TilingTextureModel,
            "pbr_endpoint": PBREstimationModel,
            "extract_endpoint": MaterialExtractionModel,
        },
    )
