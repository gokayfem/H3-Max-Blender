from ...models import ImageToVideoModel, TextToVideoModel
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalVideoOperator
from .props import FalVideoPropertyGroup


class FalVideoController(FalController):
    """Text-to-video and image-to-video (VSE panel only)."""

    display_name = "Video"
    description = "Generate video from text or image using fal.ai"
    icon = "SEQUENCE"
    operator_class = FalVideoOperator
    properties_class = FalVideoPropertyGroup
    panel_vse = FalControllerPanel(
        field_orders=[
            "mode",
            "text_endpoint",
            "image_endpoint",
            "prompt",
            "enable_prompt_expansion",
            "image_source",
            "image_path",
            "use_scene_duration",
            "duration",
            "use_scene_resolution",
            "width",
            "height",
        ],
        field_conditions={
            "text_endpoint": lambda ctx, props: props.mode == "TEXT",
            "image_endpoint": lambda ctx, props: props.mode == "IMAGE",
            "image_source": lambda ctx, props: props.mode == "IMAGE",
            "image_path": lambda ctx, props: props.mode == "IMAGE"
            and props.image_source == "FILE",
            "duration": lambda ctx, props: not props.use_scene_duration,
            "width": lambda ctx, props: not props.use_scene_resolution,
            "height": lambda ctx, props: not props.use_scene_resolution,
        },
        field_groupings=[
            {"width", "height"},
        ],
        endpoint_models={
            "text_endpoint": TextToVideoModel,
            "image_endpoint": ImageToVideoModel,
        },
    )
