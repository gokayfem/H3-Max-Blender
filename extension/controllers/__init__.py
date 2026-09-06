from .audio import FalAudioController
from .base import FalController
from .generate_3d import FalGenerate3DController
from .material import FalMaterialController
from .render import FalRenderController
from .upscale import FalUpscaleController
from .video import FalVideoController

__all__ = [
    "FalController",
    "FalAudioController",
    "FalGenerate3DController",
    "FalMaterialController",
    "FalRenderController",
    "FalUpscaleController",
    "FalVideoController",
]
