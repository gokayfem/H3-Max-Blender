from typing import Any

from ..base import AudioFalModel

__all__ = [
    "MusicGenerationModel",
    "ElevenLabsMusicGenerationModel",
    "MiniMaxMusicGenerationModel",
    "StableAudio25MusicGenerationModel",
    "CassetteAIMusicGenerationModel",
]


class MusicGenerationModel(AudioFalModel):
    """Base model for prompt-driven music generation."""

    prompt_parameter = "prompt"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["prompt"] = params.get("prompt", "")
        return params


class ElevenLabsMusicGenerationModel(MusicGenerationModel):
    """ElevenLabs music generation model."""

    endpoint = "fal-ai/elevenlabs/music"
    display_name = "ElevenLabs Music"


class MiniMaxMusicGenerationModel(MusicGenerationModel):
    """MiniMax Music 2.6 generation model."""

    endpoint = "fal-ai/minimax-music/v2.6"
    display_name = "MiniMax Music 2.6"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """MiniMax Music supports prompt and optional lyrics."""
        params: dict[str, Any] = {}
        params["prompt"] = kwargs.get("prompt", "")
        lyrics = kwargs.get("lyrics")
        if lyrics:
            params["lyrics"] = lyrics
        else:
            params["is_instrumental"] = True
        return params


class StableAudio25MusicGenerationModel(MusicGenerationModel):
    """Stable Audio 2.5 music generation model."""

    endpoint = "fal-ai/stable-audio-25/text-to-audio"
    display_name = "Stable Audio 2.5"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Stable Audio uses prompt and optional seconds_total (up to 190)."""
        params: dict[str, Any] = {}
        params["prompt"] = kwargs.get("prompt", "")
        duration = kwargs.get("duration")
        if duration:
            params["seconds_total"] = min(int(duration), 190)
        return params


class CassetteAIMusicGenerationModel(MusicGenerationModel):
    """CassetteAI music generation model."""

    endpoint = "cassetteai/music-generator"
    display_name = "CassetteAI Music"

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """CassetteAI requires prompt and duration (10-180 seconds)."""
        params: dict[str, Any] = {}
        params["prompt"] = kwargs.get("prompt", "")
        duration = kwargs.get("duration", 30)
        params["duration"] = max(10, min(int(duration), 180))
        return params
