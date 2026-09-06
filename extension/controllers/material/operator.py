from __future__ import annotations

import bpy  # type: ignore[import-not-found]

from ...importers import import_image_as_texture
from ...job_queue import FalJob, JobManager
from ...models import (
    MaterialExtractionModel,
    MaterialGenerationModel,
    PBREstimationModel,
    TilingTextureModel,
)
from ...utils import download_file, upload_blender_image, upload_file
from ..operators import FalOperator

TILING_MODELS = TilingTextureModel.catalog()
PBR_MODELS = PBREstimationModel.catalog()
MATERIAL_MODELS = MaterialGenerationModel.catalog()
EXTRACT_MODELS = MaterialExtractionModel.catalog()

PBR_MAP_NAMES = ("basecolor", "normal", "roughness", "metalness", "height")
PBR_DOWNLOAD_KEYS = [f"images.{i}.url" for i in range(len(PBR_MAP_NAMES) + 1)]


class FalMaterialOperator(FalOperator):
    """Operator for generating PBR materials via fal.ai."""

    label = "Generate Material"

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Check whether the operator can be invoked given current property state."""
        if props.mode in ("FULL", "TILING_ONLY"):
            return bool(props.prompt.strip())
        has_image = (
            bool(props.image_path.strip())
            if props.image_source == "FILE"
            else props.texture is not None
        )
        if props.mode == "EXTRACT":
            return bool(props.prompt.strip()) and has_image
        return has_image

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Dispatch material generation based on the selected mode."""
        if props.mode == "FULL":
            return self._full_pipeline(context, props)
        elif props.mode == "EXTRACT":
            return self._extract_from_photo(context, props)
        elif props.mode == "PBR_ONLY":
            return self._pbr_only(context, props)
        return self._tiling_only(context, props)

    # ── Full Pipeline ──────────────────────────────────────────────────

    def _full_pipeline(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Run the full material generation pipeline (texture + PBR maps)."""
        model = MATERIAL_MODELS[props.full_endpoint]
        seed = props.seed if props.seed >= 0 else None
        params = model.parameters(
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            enable_prompt_expansion=props.enable_prompt_expansion,
            output_format=props.output_format,
            tiling_mode=props.tiling_mode,
            upscale_factor=props.upscale_factor,
        )
        params = self.with_advanced_params(params, props)

        target_obj_name = context.active_object.name if context.active_object else None
        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            _handle_pbr_result(job, target_obj_name, f"fal_{prompt_short}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=PBR_DOWNLOAD_KEYS,
            label=f"Material: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating material...")
        return {"FINISHED"}

    # ── Extract from Photo ─────────────────────────────────────────────

    def _extract_from_photo(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Extract a tileable material with PBR maps from a photo."""
        try:
            if props.image_source == "FILE":
                image_url = upload_file(bpy.path.abspath(props.image_path))
            else:
                img = props.texture
                if not img:
                    self.report({"ERROR"}, "No texture selected")
                    return {"CANCELLED"}
                image_url = upload_blender_image(img)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        model = EXTRACT_MODELS[props.extract_endpoint]
        seed = props.seed if props.seed >= 0 else None
        params = model.parameters(
            prompt=props.prompt,
            image_url=image_url,
            width=props.width,
            height=props.height,
            seed=seed,
            enable_prompt_expansion=props.enable_prompt_expansion,
            output_format=props.output_format,
            tiling_mode=props.tiling_mode,
            upscale_factor=props.upscale_factor,
            strength=props.strength,
        )
        params = self.with_advanced_params(params, props)

        target_obj_name = context.active_object.name if context.active_object else None
        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            _handle_pbr_result(job, target_obj_name, f"fal_{prompt_short}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=PBR_DOWNLOAD_KEYS,
            label=f"Extract: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Extracting material from photo...")
        return {"FINISHED"}

    # ── PBR Only ───────────────────────────────────────────────────────

    def _pbr_only(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Extract PBR maps from an existing image."""
        if props.image_source == "FILE":
            image_path = props.image_path
        else:
            img = props.texture
            if not img:
                self.report({"ERROR"}, "No texture selected")
                return {"CANCELLED"}
            image_path = img.filepath_raw

        model = PBR_MODELS[props.pbr_endpoint]
        params = model.parameters(
            image_path=image_path,
            output_format=props.output_format,
            upscale_factor=props.upscale_factor,
        )
        params = self.with_advanced_params(params, props)

        target_obj_name = context.active_object.name if context.active_object else None
        label = (props.texture.name[:20] if props.texture else "") or "pbr"

        def on_complete(job: FalJob):
            _handle_pbr_result(job, target_obj_name, f"fal_{label}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=PBR_DOWNLOAD_KEYS,
            label=f"PBR: {label}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Estimating PBR maps...")
        return {"FINISHED"}

    # ── Tiling Only ────────────────────────────────────────────────────

    def _tiling_only(
        self, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> set[str]:
        """Generate a seamless tiling texture without PBR extraction."""
        model = TILING_MODELS[props.tiling_endpoint]
        seed = props.seed if props.seed >= 0 else None
        params = model.parameters(
            prompt=props.prompt,
            width=props.width,
            height=props.height,
            seed=seed,
            enable_prompt_expansion=props.enable_prompt_expansion,
            output_format=props.output_format,
            tiling_mode=props.tiling_mode,
        )
        params = self.with_advanced_params(params, props)

        target_obj_name = context.active_object.name if context.active_object else None
        prompt_short = props.prompt[:20]

        def on_complete(job: FalJob):
            _handle_tiling_result(job, target_obj_name, f"fal_{prompt_short}")

        job = FalJob(
            endpoint=model.endpoint,
            arguments=params,
            on_complete=on_complete,
            download_keys=["images.0.url"],
            label=f"Tiling: {prompt_short}...",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Generating tileable texture...")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Result handlers (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_pbr_result(
    job: FalJob,
    target_obj_name: str | None,
    name: str,
) -> None:
    """Handle completed PBR generation job and apply material to target object."""
    if job.status == "error":
        print(f"fal.ai: PBR generation failed: {job.error}")
        return

    paths: dict[str, str] = {}
    for i in range(len(job.result["images"])):
        map_type = job.result["images"][i].get("map_type", None)
        if map_type:
            paths[map_type] = job.downloaded_files.get(f"images.{i}.url")

    required = {"basecolor", "normal", "roughness", "metalness"}
    missing = required - paths.keys()
    if missing:
        print(f"fal.ai: Missing PBR maps in response: {missing}")
        return

    obj = bpy.data.objects.get(target_obj_name) if target_obj_name else None
    if not obj:
        print("fal.ai: No active object — PBR maps downloaded but not applied")
        return

    _apply_pbr_material(obj, paths, name)
    print("fal.ai: PBR material applied!")


def _handle_tiling_result(
    job: FalJob,
    target_obj_name: str | None,
    name: str,
) -> None:
    """Handle completed tiling texture job and apply to target object."""
    if job.status == "error":
        print(f"fal.ai: Tiling generation failed: {job.error}")
        return

    local_path = job.downloaded_files.get("images.0.url")
    if not local_path:
        result = job.result or {}
        image_url = None
        if "images" in result and result["images"]:
            image_url = result["images"][0].get("url")
        if not image_url:
            print("fal.ai: No image in tiling response")
            return
        local_path = download_file(image_url, suffix=".png")

    obj = bpy.data.objects.get(target_obj_name) if target_obj_name else None
    if obj:
        bpy.context.view_layer.objects.active = obj
    import_image_as_texture(local_path, name=name, apply_to_selected=obj is not None)
    print("fal.ai: Tiling texture applied!")


# ---------------------------------------------------------------------------
# Blender material builder
# ---------------------------------------------------------------------------
def _apply_pbr_material(
    obj: bpy.types.Object,
    paths: dict[str, str],
    name: str = "fal_pbr",
) -> bpy.types.Material:
    """Create a Principled BSDF material with full PBR map connections."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # Base Color
    tex_bc = nodes.new("ShaderNodeTexImage")
    tex_bc.location = (-400, 200)
    tex_bc.image = bpy.data.images.load(paths["basecolor"])
    tex_bc.image.name = f"{name}_basecolor"
    links.new(tex_bc.outputs["Color"], principled.inputs["Base Color"])

    # Normal Map
    tex_norm = nodes.new("ShaderNodeTexImage")
    tex_norm.location = (-700, -400)
    tex_norm.image = bpy.data.images.load(paths["normal"])
    tex_norm.image.name = f"{name}_normal"
    tex_norm.image.colorspace_settings.name = "Non-Color"
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.location = (-400, -400)
    links.new(tex_norm.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

    # Roughness
    tex_rough = nodes.new("ShaderNodeTexImage")
    tex_rough.location = (-400, -100)
    tex_rough.image = bpy.data.images.load(paths["roughness"])
    tex_rough.image.name = f"{name}_roughness"
    tex_rough.image.colorspace_settings.name = "Non-Color"
    links.new(tex_rough.outputs["Color"], principled.inputs["Roughness"])

    # Metalness
    tex_metal = nodes.new("ShaderNodeTexImage")
    tex_metal.location = (-400, -250)
    tex_metal.image = bpy.data.images.load(paths["metalness"])
    tex_metal.image.name = f"{name}_metalness"
    tex_metal.image.colorspace_settings.name = "Non-Color"
    links.new(tex_metal.outputs["Color"], principled.inputs["Metallic"])

    # Height → Displacement
    if "height" in paths:
        tex_height = nodes.new("ShaderNodeTexImage")
        tex_height.location = (-700, -600)
        tex_height.image = bpy.data.images.load(paths["height"])
        tex_height.image.name = f"{name}_height"
        tex_height.image.colorspace_settings.name = "Non-Color"

        disp = nodes.new("ShaderNodeDisplacement")
        disp.location = (0, -400)
        links.new(tex_height.outputs["Color"], disp.inputs["Height"])
        links.new(disp.outputs["Displacement"], output.inputs["Displacement"])
        if hasattr(mat, "displacement_method"):
            mat.displacement_method = "BOTH"
        elif hasattr(mat, "cycles") and hasattr(mat.cycles, "displacement_method"):
            mat.cycles.displacement_method = "BOTH"

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return mat
