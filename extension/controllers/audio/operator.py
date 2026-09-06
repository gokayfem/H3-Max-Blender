from __future__ import annotations

import bpy

from ...importers import add_audio_to_vse
from ...job_queue import FalJob, JobManager
from ...models import (
    MusicGenerationModel,
    SoundEffectsGenerationModel,
    SpeechGenerationModel,
)
from ...utils import download_file, upload_file
from ..base import FalOperator

SPEECH_GENERATION_MODELS = SpeechGenerationModel.catalog()
MUSIC_GENERATION_MODELS = MusicGenerationModel.catalog()
SOUND_EFFECTS_GENERATION_MODELS = SoundEffectsGenerationModel.catalog()


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------
class FalAudioOperator(FalOperator):
    """
    Audio operator.
    """

    label = "Generate Audio"  # text in button in UI

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Return True if the operator is enabled (i.e. if the button can be clicked)
        """
        if props.mode == "TTS":
            if props.voice_mode == "CLONE":
                if props.tts_clone_endpoint == "NONE" or not bool(
                    props.voice_ref_path.strip()
                ):
                    return False
            elif props.voice_mode == "PRESET":
                if props.tts_preset_endpoint == "NONE":
                    return False
            return bool(props.text.strip())
        elif props.mode == "SFX":
            if props.sfx_endpoint == "NONE":
                return False
            return bool(props.sfx_prompt.strip())
        else:  # MUSIC
            if props.music_endpoint == "NONE":
                return False
            return bool(props.music_prompt.strip())

    def _tts(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Generate text-to-speech audio (preset or clone mode)."""
        if props.voice_mode == "PRESET":
            return self._tts_preset(context, props)
        else:
            return self._tts_clone(context, props)

    def _tts_preset(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Generate TTS using a preset voice."""
        model = SPEECH_GENERATION_MODELS[props.tts_preset_endpoint]

        # Resolve voice: use custom text if "Custom" selected, else the preset name
        voice = (
            props.voice_custom
            if props.voice_preset == "__CUSTOM__"
            else props.voice_preset
        )
        params = model.parameters(
            text=props.text,
            voice=voice,
            duration=props.duration,
        )
        params = self.with_advanced_params(params, props)

        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_tts", scene=origin_scene)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"TTS: {props.text[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating speech...")
        return {"FINISHED"}

    def _tts_clone(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Generate TTS using a cloned voice from reference audio."""
        model = SPEECH_GENERATION_MODELS[props.tts_clone_endpoint]

        if not model.clone_endpoint:
            self.report(
                {"ERROR"}, f"{model.display_name} does not support voice cloning"
            )
            return {"CANCELLED"}

        # Upload reference audio to get a URL
        ref_path = bpy.path.abspath(props.voice_ref_path)
        try:
            audio_url = upload_file(ref_path)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to upload reference audio: {e}")
            return {"CANCELLED"}

        params = model.clone_parameters(
            audio_url=audio_url,
            text=props.text,
        )
        params = self.with_advanced_params(params, props)

        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_tts_clone", scene=origin_scene)

        job = FalJob(
            endpoint=model.clone_endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"TTS Clone: {props.text[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Cloning voice and generating speech...")
        return {"FINISHED"}

    def _sfx(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """
        Generate sound effect audio.
        """
        model = SOUND_EFFECTS_GENERATION_MODELS[props.sfx_endpoint]
        params = model.parameters(
            prompt=props.sfx_prompt,
            duration=props.duration,
        )
        params = self.with_advanced_params(params, props)

        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_sfx", scene=origin_scene)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"SFX: {props.sfx_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating sound effect...")
        return {"FINISHED"}

    def _music(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """
        Generate music audio.
        """
        model = MUSIC_GENERATION_MODELS[props.music_endpoint]
        params = model.parameters(
            prompt=props.music_prompt,
            duration=props.duration,
        )
        params = self.with_advanced_params(params, props)

        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_audio_result(job, "fal_music", scene=origin_scene)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Music: {props.music_prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating music...")
        return {"FINISHED"}

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """
        Invoke the operator.
        """
        if props.mode == "TTS":
            return self._tts(context, props)
        elif props.mode == "SFX":
            return self._sfx(context, props)
        else:
            return self._music(context, props)


# ---------------------------------------------------------------------------
# Result handler (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_audio_result(
    job: FalJob,
    name: str,
    *,
    scene: bpy.types.Scene | None = None,
) -> None:
    """Download audio result and add to VSE."""
    if job.status == "error":
        print(f"fal.ai: Audio generation failed: {job.error}")
        return

    result = job.result or {}
    audio_url = None
    for key in ["audio", "output", "audio_url", "audio_file"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            audio_url = val["url"]
            break
        elif isinstance(val, str) and val.startswith("http"):
            audio_url = val
            break

    if not audio_url:
        print("fal.ai: No audio in response")
        return

    local_path = download_file(audio_url, suffix=".wav")
    add_audio_to_vse(local_path, name=name, scene=scene)
    print("fal.ai: Audio added to VSE!")
