from .music import (
    CassetteAIMusicGenerationModel,
    ElevenLabsMusicGenerationModel,
    MiniMaxMusicGenerationModel,
    MusicGenerationModel,
    StableAudio25MusicGenerationModel,
)
from .sfx import (
    CassetteAISoundEffectsGenerationModel,
    ElevenLabsSoundEffectsGenerationModel,
    SoundEffectsGenerationModel,
)
from .speech import (
    ElevenLabsSpeechGenerationModel,
    ElevenLabsV3SpeechGenerationModel,
    GeminiFlashTTSModel,
    InworldTTSModel,
    KokoroSpeechGenerationModel,
    MiniMaxHDSpeechGenerationModel,
    MiniMaxSpeechGenerationModel,
    SpeechGenerationModel,
    XAISpeechGenerationModel,
)

__all__ = [
    # Speech
    "SpeechGenerationModel",
    "ElevenLabsSpeechGenerationModel",
    "MiniMaxSpeechGenerationModel",
    "KokoroSpeechGenerationModel",
    "ElevenLabsV3SpeechGenerationModel",
    "XAISpeechGenerationModel",
    "GeminiFlashTTSModel",
    "InworldTTSModel",
    "MiniMaxHDSpeechGenerationModel",
    # Music
    "MusicGenerationModel",
    "ElevenLabsMusicGenerationModel",
    "MiniMaxMusicGenerationModel",
    "StableAudio25MusicGenerationModel",
    "CassetteAIMusicGenerationModel",
    # SFX
    "SoundEffectsGenerationModel",
    "ElevenLabsSoundEffectsGenerationModel",
    "CassetteAISoundEffectsGenerationModel",
]
