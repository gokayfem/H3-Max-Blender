from __future__ import annotations

from typing import Any, ClassVar

from ...utils import path_to_data_uri
from ..base import FalModel

__all__ = [
    "MeshyV6PreviewModel",
    "RodinV25Model",
]


class MeshGenerationModel(FalModel):
    """Base model for mesh generation."""

    image_url_parameter: ClassVar[str | None] = None
    image_urls_parameter: ClassVar[str | None] = None
    generate_materials_parameter: ClassVar[str | None] = None
    enable_prompt_expansion_parameter: ClassVar[str | None] = None
    prompt_parameter: ClassVar[str | None] = "prompt"

    # Maps a UI property name → API field name (or None to drop).
    # Populated by subclasses to declare which Blender UI controls apply.
    # The controller panel uses membership to decide which fields to show;
    # the operator passes every UI prop as a kwarg, and ``parameters()``
    # forwards only those declared here.
    ui_parameter_map: ClassVar[dict[str, str]] = {}

    # Per-model clamp ranges for the unified ``face_count`` UI slider.
    # (min, max) — the UI property declares a wide range; we clamp at
    # submit time so each endpoint gets values within its actual schema.
    face_count_range: ClassVar[tuple[int, int] | None] = None

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build the API parameters from static defaults and an optional image path."""
        params = super().parameters(**kwargs)

        image_paths = []
        image_urls = []

        if "image_paths" in kwargs:
            image_paths = kwargs["image_paths"]
        if "image_path" in kwargs:
            image_paths.append(kwargs["image_path"])
        if "image_urls" in kwargs:
            image_urls = kwargs["image_urls"]
        if "image_url" in kwargs:
            image_urls.append(kwargs["image_url"])

        if cls.image_urls_parameter or cls.image_url_parameter:
            all_image_urls = image_urls + [
                path_to_data_uri(image_path) for image_path in image_paths
            ]
            if all_image_urls:
                if cls.image_urls_parameter:
                    params[cls.image_urls_parameter] = all_image_urls
                if cls.image_url_parameter:
                    params[cls.image_url_parameter] = all_image_urls[0]

        if cls.generate_materials_parameter:
            params[cls.generate_materials_parameter] = kwargs.get(
                "generate_materials", True
            )

        if cls.prompt_parameter:
            params["prompt"] = kwargs.get("prompt", "")

        if cls.enable_prompt_expansion_parameter:
            params[cls.enable_prompt_expansion_parameter] = kwargs.get(
                "enable_prompt_expansion", True
            )

        # Forward declared UI params. Empty strings, None, and sentinel
        # "NONE" enum values are treated as "leave at server default".
        for ui_name, api_name in cls.ui_parameter_map.items():
            if ui_name not in kwargs:
                continue
            value = kwargs[ui_name]
            if value is None:
                continue
            if isinstance(value, str):
                if not value.strip() or value == "NONE":
                    continue
            # Clamp the unified face_count slider to this model's schema
            if ui_name == "face_count" and cls.face_count_range:
                lo, hi = cls.face_count_range
                value = max(lo, min(hi, int(value)))
            params[api_name] = value

        return params


class MeshyV6PreviewModel(MeshGenerationModel):
    display_name = "Meshy v6 Preview"
    static_parameters = {
        "should_remesh": False,
        "should_texture": True,
        "topology": "triangle",
    }
    image_url_parameter = "image_url"
    generate_materials_parameter = "generate_pbr"
    face_count_range = (100, 300_000)
    ui_parameter_map = {
        "face_count": "target_polycount",
        "seed": "seed",
        "meshy_mode": "mode",
        "art_style": "art_style",
        "symmetry_mode": "symmetry_mode",
        "pose_mode": "pose_mode",
        "texture_prompt": "texture_prompt",
    }


class Hunyuan3DV31ProModel(MeshGenerationModel):
    display_name = "Hunyuan 3D v3.1 Pro"
    image_url_parameter = "input_image_url"
    generate_materials_parameter = "generate_pbr"
    face_count_range = (40_000, 1_500_000)
    ui_parameter_map = {
        "face_count": "face_count",
        "hunyuan_generate_type": "generate_type",
    }


class Hunyuan3DV31RapidModel(MeshGenerationModel):
    display_name = "Hunyuan 3D v3.1 Rapid"
    image_url_parameter = "input_image_url"
    generate_materials_parameter = "generate_pbr"
    ui_parameter_map = {
        "enable_geometry": "enable_geometry",
    }


class TripoP1Model(MeshGenerationModel):
    """Tripo P1 model base."""

    display_name = "Tripo P1"
    image_url_parameter = "image_url"
    static_parameters: ClassVar[dict[str, Any]] = {"texture": True}
    face_count_range = (48, 20_000)
    ui_parameter_map = {
        "face_count": "face_limit",
        "seed": "model_seed",
    }


class TripoH31Model(MeshGenerationModel):
    """Tripo H3.1 model base."""

    display_name = "Tripo H3.1"
    image_url_parameter = "image_url"
    generate_materials_parameter = "pbr"
    static_parameters: ClassVar[dict[str, Any]] = {"texture": True, "pbr": True}
    face_count_range = (1_000, 2_000_000)
    ui_parameter_map = {
        "face_count": "face_limit",
        "seed": "model_seed",
        "texture_seed": "texture_seed",
        "quad": "quad",
        "auto_size": "auto_size",
        "geometry_quality": "geometry_quality",
        "texture_quality": "texture_quality",
    }


class RodinV25Model(MeshGenerationModel):
    """Hyper3D Rodin v2.5 model base (shared by text-to-3D and image-to-3D).

    Rodin exposes a single combined ``quality_mesh_option`` enum rather
    than a free polygon budget, so it does not declare ``face_count_range``
    / a ``face_count`` UI control. Materials are selected through the
    ``material`` enum (not a boolean), so ``generate_materials_parameter``
    is intentionally left unset.

    Most controls are plain enum/bool passthroughs declared in
    ``ui_parameter_map``. Three controls need post-processing and are
    therefore *popped* from kwargs in :meth:`parameters` before the generic
    forwarder runs (they still appear in ``ui_parameter_map`` so the panel
    knows to surface them):

    - ``rodin_high_pack`` (bool) → ``addons=["HighPack"]``
    - ``rodin_use_bbox`` (bool) + ``rodin_bbox_{width,height,length}``
      (ints) → ``bbox_condition=[w, h, l]``
    """

    display_name = "Hyper3D Rodin v2.5"
    # Image-to-3D sends up to 5 ``image_urls``; text-to-3D never passes an
    # image so this stays inert there (no urls -> nothing emitted).
    image_urls_parameter = "image_urls"
    prompt_parameter = "prompt"

    # Seed bounds accepted by the Rodin API.
    seed_range: ClassVar[tuple[int, int]] = (0, 65535)

    ui_parameter_map: ClassVar[dict[str, str]] = {
        "seed": "seed",
        "rodin_tier": "tier",
        "rodin_geometry_file_format": "geometry_file_format",
        "rodin_material": "material",
        "rodin_quality_mesh_option": "quality_mesh_option",
        "rodin_texture_mode": "texture_mode",
        "rodin_geometry_instruct_mode": "geometry_instruct_mode",
        "rodin_is_symmetric": "is_symmetric",
        "rodin_hd_texture": "hd_texture",
        "rodin_texture_delight": "texture_delight",
        "rodin_is_micro": "is_micro",
        "rodin_tapose": "TAPose",
        # Custom-handled in parameters() (see class docstring). Listed here
        # only so the controller panel surfaces them; popped before the
        # generic forwarder so they are never sent verbatim.
        "rodin_high_pack": "addons",
        "rodin_use_bbox": "bbox_condition",
        "rodin_bbox_width": "bbox_condition",
        "rodin_bbox_height": "bbox_condition",
        "rodin_bbox_length": "bbox_condition",
    }

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build Rodin API params, transforming the custom-handled controls."""
        kwargs = dict(kwargs)
        high_pack = kwargs.pop("rodin_high_pack", False)
        use_bbox = kwargs.pop("rodin_use_bbox", False)
        bbox = (
            kwargs.pop("rodin_bbox_width", 0),
            kwargs.pop("rodin_bbox_height", 0),
            kwargs.pop("rodin_bbox_length", 0),
        )

        params = super().parameters(**kwargs)

        # Clamp the seed into the range the API accepts.
        seed = params.get("seed")
        if seed is not None:
            lo, hi = cls.seed_range
            params["seed"] = max(lo, min(hi, int(seed)))

        if high_pack:
            params["addons"] = ["HighPack"]

        if use_bbox:
            params["bbox_condition"] = [int(v) for v in bbox]

        return params
