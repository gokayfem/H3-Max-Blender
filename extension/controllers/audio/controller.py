from ...models import (
    MusicGenerationModel,
    SoundEffectsGenerationModel,
    SpeechGenerationModel,
)
from ..base import FalController
from ..ui import FalControllerPanel
from .operator import FalAudioOperator
from .props import FalAudioPropertyGroup


class FalAudioController(FalController):
    """
    Audio controller.
    """

    display_name = "Audio"
    description = "Generate audio using fal.ai"
    icon = "SPEAKER"
    operator_class = FalAudioOperator
    properties_class = FalAudioPropertyGroup
    panel_vse = FalControllerPanel(
        field_orders=[
            "mode",
            "duration",
            "tts_preset_endpoint",
            "tts_clone_endpoint",
            "sfx_endpoint",
            "music_endpoint",
            "voice_mode",
            "voice_preset",
            "voice_custom",
            "voice_ref_path",
            "text",
            "sfx_prompt",
            "music_prompt",
        ],
        field_conditions={
            "tts_preset_endpoint": lambda context, props: props.mode == "TTS"
            and props.voice_mode == "PRESET",
            "tts_clone_endpoint": lambda context, props: props.mode == "TTS"
            and props.voice_mode == "CLONE",
            "sfx_endpoint": lambda context, props: props.mode == "SFX",
            "music_endpoint": lambda context, props: props.mode == "MUSIC",
            "voice_mode": lambda context, props: props.mode == "TTS",
            "voice_preset": lambda context, props: props.mode == "TTS"
            and props.voice_mode == "PRESET",
            "voice_custom": lambda context, props: props.mode == "TTS"
            and props.voice_mode == "PRESET"
            and props.voice_preset == "__CUSTOM__",
            "voice_ref_path": lambda context, props: props.mode == "TTS"
            and props.voice_mode == "CLONE",
            "sfx_prompt": lambda context, props: props.mode == "SFX",
            "music_prompt": lambda context, props: props.mode == "MUSIC",
            "text": lambda context, props: props.mode == "TTS",
            "duration": lambda context, props: props.mode == "SFX"
            or props.mode == "MUSIC",
        },
        endpoint_models={
            "tts_preset_endpoint": SpeechGenerationModel,
            "tts_clone_endpoint": SpeechGenerationModel,
            "sfx_endpoint": SoundEffectsGenerationModel,
            "music_endpoint": MusicGenerationModel,
        },
    )
