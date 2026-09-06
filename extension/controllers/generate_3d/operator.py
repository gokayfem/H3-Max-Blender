from __future__ import annotations

import os
import tempfile
import urllib.request

import bpy

from ...importers import import_glb, import_obj
from ...job_queue import FalJob, JobManager
from ...models import ImageTo3DModel, TextTo3DModel
from ...utils import download_file
from ..operators import FalOperator

TEXT_TO_3D_MODELS = TextTo3DModel.catalog()
IMAGE_TO_3D_MODELS = ImageTo3DModel.catalog()


def _collect_ui_params(
    props: bpy.types.PropertyGroup,
    model_cls: type,
) -> dict:
    """Pull every UI prop the selected model declares into a kwargs dict.

    Skips the common kwargs (prompt, image_*) that callers already pass
    explicitly, and drops sentinel values so the model's ``parameters()``
    can apply defaults:
      - seeds of -1 → random
      - 'NONE' enum → unset
      - empty strings → unset (handled in ``parameters()``)
    """
    ui_map = getattr(model_cls, "ui_parameter_map", {})
    out: dict = {}
    for ui_name in ui_map:
        if not hasattr(props, ui_name):
            continue
        value = getattr(props, ui_name)
        # Seeds use -1 as "random / leave unset"
        if ui_name.endswith("seed") and value == -1:
            continue
        out[ui_name] = value
    return out


def _extract_url(val: object) -> str | None:
    """Extract a URL string from a response value (dict with ``url`` key or bare string)."""
    if isinstance(val, dict) and "url" in val:
        return val["url"]
    if isinstance(val, str) and val.startswith("http"):
        return val
    return None


def _find_glb_url(result: dict) -> str | None:
    """Return a GLB/glTF model URL from *result*, or ``None``."""
    for key in ["model_glb", "model_mesh", "model", "output", "mesh", "glb"]:
        url = _extract_url(result.get(key))
        if url:
            return url

    urls = result.get("model_urls")
    if isinstance(urls, dict):
        url = _extract_url(urls.get("glb"))
        if url:
            return url

    return None


def _find_obj_info(result: dict) -> dict:
    """Return ``{obj: …, mtl: …, texture: …}`` file-info dicts present in *result*."""
    info: dict = {}

    for key, target in [
        ("model_obj", "obj"),
        ("material_mtl", "mtl"),
        ("texture", "texture"),
    ]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            info[target] = val

    urls = result.get("model_urls")
    if isinstance(urls, dict):
        for key in ["obj", "mtl", "texture"]:
            val = urls.get(key)
            if isinstance(val, dict) and "url" in val:
                info.setdefault(key, val)

    return info


def _download_obj_bundle(info: dict) -> str:
    """Download OBJ + MTL + texture into a shared temp directory.

    Files are saved with their original names so that the MTL's texture
    references resolve correctly.  Returns the path to the OBJ file.
    """
    tmp_dir = tempfile.mkdtemp(prefix="fal_obj_")
    obj_path = None

    for key in ["obj", "mtl", "texture"]:
        entry = info.get(key)
        if not entry:
            continue
        url = entry["url"]
        filename = entry.get("file_name") or os.path.basename(url.split("?")[0])
        local = os.path.join(tmp_dir, filename)
        urllib.request.urlretrieve(url, local)
        if key == "obj":
            obj_path = local

    return obj_path


def _handle_3d_result(job: FalJob, name: str) -> None:
    """Download 3D result and import into the scene, falling back to OBJ if GLB fails."""
    if job.status == "error":
        print(f"fal.ai: 3D generation failed: {job.error}")
        return

    result = job.result or {}
    cursor_loc = tuple(bpy.context.scene.cursor.location)

    # --- Try GLB first ---
    glb_url = _find_glb_url(result)
    if glb_url:
        try:
            local_path = download_file(glb_url, suffix=".glb")
            objects = import_glb(local_path, name=f"fal_{name}", location=cursor_loc)
            print(f"fal.ai: Imported {len(objects)} object(s) from 3D generation")
            return
        except Exception as e:
            print(f"fal.ai: GLB import failed ({e}), trying OBJ fallback...")

    # --- Fall back to OBJ/MTL ---
    obj_info = _find_obj_info(result)
    if obj_info.get("obj"):
        try:
            obj_path = _download_obj_bundle(obj_info)
            objects = import_obj(obj_path, name=f"fal_{name}", location=cursor_loc)
            print(f"fal.ai: Imported {len(objects)} object(s) from OBJ fallback")
            return
        except Exception as e:
            print(f"fal.ai: OBJ import also failed: {e}")

    print(
        f"fal.ai: No importable 3D model found in response keys: {list(result.keys())}"
    )


class FalGenerate3DOperator(FalOperator):
    """Operator that submits text-to-3D or image-to-3D generation jobs to fal.ai."""

    label = "Generate 3D Model"
    description = "Generate a 3D model using fal.ai"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Return whether a valid prompt or image source is configured."""
        if props.mode == "TEXT":
            return bool(props.prompt.strip())
        else:
            return bool(props.image_path.strip() or props.image_source == "RENDER")

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Dispatch to text-to-3D or image-to-3D based on the current mode."""
        if props.mode == "TEXT":
            return self._text_to_3d(context, props)
        else:
            return self._image_to_3d(context, props)

    def _text_to_3d(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Submit a text-to-3D generation job."""
        model = TEXT_TO_3D_MODELS[props.text_endpoint]
        params = model.parameters(
            prompt=props.prompt,
            generate_materials=props.generate_materials,
            **_collect_ui_params(props, model),
        )
        params = self.with_advanced_params(params, props)
        name = props.prompt[:30]

        def on_complete(job: FalJob) -> None:
            _handle_3d_result(job, name)

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"3D: {props.prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model...")
        return {"FINISHED"}

    def _image_to_3d(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Submit an image-to-3D generation job."""
        if props.image_source == "RENDER":
            render_img = bpy.data.images.get("Render Result")
            if not render_img:
                self.report({"ERROR"}, "No render result available")
                return {"CANCELLED"}
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            render_img.save_render(tmp.name)
            image_path = tmp.name
        elif props.image_path:
            image_path = bpy.path.abspath(props.image_path)
        else:
            self.report({"ERROR"}, "No image specified")
            return {"CANCELLED"}
        model = IMAGE_TO_3D_MODELS[props.image_endpoint]
        params = model.parameters(
            image_path=image_path,
            prompt=props.prompt,
            generate_materials=props.generate_materials,
            **_collect_ui_params(props, model),
        )
        params = self.with_advanced_params(params, props)

        def on_complete(job: FalJob) -> None:
            _handle_3d_result(job, "image_model")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label="3D from image",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating 3D model from image...")
        return {"FINISHED"}
