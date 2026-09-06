from __future__ import annotations

from .base import (
    Hunyuan3DV31ProModel,
    Hunyuan3DV31RapidModel,
    MeshGenerationModel,
    MeshyV6PreviewModel,
    RodinV25Model,
    TripoH31Model,
    TripoP1Model,
)

__all__ = [
    "ImageTo3DModel",
    "MeshyV6PreviewImageTo3DModel",
    "Hunyuan3DV31ProImageTo3DModel",
    "Hunyuan3DV31RapidImageTo3DModel",
    "TripoP1ImageTo3DModel",
    "TripoH31ImageTo3DModel",
    "RodinV25ImageTo3DModel",
]


class ImageTo3DModel(MeshGenerationModel):
    """Base model for image-to-3D mesh generation."""

    pass


class MeshyV6PreviewImageTo3DModel(ImageTo3DModel, MeshyV6PreviewModel):
    """Meshy v6 preview image-to-3D model."""

    endpoint = "fal-ai/meshy/v6-preview/image-to-3d"


class Hunyuan3DV31ProImageTo3DModel(ImageTo3DModel, Hunyuan3DV31ProModel):
    """Hunyuan 3D v3.1 Pro image-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/pro/image-to-3d"


class Hunyuan3DV31RapidImageTo3DModel(ImageTo3DModel, Hunyuan3DV31RapidModel):
    """Hunyuan 3D v3.1 Rapid image-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/rapid/image-to-3d"


class TripoP1ImageTo3DModel(ImageTo3DModel, TripoP1Model):
    """Tripo P1 image-to-3D model."""

    endpoint = "tripo3d/p1/image-to-3d"


class TripoH31ImageTo3DModel(ImageTo3DModel, TripoH31Model):
    """Tripo H3.1 image-to-3D model."""

    endpoint = "tripo3d/h3.1/image-to-3d"
    ui_parameter_map = {
        **TripoH31Model.ui_parameter_map,
        "orientation": "orientation",
        "texture_alignment": "texture_alignment",
    }


class RodinV25ImageTo3DModel(ImageTo3DModel, RodinV25Model):
    """Hyper3D Rodin v2.5 image-to-3D model.

    The image-to-3D endpoint lives at the Rodin v2.5 root and adds two
    image-only controls on top of the shared Rodin parameters.
    """

    endpoint = "fal-ai/hyper3d/rodin/v2.5"
    ui_parameter_map = {
        **RodinV25Model.ui_parameter_map,
        "rodin_use_original_alpha": "use_original_alpha",
        "rodin_preview_render": "preview_render",
    }
