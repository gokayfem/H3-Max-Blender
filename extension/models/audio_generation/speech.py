from typing import Any, ClassVar

from ..base import AudioFalModel

__all__ = [
    "SpeechGenerationModel",
    "ElevenLabsSpeechGenerationModel",
    "MiniMaxSpeechGenerationModel",
    "KokoroSpeechGenerationModel",
    "ElevenLabsV3SpeechGenerationModel",
    "XAISpeechGenerationModel",
    "GeminiFlashTTSModel",
    "InworldTTSModel",
    "MiniMaxHDSpeechGenerationModel",
]


class SpeechGenerationModel(AudioFalModel):
    """Base model for text-to-speech generation."""

    supports_preset: ClassVar[bool] = False
    supports_clone: ClassVar[bool] = False
    clone_endpoint: ClassVar[str | None] = None
    text_parameter = "text"
    voice_presets: ClassVar[list[str]] = []
    voice_parameter: ClassVar[str] = "voice"

    @classmethod
    def clone_parameters(
        cls, audio_url: str, text: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Build parameters for voice cloning. Override in subclasses with different APIs."""
        return {"audio_url": audio_url, "text": text}

    @classmethod
    def enumerate(cls, **kwargs: Any) -> list[tuple[str, str, str]]:
        """
        Returns a list of all available models.
        """
        for_preset = kwargs.get("for_preset", False)
        for_clone = kwargs.get("for_clone", False)
        return [
            (subcls.__name__, subcls.display_name, subcls.description)
            for subcls in cls.__subclasses__()
            if subcls.is_available()
            and ((for_preset and subcls.supports_preset) or not for_preset)
            and ((for_clone and subcls.supports_clone) or not for_clone)
        ]

    @classmethod
    def get_voice_presets_for_model(cls, model_key: str) -> list[tuple[str, str, str]]:
        """Return Blender EnumProperty items for a specific model's voice presets.

        Looks up the model subclass by class name, reads its ``voice_presets``,
        and appends a *Custom* sentinel for free-form IDs.
        """
        catalog = cls.catalog()
        model = catalog.get(model_key)
        items: list[tuple[str, str, str]] = []
        if model and hasattr(model, "voice_presets"):
            for name in model.voice_presets:
                items.append((name, name, f"Preset voice: {name}"))
        items.append(("__CUSTOM__", "Custom", "Enter a custom voice ID"))
        return items

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """
        Returns the parameters for the model.
        """
        params = super().parameters(**kwargs)
        params["text"] = kwargs.get("text", None)
        voice = kwargs.get("voice", None)
        if voice:
            params[cls.voice_parameter] = voice
        return params


class ElevenLabsSpeechGenerationModel(SpeechGenerationModel):
    """ElevenLabs TTS Turbo v2.5 speech generation model."""

    endpoint = "fal-ai/elevenlabs/tts/turbo-v2.5"
    display_name = "ElevenLabs TTS Turbo v2.5"
    supports_preset = True
    voice_presets = [
        "Aria",
        "Roger",
        "Sarah",
        "Laura",
        "Charlie",
        "George",
        "Callum",
        "River",
        "Liam",
        "Charlotte",
        "Alice",
        "Matilda",
        "Will",
        "Jessica",
        "Eric",
        "Chris",
        "Brian",
        "Daniel",
        "Lily",
        "Bill",
    ]


class MiniMaxSpeechGenerationModel(SpeechGenerationModel):
    """MiniMax Speech Turbo text-to-speech model."""

    endpoint = "fal-ai/minimax/speech-2.8-turbo"
    clone_endpoint = "fal-ai/minimax/voice-clone"
    display_name = "MiniMax Speech Turbo"
    supports_preset = True
    supports_clone = True
    voice_presets = [
        "Wise_Woman",
        "Friendly_Person",
        "Inspirational_girl",
        "Deep_Voice_Man",
        "Calm_Woman",
        "Casual_Guy",
        "Lively_Girl",
        "Patient_Man",
        "Young_Knight",
        "Determined_Man",
        "Lovely_Girl",
        "Decent_Boy",
        "Imposing_Manner",
        "Elegant_Man",
        "Abbess",
        "Sweet_Girl_2",
        "Exuberant_Girl",
    ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """MiniMax uses 'prompt' (not 'text') and nested voice_setting.voice_id."""
        params: dict[str, Any] = {}
        text = kwargs.get("text", None)
        if text:
            params["prompt"] = text
        voice = kwargs.get("voice", None)
        if voice:
            params["voice_setting"] = {"voice_id": voice}
        params["output_format"] = "url"  # Get URL back, not hex
        return params


class KokoroSpeechGenerationModel(SpeechGenerationModel):
    """Kokoro TTS speech generation model."""

    endpoint = "fal-ai/kokoro/american-english"
    display_name = "Kokoro"
    supports_preset = True
    text_parameter = "prompt"
    voice_presets = [
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Kokoro uses 'prompt' instead of 'text'."""
        params: dict[str, Any] = {}
        text = kwargs.get("text", None)
        if text:
            params["prompt"] = text
        voice = kwargs.get("voice", None)
        if voice:
            params["voice"] = voice
        return params


class ElevenLabsV3SpeechGenerationModel(SpeechGenerationModel):
    """ElevenLabs TTS Eleven-v3 speech generation model."""

    endpoint = "fal-ai/elevenlabs/tts/eleven-v3"
    display_name = "ElevenLabs v3"
    supports_preset = True
    voice_presets = [
        "Aria",
        "Roger",
        "Sarah",
        "Laura",
        "Charlie",
        "George",
        "Callum",
        "River",
        "Liam",
        "Charlotte",
        "Alice",
        "Matilda",
        "Will",
        "Jessica",
        "Eric",
        "Chris",
        "Brian",
        "Daniel",
        "Lily",
        "Bill",
    ]


class XAISpeechGenerationModel(SpeechGenerationModel):
    """xAI TTS speech generation model."""

    endpoint = "xai/tts/v1"
    display_name = "xAI TTS"
    supports_preset = True
    voice_presets = ["eve", "ara", "rex", "sal", "leo"]


class GeminiFlashTTSModel(SpeechGenerationModel):
    """Gemini 3.1 Flash TTS speech generation model."""

    endpoint = "fal-ai/gemini-3.1-flash-tts"
    display_name = "Gemini Flash TTS"
    supports_preset = True
    text_parameter = "prompt"
    voice_presets = [
        "Kore",
        "Puck",
        "Charon",
        "Zephyr",
        "Aoede",
        "Fenrir",
        "Leda",
        "Orus",
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Autonoe",
        "Callirrhoe",
        "Despina",
        "Enceladus",
        "Erinome",
        "Gacrux",
        "Iapetus",
        "Laomedeia",
        "Pulcherrima",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zubenelgenubi",
    ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """Gemini Flash TTS uses 'prompt' instead of 'text'."""
        params: dict[str, Any] = {}
        text = kwargs.get("text", None)
        if text:
            params["prompt"] = text
        voice = kwargs.get("voice", None)
        if voice:
            params["voice"] = voice
        return params


class InworldTTSModel(SpeechGenerationModel):
    """Inworld TTS-1.5 Max speech generation model."""

    endpoint = "fal-ai/inworld-tts"
    display_name = "Inworld TTS"
    supports_preset = True
    voice_presets = [
        "Craig (en)",
        "Loretta (en)",
        "Darlene (en)",
        "Marlene (en)",
        "Hank (en)",
        "Evelyn (en)",
        "Celeste (en)",
        "Pippa (en)",
        "Tessa (en)",
        "Liam (en)",
        "Callum (en)",
        "Hamish (en)",
        "Abby (en)",
        "Graham (en)",
        "Rupert (en)",
        "Mortimer (en)",
        "Snik (en)",
        "Claire (en)",
        "Oliver (en)",
        "Simon (en)",
        "James (en)",
        "Serena (en)",
        "Jessica (en)",
        "Ethan (en)",
        "Tyler (en)",
        "Jason (en)",
        "Chloe (en)",
        "Victoria (en)",
    ]


class MiniMaxHDSpeechGenerationModel(SpeechGenerationModel):
    """MiniMax Speech 2.8 HD text-to-speech model."""

    endpoint = "fal-ai/minimax/speech-2.8-hd"
    display_name = "MiniMax Speech 2.8 HD"
    supports_preset = True
    supports_clone = True
    clone_endpoint = "fal-ai/minimax/voice-clone"
    voice_presets = [
        "Wise_Woman",
        "Friendly_Person",
        "Inspirational_girl",
        "Deep_Voice_Man",
        "Calm_Woman",
        "Casual_Guy",
        "Lively_Girl",
        "Patient_Man",
        "Young_Knight",
        "Determined_Man",
        "Lovely_Girl",
        "Decent_Boy",
        "Imposing_Manner",
        "Elegant_Man",
        "Abbess",
        "Sweet_Girl_2",
        "Exuberant_Girl",
    ]

    @classmethod
    def parameters(cls, **kwargs: Any) -> dict[str, Any]:
        """MiniMax HD uses 'prompt' (not 'text') and nested voice_setting.voice_id."""
        params: dict[str, Any] = {}
        text = kwargs.get("text", None)
        if text:
            params["prompt"] = text
        voice = kwargs.get("voice", None)
        if voice:
            params["voice_setting"] = {"voice_id": voice}
        params["output_format"] = "url"  # Get URL back, not hex
        return params
