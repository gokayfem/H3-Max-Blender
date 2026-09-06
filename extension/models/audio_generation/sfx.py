from typing import Any

from ..base import AudioFalModel

__all__ = [
    "SoundEffectsGenerationModel",
    "ElevenLabsSoundEffectsGenerationModel",
    "CassetteAISoundEffectsGenerationModel",
]


class SoundEffectsGenerationModel(AudioFalModel):
    """Base model for sound effects generation."""

    pass


class ElevenLabsSoundEffectsGenerationModel(SoundEffectsGenerationModel):
    """ElevenLabs Sound Effects v2 generation model."""

    endpoint = "fal-ai/elevenlabs/sound-effects/v2"
    display_name = "ElevenLabs Sound Effects v2"
    prompt_parameter = "text"  # non-standard
    duration_parameter = "duration_seconds"  # non-standard


class CassetteAISoundEffectsGenerationModel(SoundEffectsGenerationModel):
    """CassetteAI Sound Effects generation model."""

    endpoint = "cassetteai/sound-effects-generator"
    display_name = "CassetteAI SFX"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """CassetteAI SFX requires prompt and duration (1-30 seconds)."""
        params: dict[str, Any] = {}
        params["prompt"] = kwargs.get("prompt", "")
        duration = kwargs.get("duration", 5)
        params["duration"] = max(1, min(int(duration), 30))
        return params
