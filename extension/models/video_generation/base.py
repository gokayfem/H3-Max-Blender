from __future__ import annotations

from typing import Any, ClassVar

from ..base import VisualFalModel

__all__ = [
    "VideoFalModel",
    "LTX2VideoModel",
    "LTX2DistilledVideoModel",
    "LTX23VideoModel",
    "LTX23DistilledVideoModel",
    "Wan22VideoModel",
    "Wan22TurboVideoModel",
    "Wan27VideoModel",
    "Seedance20VideoModel",
    "Seedance20FastVideoModel",
    "KlingV3VideoModel",
    "KlingV3StandardVideoModel",
    "KlingV3ProVideoModel",
    "Veo31VideoModel",
    "Veo31FastVideoModel",
    "Sora2VideoModel",
    "WanVACE14BVideoModel",
    "WanFun22A14BVideoModel",
]


class VideoFalModel(VisualFalModel):
    """
    Base for video-generating fal.ai models.

    Adds unified duration/fps handling on top of VisualFalModel. Subclasses set
    class attributes to describe their specific duration shape:

    - ``duration_parameter``: API key under which duration is emitted. None
      means the model doesn't accept a duration parameter (e.g. turbo variants).
    - ``duration_unit``: "seconds" or "frames". If "frames", the caller-supplied
      seconds are converted via ``native_fps`` (or user-supplied fps if the
      model exposes one).
    - ``duration_cast``: ``int`` or ``str`` — the final value type emitted.
    - ``duration_suffix``: string appended when ``duration_cast is str`` (e.g.
      "s" for Veo's "4s"/"6s"/"8s").
    - ``duration_values``: if set, the numeric input is snapped to the nearest
      value in this list (which holds already-formatted canonical values).
    - ``duration_min`` / ``duration_max``: otherwise, the numeric input is
      clamped to this range before formatting.
    - ``native_fps``: used for seconds↔frames conversion and as the default
      when ``fps_parameter`` is exposed but no fps is supplied.
    - ``fps_parameter``: if set, caller-supplied fps is emitted under this key.
    """

    duration_parameter: ClassVar[str | None] = None
    duration_unit: ClassVar[str] = "seconds"
    duration_cast: ClassVar[type] = int
    duration_suffix: ClassVar[str] = ""
    duration_values: ClassVar[list[Any] | None] = None
    duration_min: ClassVar[int | float | None] = None
    duration_max: ClassVar[int | float | None] = None
    native_fps: ClassVar[int] = 24
    fps_parameter: ClassVar[str | None] = None

    @classmethod
    def _to_numeric(cls, value: Any) -> float:
        """Strip suffix and convert a (possibly string) duration value to float."""
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value)
        if cls.duration_suffix and s.endswith(cls.duration_suffix):
            s = s[: -len(cls.duration_suffix)]
        return float(s)

    @classmethod
    def _format_duration(cls, numeric: float) -> Any:
        """Cast a numeric duration into the API's expected wire format."""
        if cls.duration_cast is str:
            return f"{int(round(numeric))}{cls.duration_suffix}"
        return int(round(numeric))

    @classmethod
    def _clamp_or_snap(cls, numeric: float) -> Any:
        """Snap to nearest allowed value, or clamp to declared min/max."""
        if cls.duration_values is not None:
            return min(
                cls.duration_values,
                key=lambda v: abs(cls._to_numeric(v) - numeric),
            )
        if cls.duration_min is not None:
            numeric = max(cls._to_numeric(cls.duration_min), numeric)
        if cls.duration_max is not None:
            numeric = min(cls._to_numeric(cls.duration_max), numeric)
        return cls._format_duration(numeric)

    @classmethod
    def _get_duration_parameters(
        cls,
        duration_seconds: float | None,
        fps: float | None = None,
    ) -> dict[str, Any]:
        """Build fps + duration/num_frames params for this model."""
        result: dict[str, Any] = {}

        if cls.fps_parameter and fps:
            result[cls.fps_parameter] = int(fps)

        if cls.duration_parameter is None or duration_seconds is None:
            return result

        effective_fps = fps if fps else cls.native_fps
        if cls.duration_unit == "frames":
            numeric = float(duration_seconds) * float(effective_fps)
        else:
            numeric = float(duration_seconds)

        result[cls.duration_parameter] = cls._clamp_or_snap(numeric)
        return result

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        params: dict[str, Any] = super().parameters(**kwargs) or {}
        params.update(
            cls._get_duration_parameters(
                duration_seconds=kwargs.get("duration"),
                fps=kwargs.get("fps"),
            )
        )
        return params


# ---------------------------------------------------------------------------
# LTX-2 (19B) — video_size freeform, num_frames, user-settable fps
# ---------------------------------------------------------------------------
class LTX2VideoModel(VideoFalModel):
    """Base model for LTX-2 19B family."""

    display_name = "LTX-2 19B"
    size_parameter = "video_size"
    duration_parameter = "num_frames"
    duration_unit = "frames"
    duration_min = 9
    duration_max = 481
    native_fps = 25
    fps_parameter = "fps"


class LTX2DistilledVideoModel(LTX2VideoModel):
    """LTX-2 19B Distilled family."""

    display_name = "LTX-2 19B Distilled"


# ---------------------------------------------------------------------------
# LTX-2.3 (22B) — video_size freeform, num_frames, user-settable fps
# ---------------------------------------------------------------------------
class LTX23VideoModel(VideoFalModel):
    """Base model for LTX-2.3 22B family."""

    display_name = "LTX 2.3 22B"
    size_parameter = "video_size"
    duration_parameter = "num_frames"
    duration_unit = "frames"
    duration_min = 9
    duration_max = 481
    native_fps = 24
    fps_parameter = "fps"


class LTX23DistilledVideoModel(LTX23VideoModel):
    """LTX-2.3 22B Distilled family."""

    display_name = "LTX 2.3 22B Distilled"


# ---------------------------------------------------------------------------
# Wan 2.2 A14B — aspect_ratio + resolution, num_frames, user-settable fps
# ---------------------------------------------------------------------------
class Wan22VideoModel(VideoFalModel):
    """Base model for Wan 2.2 A14B family."""

    display_name = "Wan 2.2"
    use_resolution_aspect_ratio = True
    aspect_ratios = ["16:9", "9:16", "1:1"]
    resolutions = {"480p": 480, "580p": 580, "720p": 720}
    duration_parameter = "num_frames"
    duration_unit = "frames"
    duration_min = 17
    duration_max = 161
    native_fps = 16
    fps_parameter = "frames_per_second"


class Wan22TurboVideoModel(Wan22VideoModel):
    """Wan 2.2 Turbo — no user-settable duration or fps."""

    display_name = "Wan 2.2 Turbo"
    duration_parameter = None
    fps_parameter = None


# ---------------------------------------------------------------------------
# Wan 2.7 — aspect_ratio + resolution (t2v), resolution-only (i2v), int seconds
# ---------------------------------------------------------------------------
class Wan27VideoModel(VideoFalModel):
    """Base model for Wan 2.7 family."""

    display_name = "Wan 2.7"
    use_resolution_aspect_ratio = True
    aspect_ratios = ["16:9", "9:16", "1:1", "4:3", "3:4"]
    resolutions = {"720p": 720, "1080p": 1080}
    duration_parameter = "duration"
    duration_unit = "seconds"
    duration_cast = int
    duration_min = 2
    duration_max = 15


# ---------------------------------------------------------------------------
# Seedance 2.0 — aspect_ratio + resolution, string-seconds with "auto"/"4".."15"
# ---------------------------------------------------------------------------
class Seedance20VideoModel(VideoFalModel):
    """Base model for Seedance 2.0 family."""

    display_name = "Seedance 2.0"
    use_resolution_aspect_ratio = True
    aspect_ratios = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
    resolutions = {"480p": 480, "720p": 720}
    duration_parameter = "duration"
    duration_unit = "seconds"
    duration_cast = str
    duration_values = [str(i) for i in range(4, 16)]


class Seedance20FastVideoModel(Seedance20VideoModel):
    """Seedance 2.0 Fast family."""

    display_name = "Seedance 2.0 Fast"


# ---------------------------------------------------------------------------
# Kling v3 — aspect_ratio only (t2v), none (i2v); string-seconds "3".."15"
# ---------------------------------------------------------------------------
class KlingV3VideoModel(VideoFalModel):
    """Base model for Kling v3 family."""

    display_name = "Kling v3"
    use_resolution_aspect_ratio = True
    emit_resolution = False
    aspect_ratios = ["16:9", "9:16", "1:1"]
    duration_parameter = "duration"
    duration_unit = "seconds"
    duration_cast = str
    duration_values = [str(i) for i in range(3, 16)]


class KlingV3StandardVideoModel(KlingV3VideoModel):
    """Kling v3 Standard family."""

    display_name = "Kling v3 Standard"


class KlingV3ProVideoModel(KlingV3VideoModel):
    """Kling v3 Pro family."""

    display_name = "Kling v3 Pro"


# ---------------------------------------------------------------------------
# Veo 3.1 — aspect_ratio + resolution, string-seconds with "s" suffix
# ---------------------------------------------------------------------------
class Veo31VideoModel(VideoFalModel):
    """Base model for Veo 3.1 family."""

    display_name = "Veo 3.1"
    use_resolution_aspect_ratio = True
    aspect_ratios = ["16:9", "9:16"]
    resolutions = {"720p": 720, "1080p": 1080, "4k": 2160}
    duration_parameter = "duration"
    duration_unit = "seconds"
    duration_cast = str
    duration_suffix = "s"
    duration_values = ["4s", "6s", "8s"]


class Veo31FastVideoModel(Veo31VideoModel):
    """Veo 3.1 Fast family."""

    display_name = "Veo 3.1 Fast"


# ---------------------------------------------------------------------------
# Sora 2 — aspect_ratio + fixed 720p resolution, int-seconds enum
# ---------------------------------------------------------------------------
class Sora2VideoModel(VideoFalModel):
    """Base model for Sora 2 family."""

    display_name = "Sora 2"
    use_resolution_aspect_ratio = True
    aspect_ratios = ["9:16", "16:9"]
    resolutions = {"720p": 720}
    duration_parameter = "duration"
    duration_unit = "seconds"
    duration_cast = int
    duration_values = [4, 8, 12, 16, 20]


# ---------------------------------------------------------------------------
# Wan-VACE / Wan-Fun (used for depth/edge V2V) — kept as-is for now
# ---------------------------------------------------------------------------
class WanVACE14BVideoModel(VisualFalModel):
    """Wan-VACE 14B video model."""

    display_name = "Wan-VACE 14B"


class WanFun22A14BVideoModel(VisualFalModel):
    """Wan-Fun 2.2 A14B video model."""

    display_name = "Wan Fun 2.2 A14B"
