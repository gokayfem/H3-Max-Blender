from __future__ import annotations

from ...models import ImageTo3DModel, TextTo3DModel
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalGenerate3DOperator
from .props import FalGenerate3DPropertyGroup


def _selected_model(ctx, props):
    """Return the model class currently selected by the mode/endpoint enums."""
    if props.mode == "TEXT":
        catalog = TextTo3DModel.catalog()
        key = props.text_endpoint
    else:
        catalog = ImageTo3DModel.catalog()
        key = props.image_endpoint
    return catalog.get(key)


def _endpoint_supports(field_name):
    """Condition factory: True if the selected endpoint declares this UI field."""

    def check(ctx, props):
        model = _selected_model(ctx, props)
        if model is None:
            return False
        return field_name in getattr(model, "ui_parameter_map", {})

    return check


class FalGenerate3DController(FalController):
    """Controller for text-to-3D and image-to-3D model generation via fal.ai."""

    display_name = "3D Generation"
    description = "Generate 3D models from text or images using fal.ai"
    icon = "MESH_MONKEY"
    operator_class = FalGenerate3DOperator
    properties_class = FalGenerate3DPropertyGroup
    panel_3d = FalControllerPanel(
        field_orders=[
            "mode",
            "text_endpoint",
            "image_endpoint",
            "prompt",
            "negative_prompt",
            "texture_prompt",
            "image_source",
            "image_path",
            "generate_materials",
            # Meshy-specific
            "meshy_mode",
            "art_style",
            # Hunyuan
            "hunyuan_generate_type",
            "enable_geometry",
            # Tripo h3.1 quality knobs
            "geometry_quality",
            "texture_quality",
            "quad",
            "auto_size",
            "orientation",
            "texture_alignment",
            # Hyper3D Rodin v2.5
            "rodin_tier",
            "rodin_quality_mesh_option",
            "rodin_material",
            "rodin_texture_mode",
            "rodin_geometry_instruct_mode",
            "rodin_is_symmetric",
            "rodin_geometry_file_format",
            "rodin_hd_texture",
            "rodin_texture_delight",
            "rodin_is_micro",
            "rodin_tapose",
            "rodin_high_pack",
            "rodin_use_original_alpha",
            "rodin_preview_render",
            "rodin_use_bbox",
            "rodin_bbox_width",
            "rodin_bbox_height",
            "rodin_bbox_length",
            # Shared
            "face_count",
            "symmetry_mode",
            "pose_mode",
            "seed",
            "texture_seed",
        ],
        field_conditions={
            "text_endpoint": lambda ctx, props: props.mode == "TEXT",
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "image_source": lambda ctx, props: props.mode == "IMAGE",
            "image_path": lambda ctx, props: props.mode == "IMAGE"
            and props.image_source == "FILE",
            "negative_prompt": _endpoint_supports("negative_prompt"),
            "texture_prompt": _endpoint_supports("texture_prompt"),
            "meshy_mode": _endpoint_supports("meshy_mode"),
            "art_style": _endpoint_supports("art_style"),
            "hunyuan_generate_type": _endpoint_supports("hunyuan_generate_type"),
            "enable_geometry": _endpoint_supports("enable_geometry"),
            "geometry_quality": _endpoint_supports("geometry_quality"),
            "texture_quality": _endpoint_supports("texture_quality"),
            "quad": _endpoint_supports("quad"),
            "auto_size": _endpoint_supports("auto_size"),
            "orientation": _endpoint_supports("orientation"),
            "texture_alignment": _endpoint_supports("texture_alignment"),
            # Hyper3D Rodin v2.5
            "rodin_tier": _endpoint_supports("rodin_tier"),
            "rodin_quality_mesh_option": _endpoint_supports(
                "rodin_quality_mesh_option"
            ),
            "rodin_material": _endpoint_supports("rodin_material"),
            "rodin_texture_mode": _endpoint_supports("rodin_texture_mode"),
            "rodin_geometry_instruct_mode": _endpoint_supports(
                "rodin_geometry_instruct_mode"
            ),
            "rodin_is_symmetric": _endpoint_supports("rodin_is_symmetric"),
            "rodin_geometry_file_format": _endpoint_supports(
                "rodin_geometry_file_format"
            ),
            "rodin_hd_texture": _endpoint_supports("rodin_hd_texture"),
            "rodin_texture_delight": _endpoint_supports("rodin_texture_delight"),
            "rodin_is_micro": _endpoint_supports("rodin_is_micro"),
            "rodin_tapose": _endpoint_supports("rodin_tapose"),
            "rodin_high_pack": _endpoint_supports("rodin_high_pack"),
            "rodin_use_original_alpha": _endpoint_supports(
                "rodin_use_original_alpha"
            ),
            "rodin_preview_render": _endpoint_supports("rodin_preview_render"),
            "rodin_use_bbox": _endpoint_supports("rodin_use_bbox"),
            # Dimension sliders only show once bounding-box conditioning is on.
            "rodin_bbox_width": lambda ctx, props: _endpoint_supports(
                "rodin_bbox_width"
            )(ctx, props)
            and props.rodin_use_bbox,
            "rodin_bbox_height": lambda ctx, props: _endpoint_supports(
                "rodin_bbox_height"
            )(ctx, props)
            and props.rodin_use_bbox,
            "rodin_bbox_length": lambda ctx, props: _endpoint_supports(
                "rodin_bbox_length"
            )(ctx, props)
            and props.rodin_use_bbox,
            "face_count": _endpoint_supports("face_count"),
            "symmetry_mode": _endpoint_supports("symmetry_mode"),
            "pose_mode": _endpoint_supports("pose_mode"),
            "seed": _endpoint_supports("seed"),
            "texture_seed": _endpoint_supports("texture_seed"),
        },
        endpoint_models={
            "text_endpoint": TextTo3DModel,
            "image_endpoint": ImageTo3DModel,
        },
    )
