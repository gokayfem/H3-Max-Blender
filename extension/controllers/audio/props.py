import bpy

from ...models import (
    MusicGenerationModel,
    SoundEffectsGenerationModel,
    SpeechGenerationModel,
)
from ..advanced_params import with_advanced_params


def _voice_preset_items(
    self: "FalAudioPropertyGroup",
    context: bpy.types.Context,
) -> list[tuple[str, str, str]]:
    """Dynamic callback: return voice presets for the currently selected TTS model."""
    model_key = self.tts_preset_endpoint
    return SpeechGenerationModel.get_voice_presets_for_model(model_key)


@with_advanced_params
class FalAudioPropertyGroup(bpy.types.PropertyGroup):
    """Property group for audio generation settings."""

    # ── Common ──────────────────────────────────────────────────────────
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("TTS", "Text-to-Speech", "Generate speech from text"),
            ("SFX", "Sound Effects", "Generate sound effects from prompt"),
            ("MUSIC", "Music", "Generate music from prompt"),
        ],
        default="TTS",
    )

    duration: bpy.props.FloatProperty(
        name="Duration",
        description="Duration in seconds (0 for default/auto)",
        default=0.0,
        min=0.0,
        max=300.0,
    )

    # ── TTS Mode ──────────────────────────────────────────────────────────

    tts_preset_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SpeechGenerationModel.enumerate(for_preset=True)
        or [("NONE", "No Models Available", "")],
        description="Which model to use for TTS",
    )

    tts_clone_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SpeechGenerationModel.enumerate(for_clone=True)
        or [("NONE", "No Models Available", "")],
        description="Which model to use for TTS",
    )

    text: bpy.props.StringProperty(
        name="Text",
        description="Text to convert to speech",
        default="",
    )

    voice_mode: bpy.props.EnumProperty(
        name="Voice Mode",
        items=[
            ("PRESET", "Preset", "Use a voice preset"),
            ("CLONE", "Clone", "Clone voice from reference audio"),
        ],
        default="PRESET",
    )

    voice_preset: bpy.props.EnumProperty(
        name="Voice",
        items=_voice_preset_items,
        description="Select a voice preset",
    )

    voice_custom: bpy.props.StringProperty(
        name="Custom Voice ID",
        description="Custom voice name or ID",
        default="",
    )

    voice_ref_path: bpy.props.StringProperty(
        name="Reference Audio",
        description="Path to reference audio for voice cloning",
        subtype="FILE_PATH",
        default="",
    )

    # ── SFX Mode ──────────────────────────────────────────────────────────

    sfx_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=SoundEffectsGenerationModel.enumerate()
        or [("NONE", "No Models Available", "")],
        description="Which model to use for SFX",
    )

    sfx_prompt: bpy.props.StringProperty(
        name="SFX Prompt",
        description="Describe the sound effect",
        default="",
    )

    # ── Music Mode ──────────────────────────────────────────────────────────

    music_endpoint: bpy.props.EnumProperty(
        name="Endpoint",
        items=MusicGenerationModel.enumerate() or [("NONE", "No Models Available", "")],
        description="Which model to use for music",
    )

    music_prompt: bpy.props.StringProperty(
        name="Music Prompt",
        description="Describe the music (genre, mood, instruments)",
        default="",
    )
