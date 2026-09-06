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
    "TextTo3DModel",
    "MeshyV6PreviewTextTo3DModel",
    "Hunyuan3DV31ProTextTo3DModel",
    "Hunyuan3DV31RapidTextTo3DModel",
    "TripoP1TextTo3DModel",
    "TripoH31TextTo3DModel",
    "RodinV25TextTo3DModel",
]


class TextTo3DModel(MeshGenerationModel):
    """Base model for text-to-3D mesh generation."""

    pass


class MeshyV6PreviewTextTo3DModel(TextTo3DModel, MeshyV6PreviewModel):
    """Meshy v6 preview text-to-3D model."""

    endpoint = "fal-ai/meshy/v6-preview/text-to-3d"


class Hunyuan3DV31ProTextTo3DModel(TextTo3DModel, Hunyuan3DV31ProModel):
    """Hunyuan 3D v3.1 Pro text-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/pro/text-to-3d"


class Hunyuan3DV31RapidTextTo3DModel(TextTo3DModel, Hunyuan3DV31RapidModel):
    """Hunyuan 3D v3.1 Rapid text-to-3D model."""

    endpoint = "fal-ai/hunyuan-3d/v3.1/rapid/text-to-3d"


class TripoP1TextTo3DModel(TextTo3DModel, TripoP1Model):
    """Tripo P1 text-to-3D model."""

    endpoint = "tripo3d/p1/text-to-3d"


class TripoH31TextTo3DModel(TextTo3DModel, TripoH31Model):
    """Tripo H3.1 text-to-3D model."""

    endpoint = "tripo3d/h3.1/text-to-3d"
    ui_parameter_map = {
        **TripoH31Model.ui_parameter_map,
        "negative_prompt": "negative_prompt",
    }


class RodinV25TextTo3DModel(TextTo3DModel, RodinV25Model):
    """Hyper3D Rodin v2.5 text-to-3D model."""

    endpoint = "fal-ai/hyper3d/rodin/v2.5/text-to-3d"
