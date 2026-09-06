from __future__ import annotations

import tempfile

import bpy

from ...importers import add_video_to_vse, import_image_to_editor
from ...job_queue import FalJob, JobManager
from ...models import ImageUpscalingModel, VideoUpscalingModel
from ...utils import download_file, upload_blender_image, upload_file
from ..operators import FalOperator

IMAGE_UPSCALING_MODELS = ImageUpscalingModel.catalog()
VIDEO_UPSCALING_MODELS = VideoUpscalingModel.catalog()


class FalUpscaleOperator(FalOperator):
    """Operator that submits image or video upscaling jobs to fal.ai."""

    label = "Upscale"
    description = "Upscale an image or video using fal.ai"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Return whether a valid source is configured for upscaling."""
        if props.source == "FILE":
            return bool(props.image_path.strip())
        elif props.source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            return render_img is not None and render_img.has_data
        elif props.source == "TEXTURE":
            return props.texture is not None
        return False

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Submit an upscaling job based on the current mode and source settings."""
        is_video = props.mode == "VIDEO"

        try:
            source_url = _resolve_source_url(props)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        if is_video:
            model = VIDEO_UPSCALING_MODELS[props.video_endpoint]
            params = model.parameters(video_url=source_url)
        else:
            model = IMAGE_UPSCALING_MODELS[props.image_endpoint]
            params = model.parameters(image_url=source_url)
        params = self.with_advanced_params(params, props)

        mode_str = props.mode.lower()
        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_upscale_result(job, is_video, scene=origin_scene)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Upscale ({mode_str})",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, f"Upscaling {mode_str}...")
        return {"FINISHED"}


def _resolve_source_url(props: bpy.types.PropertyGroup) -> str:
    """Resolve the source property to a fal CDN URL."""
    if props.source == "FILE":
        return upload_file(bpy.path.abspath(props.image_path))
    elif props.source == "RENDER":
        render_img = bpy.data.images.get("Render Result")
        if not render_img or not render_img.has_data:
            raise RuntimeError("No render result available")
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        render_img.save_render(tmp.name)  # Let RuntimeError propagate
        return upload_file(tmp.name)
    elif props.source == "TEXTURE":
        img = props.texture  # Already an Image object
        if not img:
            raise RuntimeError("No texture selected")
        return upload_blender_image(img)
    raise RuntimeError("Unknown source type")


def _find_result_url(result: dict, is_video: bool) -> str | None:
    """Extract the output URL from the API response."""
    for key in ["video", "output", "image"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            return val["url"]
        elif isinstance(val, str) and val.startswith("http"):
            return val
    if "images" in result and result["images"]:
        first = result["images"][0]
        if isinstance(first, dict) and "url" in first:
            return first["url"]
        elif isinstance(first, str):
            return first
    return None


def _handle_upscale_result(
    job: FalJob,
    is_video: bool,
    *,
    scene: bpy.types.Scene | None = None,
) -> None:
    """Download the upscaled result and import into Blender."""
    if job.status == "error":
        print(f"fal.ai: Upscale failed: {job.error}")
        return

    result = job.result or {}
    result_url = _find_result_url(result, is_video)
    if not result_url:
        print("fal.ai: No output in upscale response")
        return

    suffix = ".mp4" if is_video else ".png"
    local_path = download_file(result_url, suffix=suffix)

    if is_video:
        add_video_to_vse(local_path, name="fal_upscaled", scene=scene)
        print("fal.ai: Upscaled video added to VSE")
    else:
        import_image_to_editor(local_path, name="fal_upscaled")
        print("fal.ai: Upscaled image loaded")
