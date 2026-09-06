from typing import Any, ClassVar

from ..base import VisualFalModel

__all__ = [
    "FLUX1Dev",
    "FLUX2Klein9B",
    "GPTImage15",
    "GPTImage2",
    "NanoBanana",
    "NanoBanana2",
    "NanoBananaPro",
    "Seedream45",
    "Seedream5Lite",
    "ZImageBase",
    "ZImageTurbo",
]


class NanoBanana(VisualFalModel):
    """Nano Banana image generation model with 1K resolution support."""

    display_name = "Nano Banana"
    use_resolution_aspect_ratio = True
    image_urls_parameter = "image_urls"
    aspect_ratios = [
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
    ]
    resolutions = {"1K": 1024}  # Only 1K resolution is supported for NB1


class NanoBananaPro(VisualFalModel):
    """Nano Banana Pro image generation model with 1K/2K/4K resolution support."""

    display_name = "Nano Banana Pro"
    use_resolution_aspect_ratio = True
    image_urls_parameter = "image_urls"
    aspect_ratios = [
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
    ]
    resolutions = {
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }


class NanoBanana2(VisualFalModel):
    """Nano Banana 2 image generation model with extended aspect ratios and 0.5K-4K resolution support."""

    display_name = "Nano Banana 2"
    use_resolution_aspect_ratio = True
    image_urls_parameter = "image_urls"
    aspect_ratios = [
        "8:1",
        "4:1",
        "21:9",
        "16:9",
        "3:2",
        "4:3",
        "5:4",
        "1:1",
        "4:5",
        "3:4",
        "2:3",
        "9:16",
        "1:4",
        "1:8",
    ]
    resolutions = {
        "0.5K": 512,
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }


class ZImageTurbo(VisualFalModel):
    """Z-Image Turbo image generation model optimized for speed."""

    display_name = "Z-Image Turbo"
    size_parameter = "image_size"
    image_url_parameter = "image_url"
    prompt_expansion_parameter = "enable_prompt_expansion"


class ZImageBase(VisualFalModel):
    """Z-Image Base image generation model."""

    display_name = "Z-Image Base"
    size_parameter = "image_size"
    image_url_parameter = "image_url"
    prompt_expansion_parameter = "enable_prompt_expansion"


class FLUX1Dev(VisualFalModel):
    """FLUX.1 [dev] image generation model."""

    display_name = "FLUX.1 [dev]"
    size_parameter = "image_size"
    image_url_parameter = "image_url"


class FLUX2Klein9B(VisualFalModel):
    """FLUX.2 Klein 9B image generation model.

    Supports Colored Noise Sampling (CNS), a stochastic SDE sampler that is
    off by default. When enabled (``enable_cns``), the ``cns_*`` knobs shape
    how much colored noise is injected per step and how it's distributed
    across frequency bands. CNS payload fields are only emitted when CNS is
    enabled so the endpoint keeps its deterministic defaults otherwise.
    """

    display_name = "FLUX.2 Klein 9B"
    size_parameter = "image_size"
    image_urls_parameter = "image_urls"
    prompt_expansion_parameter = "enable_prompt_expansion"
    supports_cns = True

    # API defaults for CNS, mirrored by the UI props in controllers/render.
    CNS_DEFAULTS: ClassVar[dict[str, Any]] = {
        "cns_s_churn": 0.5,
        "cns_gamma_source": "matrix",
        "cns_power_gamma": 0.75,
        "cns_gamma_divider": 1.73,
        "cns_alpha_tilt_start": 0.15,
        "cns_alpha_tilt_end": -0.5,
        "cns_alpha_use_fnorm": True,
        "cns_alpha_exp_interp": True,
        "cns_alpha_exp_sharpness": 0.75,
        "cns_num_freq_bins": 32,
        "cns_energy_scale": 0.98,
    }

    @classmethod
    def _get_cns_parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Build the CNS payload, or nothing when CNS is disabled.

        Returning an empty dict when CNS is disabled lets the endpoint fall
        back to pure deterministic flow-matching (normal Klein).
        """
        if not kwargs.get("enable_cns", False):
            return {}
        params: dict[str, Any] = {"enable_cns": True}
        for key, default in cls.CNS_DEFAULTS.items():
            params[key] = kwargs.get(key, default)
        return params

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Return base parameters plus the optional CNS sampling payload."""
        params = super().parameters(**kwargs)
        params.update(cls._get_cns_parameters(**kwargs))
        return params


class GPTImage15(VisualFalModel):
    """GPT Image 1.5 image generation model.

    The API accepts only three fixed ``image_size`` values — 1024x1024 (1:1),
    1536x1024 (3:2), 1024x1536 (2:3). Requests are mapped by closest aspect
    ratio so a 1920x1080 request lands on ``1536x1024`` instead of falling
    through as raw width/height the endpoint would reject.
    """

    display_name = "GPT Image 1.5"
    image_urls_parameter = "image_urls"

    _SIZE_CHOICES: list[tuple[str, int, int]] = [
        ("1024x1024", 1024, 1024),
        ("1536x1024", 1536, 1024),
        ("1024x1536", 1024, 1536),
    ]

    @classmethod
    def _choose_image_size(cls, width: int, height: int) -> str:
        target = width / height if height else 1.0
        label, _, _ = min(
            cls._SIZE_CHOICES,
            key=lambda item: abs(target - item[1] / item[2]),
        )
        return label

    @classmethod
    def _get_size_parameters(cls, width: int, height: int) -> dict[str, Any]:
        return {"image_size": cls._choose_image_size(width, height)}

    @classmethod
    def describe_output_size(cls, width: int, height: int) -> str:
        return cls._choose_image_size(width, height)


class GPTImage2(VisualFalModel):
    """GPT Image 2 image generation model."""

    display_name = "GPT Image 2"
    size_parameter = "image_size"
    image_urls_parameter = "image_urls"


class Seedream45(VisualFalModel):
    """Seedream 4.5 image generation model."""

    display_name = "Seedream 4.5"
    size_parameter = "image_size"
    image_urls_parameter = "image_urls"


class Seedream5Lite(VisualFalModel):
    """Seedream 5 Lite image generation model."""

    display_name = "Seedream 5 Lite"
    size_parameter = "image_size"
    image_urls_parameter = "image_urls"
