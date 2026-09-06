from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar

import bpy

from ...importers import (
    add_video_to_vse,
    import_image_to_editor,
    resize_image_to_target,
)
from ...job_queue import FalJob, JobManager
from ...models import (
    DepthGuidedImageGenerationModel,
    DepthVideoModel,
    EdgeGuidedImageGenerationModel,
    EdgeVideoModel,
    ImageRefinementModel,
    SketchGuidedImageGenerationModel,
)
from ...utils import (
    create_compositor_output_node,
    disconnect_world_color_links,
    download_file,
    ensure_compositor_enabled,
    get_compositor_node_tree,
    get_eevee_engine,
    get_world_color,
    has_usable_compositor,
    restore_compositor,
    restore_world_color_links,
    set_world_color,
    snapshot_compositor,
    upload_blender_image,
    upload_file,
)
from ..advanced_params import get_advanced_params_dict
from ..operators import FalOperator
from .utils import (
    calc_scene_depth_bounds,
    get_dimensions,
    overlay_labels,
    render_to_canny,
    render_to_sketch,
)

SKETCH_GUIDED_IMAGE_GENERATION_MODELS = SketchGuidedImageGenerationModel.catalog()
DEPTH_GUIDED_IMAGE_GENERATION_MODELS = DepthGuidedImageGenerationModel.catalog()
EDGE_GUIDED_IMAGE_GENERATION_MODELS = EdgeGuidedImageGenerationModel.catalog()
IMAGE_REFINEMENT_MODELS = ImageRefinementModel.catalog()
DEPTH_VIDEO_MODELS = DepthVideoModel.catalog()
EDGE_VIDEO_MODELS = EdgeVideoModel.catalog()


def _get_scene_duration(scene: bpy.types.Scene) -> float:
    """Calculate the scene duration in seconds from frame range and FPS."""
    fps = scene.render.fps / scene.render.fps_base
    frames = scene.frame_end - scene.frame_start + 1
    return frames / fps


def _get_scene_dimensions(scene: bpy.types.Scene) -> tuple[int, int]:
    """Return the effective render resolution as (width, height)."""
    scale = scene.render.resolution_percentage / 100.0
    return (
        int(scene.render.resolution_x * scale),
        int(scene.render.resolution_y * scale),
    )


class FalRenderOperator(FalOperator):
    """
    Operator for rendering (image and video modes).
    """

    label = "Render"  # text in button in UI

    # Guard against overlapping renders
    _rendering: ClassVar[bool] = False

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Check if the operator is enabled.
        """
        if cls._rendering:
            return False
        if context.scene.camera is None:
            return False

        if props.render_type == "IMAGE":
            if props.mode == "SKETCH":
                return bool(props.sketch_system_prompt.strip() or props.prompt.strip())
            elif props.mode == "REFINE":
                return bool(props.refine_system_prompt.strip() or props.prompt.strip())
            return bool(props.prompt.strip())
        else:  # VIDEO
            return bool(props.prompt.strip())

    @classmethod
    def needs_confirm(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Only video renders confirm — image renders are cheap enough to skip."""
        return props.render_type == "VIDEO"

    @classmethod
    def confirm_title(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> str:
        mode = "depth" if props.video_mode == "DEPTH" else "edge"
        return f"Render animation and submit for {mode} video generation?"

    @classmethod
    def confirm_message(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> str:
        if props.video_mode == "DEPTH":
            model = DEPTH_VIDEO_MODELS.get(props.depth_video_endpoint)
        else:
            model = EDGE_VIDEO_MODELS.get(props.edge_video_endpoint)
        model_label = getattr(model, "display_name", None) or getattr(
            model, "endpoint", "fal.ai model"
        )
        if props.use_scene_duration:
            duration = max(1, int(round(_get_scene_duration(context.scene))))
        else:
            duration = int(props.duration)
        width, height = get_dimensions(context, props)
        scene = context.scene
        frames = scene.frame_end - scene.frame_start + 1
        size_label = (
            model.describe_output_size(width, height) if model else f"{width}x{height}"
        )
        requested = f"{width}x{height}"
        size_detail = (
            f"{size_label} (requested {requested})"
            if size_label != requested
            else size_label
        )
        return (
            f"{model_label} — {duration}s at {size_detail} ({frames} frames). "
            "Rendering the animation locally can take a while, and the fal.ai "
            "job will incur a charge on your account."
        )

    def _merge_advanced_params(self, args: dict[str, Any]) -> dict[str, Any]:
        """Merge advanced params into API arguments.

        Advanced params override model params, allowing power users
        to customize any parameter.
        """
        if self._advanced_params:
            args = {**args, **self._advanced_params}
        return args

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
        if not invoke:
            raise RuntimeError("Render operator should be used as a modal operator")

        self._render_type = props.render_type
        self._prompt = props.prompt
        self._expand_prompt = props.enable_prompt_expansion
        self._render_w, self._render_h = get_dimensions(context, props)

        # Reset modal state
        self._render_done = False
        self._render_cancelled = False
        self._timer = None
        self._saved: dict[str, Any] = {}
        self._sketch_mats: list = []
        self._old_materials: dict = {}
        self._hidden_lights: list = []
        self._saved_compositor: list = []
        self._saved_world_links: list[tuple] = []
        self._tmp_dir: str | None = None
        self._output_path: str | None = None
        self._animation = False
        self._canny_future = None
        self._canny_frames: list = []
        self._parallel_threads = 0
        self._advanced_params = get_advanced_params_dict(props)
        self._cns_kwargs: dict[str, Any] = {}

        if self._render_type == "IMAGE":
            self._mode = props.mode
            self._seed = props.seed

            if self._mode == "DEPTH":
                self._model = DEPTH_GUIDED_IMAGE_GENERATION_MODELS[props.depth_endpoint]
            elif self._mode == "SKETCH":
                self._model = SKETCH_GUIDED_IMAGE_GENERATION_MODELS[
                    props.sketch_endpoint
                ]
            elif self._mode == "EDGE":
                self._model = EDGE_GUIDED_IMAGE_GENERATION_MODELS[props.edge_endpoint]
            else:
                self._model = IMAGE_REFINEMENT_MODELS[props.refine_endpoint]

            self._refine_strength = props.refine_strength
            self._sketch_system_prompt = props.sketch_system_prompt
            self._refine_system_prompt = props.refine_system_prompt
            self._enable_labels = props.enable_labels
            self._auto_label = props.auto_label

            # CNS sampling knobs (consumed only by models that support CNS,
            # e.g. FLUX.2 Klein; ignored by every other refine model).
            self._cns_kwargs = {
                "enable_cns": props.enable_cns,
                "cns_s_churn": props.cns_s_churn,
                "cns_gamma_source": props.cns_gamma_source,
                "cns_power_gamma": props.cns_power_gamma,
                "cns_gamma_divider": props.cns_gamma_divider,
                "cns_alpha_tilt_start": props.cns_alpha_tilt_start,
                "cns_alpha_tilt_end": props.cns_alpha_tilt_end,
                "cns_alpha_use_fnorm": props.cns_alpha_use_fnorm,
                "cns_alpha_exp_interp": props.cns_alpha_exp_interp,
                "cns_alpha_exp_sharpness": props.cns_alpha_exp_sharpness,
                "cns_num_freq_bins": props.cns_num_freq_bins,
                "cns_energy_scale": props.cns_energy_scale,
            }

            # Setup scene for the render
            try:
                if self._mode == "DEPTH":
                    self._setup_depth(context)
                elif self._mode == "SKETCH":
                    self._setup_sketch(context)
                elif self._mode == "EDGE":
                    self._setup_edge(context)
                else:
                    self._setup_refine(context)
            except Exception as e:
                self._restore_state(context)
                self.report({"ERROR"}, f"Render setup failed: {e}")
                return {"CANCELLED"}

        else:  # VIDEO
            self._video_mode = props.video_mode
            self._animation = True

            if self._video_mode == "DEPTH":
                self._model = DEPTH_VIDEO_MODELS[props.depth_video_endpoint]
            else:
                self._model = EDGE_VIDEO_MODELS[props.edge_video_endpoint]
                self._parallel_threads = props.edge_parallel_threads

            # Cache video-specific props
            scene = context.scene
            self._use_first_frame = props.video_use_first_frame
            self._first_frame_source = props.video_image_source
            self._first_frame_path = props.video_image_path
            self._first_frame_texture = props.video_texture

            if props.use_scene_duration:
                self._duration = max(1, int(round(_get_scene_duration(scene))))
            else:
                self._duration = int(props.duration)

            fps = scene.render.fps / scene.render.fps_base
            self._num_frames = max(17, int(self._duration * min(fps, 16)))

            # Map dimensions to supported resolution tiers
            w, h = self._render_w, self._render_h
            if max(w, h) >= 1280:
                self._resolution = "720p"
            elif max(w, h) >= 580:
                self._resolution = "580p"
            else:
                self._resolution = "480p"

            print(f"fal.ai: Video dimensions: {w}x{h} -> {self._resolution}")

            # Pre-capture first-frame image BEFORE depth render
            self._first_frame_url: str | None = None
            if self._use_first_frame:
                self._first_frame_url = self._capture_first_frame()

            try:
                if self._video_mode == "DEPTH":
                    self._setup_depth_video(context)
                else:
                    self._setup_edge_video(context)
            except Exception as e:
                self._restore_state(context)
                self.report({"ERROR"}, f"Render setup failed: {e}")
                return {"CANCELLED"}

        type(self)._rendering = True

        # Register render completion handlers — store refs for clean removal
        self._handler_complete = self._on_complete
        self._handler_cancel = self._on_cancel
        bpy.app.handlers.render_complete.append(self._handler_complete)
        bpy.app.handlers.render_cancel.append(self._handler_cancel)

        # Start non-blocking render
        if self._animation:
            bpy.ops.render.render("INVOKE_DEFAULT", animation=True)
        else:
            bpy.ops.render.render("INVOKE_DEFAULT")

        # Enter modal loop
        wm = context.window_manager
        self._timer = wm.event_timer_add(
            0.25 if not self._animation else 0.5, window=context.window
        )
        wm.modal_handler_add(self._operator_instance)
        self.report({"INFO"}, "Rendering...")
        return {"RUNNING_MODAL"}

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator.
        """
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        # Check if Canny processing is in progress (edge video only)
        if self._canny_future is not None:
            if self._canny_future.done():
                # Canny finished — continue with video encode
                self._canny_future = None
                self._finish_edge_video_encode(context)
                self._cleanup_modal(context)
                return {"FINISHED"}
            # Still processing — keep polling
            return {"PASS_THROUGH"}

        if not (self._render_done or self._render_cancelled):
            return {"PASS_THROUGH"}

        if self._render_cancelled:
            self._cleanup_modal(context)
            self._restore_state(context)
            self.report({"WARNING"}, "Render cancelled")
            return {"CANCELLED"}

        # Render succeeded — dispatch to appropriate finish handler
        if self._render_type == "IMAGE":
            self._cleanup_modal(context)
            if self._mode == "DEPTH":
                self._finish_depth(context)
            elif self._mode == "SKETCH":
                self._finish_sketch(context)
            elif self._mode == "EDGE":
                self._finish_edge(context)
            else:
                self._finish_refine(context)
            return {"FINISHED"}
        else:  # VIDEO
            if self._video_mode == "DEPTH":
                self._cleanup_modal(context)
                self._finish_depth_video(context)
                return {"FINISHED"}
            else:
                # Edge video: start Canny in background, don't cleanup modal yet
                self._start_edge_video_canny(context)
                return {"PASS_THROUGH"}

    # ── Render handlers (called by Blender's render system) ────────────

    def _on_complete(self, *_args: Any) -> None:
        """
        Handler for render completion.
        """
        self._render_done = True

    def _on_cancel(self, *_args: Any) -> None:
        """
        Handler for render cancellation.
        """
        self._render_cancelled = True

    def cancel(self, context: bpy.types.Context) -> None:
        """Called when the operator is cancelled (e.g., user presses ESC)."""
        self._cleanup_modal(context)
        self._restore_state(context)

    def _cleanup_modal(self, context: bpy.types.Context) -> None:
        """
        Clean up the modal state.
        """
        type(self)._rendering = False
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        for ref, handler_list in [
            (self._handler_complete, bpy.app.handlers.render_complete),
            (self._handler_cancel, bpy.app.handlers.render_cancel),
        ]:
            try:
                handler_list.remove(ref)
            except (ValueError, AttributeError):
                pass

    # ── Depth Image Mode — setup / finish ─────────────────────────────

    def _setup_depth(self, context: bpy.types.Context) -> None:
        """
        Configure scene for depth map render via Mist pass + compositor.
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save current settings
        self._saved.update(
            {
                "engine": scene.render.engine,
                "film_transparent": scene.render.film_transparent,
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
                "use_compositing": scene.render.use_compositing,
                "use_pass_mist": view_layer.use_pass_mist,
            }
        )
        # Blender 4.x only: save use_nodes (deprecated in 5.x)
        if bpy.app.version < (5, 0, 0):
            self._saved["use_nodes"] = scene.use_nodes
        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        # Configure render
        scene.render.engine = get_eevee_engine()
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.use_compositing = True
        view_layer.use_pass_mist = True

        # Standard color management — Filmic compresses depth range
        self._saved["view_transform"] = scene.view_settings.view_transform
        self._saved["look"] = scene.view_settings.look
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # Mist range from actual scene depth bounds
        camera = scene.camera
        if camera and world:
            near, far = calc_scene_depth_bounds(scene, camera)
            if near is not None and far is not None:
                # No padding — use the full 0-1 range for actual geometry
                # This gives maximum contrast in the depth map
                world.mist_settings.start = max(0.0, near)
                world.mist_settings.depth = max(0.01, far - near)
                world.mist_settings.falloff = "INVERSE_QUADRATIC"
                print(f"fal.ai: Depth range: {near:.2f} — {far:.2f}m from camera")
            else:
                cam_data = camera.data
                world.mist_settings.start = cam_data.clip_start
                world.mist_settings.depth = cam_data.clip_end - cam_data.clip_start
                world.mist_settings.falloff = "INVERSE_QUADRATIC"

        # Build compositor: Mist → Invert → Composite
        tree = ensure_compositor_enabled(scene)
        self._saved_compositor = snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        rl_node = tree.nodes.new("CompositorNodeRLayers")
        rl_node.location = (0, 0)
        invert_node = tree.nodes.new("CompositorNodeInvert")
        invert_node.location = (300, 0)
        composite_node = create_compositor_output_node(tree)
        composite_node.location = (600, 0)
        tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
        tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

    def _finish_depth(self, context: bpy.types.Context) -> None:
        """
        Save depth render result, restore scene, upload and submit API job.
        """
        render_img = bpy.data.images.get("Render Result")
        if not render_img or not render_img.has_data:
            self._restore_state(context)
            self.report({"ERROR"}, "Depth render failed — no image data")
            return

        depth_path = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_depth_"
        ).name
        try:
            render_img.save_render(depth_path)
        except RuntimeError as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Failed to save depth render: {e}")
            return
        print(f"fal.ai: Depth map saved to {depth_path}")

        # Restore scene state before doing network I/O
        self._restore_state(context)

        args = self._model.parameters(
            image_path=depth_path,
            prompt=self._prompt,
            enable_prompt_expansion=self._expand_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=self._seed if self._seed >= 0 else None,
        )
        args = self._merge_advanced_params(args)

        rw, rh = self._render_w, self._render_h

        def on_complete(job: FalJob):
            _handle_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Render Depth: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Depth rendered — generating image...")

    # ── Sketch Mode — setup / finish ───────────────────────────────────

    def _setup_sketch(self, context: bpy.types.Context) -> None:
        """
        Configure scene for Freestyle sketch render with emission materials.
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world

        # Save render settings
        self._saved.update(
            {
                "engine": scene.render.engine,
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
                "film_transparent": scene.render.film_transparent,
                "use_freestyle": scene.render.use_freestyle,
                "vl_use_freestyle": view_layer.use_freestyle,
                "view_transform": scene.view_settings.view_transform,
                "look": scene.view_settings.look,
            }
        )
        if world:
            self._saved["world_color"] = get_world_color(world)

        # Hide all lights
        self._hidden_lights = []
        for obj in scene.objects:
            if obj.type == "LIGHT" and not obj.hide_render:
                obj.hide_render = True
                self._hidden_lights.append(obj)

        # Assign each object a unique gray emission material
        self._sketch_mats = []
        self._old_materials = {}
        visible_meshes = [
            obj
            for obj in scene.objects
            if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}
            and obj.visible_get()
        ]

        n = max(len(visible_meshes), 1)
        gray_values = []
        for i in range(n):
            if i % 2 == 0:
                gray_values.append(0.9 - (i // 2) * (0.3 / max(n // 2, 1)))
            else:
                gray_values.append(0.4 + (i // 2) * (0.3 / max(n // 2, 1)))

        for idx, obj in enumerate(visible_meshes):
            self._old_materials[obj.name] = [
                (i, slot.material) for i, slot in enumerate(obj.material_slots)
            ]

            g = max(0.3, min(0.95, gray_values[idx % len(gray_values)]))
            mat = bpy.data.materials.new(f"_fal_sketch_{idx}")
            mat.use_nodes = True
            mat_nodes = mat.node_tree.nodes
            mat_nodes.clear()
            emission = mat_nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (g, g, g, 1.0)
            emission.inputs["Strength"].default_value = 1.0
            mat_output = mat_nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(emission.outputs[0], mat_output.inputs[0])
            self._sketch_mats.append(mat)

            for slot in obj.material_slots:
                slot.material = mat
            if not obj.material_slots:
                obj.data.materials.append(mat)
                self._old_materials[obj.name].append((-1, None))

        # Configure render
        scene.render.engine = get_eevee_engine()
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.use_freestyle = True
        view_layer.use_freestyle = True

        # Standard color management (no Filmic dimming)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        # White world background — disconnect any HDRI/texture links first
        # so the default_value actually takes effect
        if world:
            self._saved_world_links = disconnect_world_color_links(world)
            set_world_color(world, (1.0, 1.0, 1.0))

        # Configure Freestyle
        freestyle = view_layer.freestyle_settings
        freestyle.crease_angle = 2.356  # ~135 degrees
        freestyle.as_render_pass = False

        if not freestyle.linesets:
            ls = freestyle.linesets.new("Sketch Lines")
        else:
            ls = freestyle.linesets[0]

        ls.show_render = True
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = True
        ls.select_edge_mark = True
        ls.select_contour = True
        ls.select_external_contour = True
        ls.select_material_boundary = False
        ls.select_suggestive_contour = False

        linestyle = ls.linestyle
        linestyle.color = (0.0, 0.0, 0.0)
        linestyle.thickness = max(2.0, self._render_w / 500.0)
        linestyle.alpha = 1.0

        self._disable_empty_compositor(scene)

    def _finish_sketch(self, context: bpy.types.Context) -> None:
        """
        Save sketch render, post-process, restore scene, add labels, submit.
        """
        render_img = bpy.data.images.get("Render Result")
        if not render_img or not render_img.has_data:
            self._restore_state(context)
            self.report({"ERROR"}, "Sketch render failed — no image data")
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_sketch_"
        ).name
        try:
            render_img.save_render(tmp)
        except RuntimeError as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Failed to save sketch render: {e}")
            return
        print(f"fal.ai: Freestyle sketch saved to {tmp}")

        # Edge detection post-processing (before restore — just PIL work)
        try:
            render_to_sketch(tmp, self._render_w, self._render_h)
            print("fal.ai: Sketch post-processing complete")
        except Exception as e:
            print(f"fal.ai: Sketch post-processing failed, using raw render: {e}")

        # Restore scene state
        self._restore_state(context)

        # Overlay labels (after restore — uses camera projection + geometry)
        if self._enable_labels:
            overlay_labels(
                context, tmp, self._render_w, self._render_h, self._auto_label
            )

        # Show the processed sketch (with labels) as an intermediate result
        import_image_to_editor(tmp, name="fal_sketch_preview")

        # Upload and submit
        seed = self._seed if self._seed >= 0 else None
        args = self._model.parameters(
            prompt=self._prompt.strip(),
            system_prompt=self._sketch_system_prompt.strip(),
            width=self._render_w,
            height=self._render_h,
            seed=seed,
            enable_prompt_expansion=self._expand_prompt,
            image_path=tmp,
        )
        args = self._merge_advanced_params(args)

        rw, rh = self._render_w, self._render_h

        def on_complete(job: FalJob):
            _handle_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Render Sketch: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Sketch rendered — generating image...")

    # ── Refine Mode — setup / finish ───────────────────────────────────

    def _setup_refine(self, context: bpy.types.Context) -> None:
        """
        Configure scene for a normal render (no scene modifications needed).
        """
        scene = context.scene

        # Save render settings so we can restore after
        self._saved.update(
            {
                "res_x": scene.render.resolution_x,
                "res_y": scene.render.resolution_y,
                "res_pct": scene.render.resolution_percentage,
            }
        )

        # Set resolution
        scene.render.resolution_x = self._render_w
        scene.render.resolution_y = self._render_h
        scene.render.resolution_percentage = 100

        self._disable_empty_compositor(scene)

    def _finish_refine(self, context: bpy.types.Context) -> None:
        """
        Save normal render, restore scene, upload and submit for img2img.
        """
        render_img = bpy.data.images.get("Render Result")
        if not render_img or not render_img.has_data:
            self._restore_state(context)
            self.report({"ERROR"}, "Render failed — no image data")
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_refine_"
        ).name
        try:
            render_img.save_render(tmp)
        except RuntimeError as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Failed to save render: {e}")
            return
        print(f"fal.ai: Render saved for refinement: {tmp}")

        # Restore scene state
        self._restore_state(context)

        args = self._model.parameters(
            prompt=self._prompt.strip(),
            system_prompt=self._refine_system_prompt.strip(),
            image_path=tmp,
            strength=self._refine_strength,
            enable_prompt_expansion=self._expand_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=self._seed if self._seed >= 0 else None,
            **self._cns_kwargs,
        )
        args = self._merge_advanced_params(args)

        rw, rh = self._render_w, self._render_h

        def on_complete(job: FalJob):
            _handle_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Render Refine: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report(
            {"INFO"},
            f"Render complete — refining (strength={self._refine_strength:.0%})...",
        )

    # ── Edge Image Mode — setup / finish ──────────────────────────────

    def _setup_edge(self, context: bpy.types.Context) -> None:
        """
        Configure scene for a normal render (same as refine — just override resolution).
        """
        self._setup_refine(context)

    def _finish_edge(self, context: bpy.types.Context) -> None:
        """
        Save normal render, apply Canny edge detection, upload, submit.
        """
        render_img = bpy.data.images.get("Render Result")
        if not render_img or not render_img.has_data:
            self._restore_state(context)
            self.report({"ERROR"}, "Render failed — no image data")
            return

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix="fal_edge_"
        ).name
        try:
            render_img.save_render(tmp)
        except RuntimeError as e:
            self._restore_state(context)
            self.report({"ERROR"}, f"Failed to save render: {e}")
            return
        print(f"fal.ai: Render saved for edge detection: {tmp}")

        # Restore scene state
        self._restore_state(context)

        # Apply Canny edge detection
        try:
            render_to_canny(tmp, self._render_w, self._render_h)
            print("fal.ai: Canny edge detection complete")
        except Exception as e:
            self.report({"ERROR"}, f"Edge detection failed: {e}")
            return

        # Show canny preview
        import_image_to_editor(tmp, name="fal_edge_preview")

        args = self._model.parameters(
            image_path=tmp,
            prompt=self._prompt.strip(),
            enable_prompt_expansion=self._expand_prompt,
            width=self._render_w,
            height=self._render_h,
            seed=self._seed if self._seed >= 0 else None,
        )
        args = self._merge_advanced_params(args)

        rw, rh = self._render_w, self._render_h

        def on_complete(job: FalJob):
            _handle_image_result(job, rw, rh)

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=args,
            on_complete=on_complete,
            label=f"Render Edge: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Edge detected — generating image...")

    # ── Depth Video Mode — setup / finish ─────────────────────────────

    def _setup_depth_video(self, context: bpy.types.Context) -> None:
        """Configure Blender to render a mist/depth pass animation as video."""
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        camera = scene.camera

        self._saved.update(
            {
                "engine": scene.render.engine,
                "film_transparent": scene.render.film_transparent,
                "use_compositing": scene.render.use_compositing,
                "use_pass_mist": view_layer.use_pass_mist,
                "view_transform": scene.view_settings.view_transform,
                "look": scene.view_settings.look,
                "file_format": scene.render.image_settings.file_format,
                "color_mode": scene.render.image_settings.color_mode,
                "filepath": scene.render.filepath,
            }
        )
        # Blender 4.x only: save use_nodes (deprecated in 5.x)
        if bpy.app.version < (5, 0, 0):
            self._saved["use_nodes"] = scene.use_nodes
        # Blender 5.x: save media_type (new in 5.x)
        if bpy.app.version >= (5, 0, 0):
            self._saved["media_type"] = scene.render.image_settings.media_type

        try:
            self._saved["ffmpeg_codec"] = scene.render.ffmpeg.codec
            self._saved["ffmpeg_format"] = scene.render.ffmpeg.format
        except AttributeError:
            pass

        if world:
            self._saved["mist_start"] = world.mist_settings.start
            self._saved["mist_depth"] = world.mist_settings.depth

        self._tmp_dir = tempfile.mkdtemp(prefix="fal_depth_video_")
        self._output_path = os.path.join(self._tmp_dir, "depth")

        scene.render.engine = get_eevee_engine()
        scene.render.film_transparent = False
        scene.render.use_compositing = True

        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        view_layer.use_pass_mist = True

        if camera and world:
            near, far = calc_scene_depth_bounds(scene, camera)
            if near is not None and far is not None:
                padding = (far - near) * 0.05
                world.mist_settings.start = max(0.0, near - padding)
                world.mist_settings.depth = (far - near) + padding * 2
                world.mist_settings.falloff = "INVERSE_QUADRATIC"
                print(f"fal.ai: Depth video range: {near:.2f} — {far:.2f}m")
            else:
                cam_data = camera.data
                world.mist_settings.start = cam_data.clip_start
                world.mist_settings.depth = cam_data.clip_end - cam_data.clip_start
                world.mist_settings.falloff = "INVERSE_QUADRATIC"

        tree = ensure_compositor_enabled(scene)
        self._saved_compositor = snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        rl_node = tree.nodes.new("CompositorNodeRLayers")
        rl_node.location = (0, 0)
        invert_node = tree.nodes.new("CompositorNodeInvert")
        invert_node.location = (300, 0)
        composite_node = create_compositor_output_node(tree)
        composite_node.location = (600, 0)
        tree.links.new(rl_node.outputs["Mist"], invert_node.inputs["Color"])
        tree.links.new(invert_node.outputs["Color"], composite_node.inputs["Image"])

        # Blender 5.x: set media_type to VIDEO first (FFMPEG is now implicit)
        # Blender 4.x: set file_format to FFMPEG
        if bpy.app.version >= (5, 0, 0):
            scene.render.image_settings.media_type = "VIDEO"
        else:
            scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.image_settings.color_mode = "BW"
        scene.render.filepath = self._output_path

    def _finish_depth_video(self, context: bpy.types.Context) -> None:
        """Upload the rendered depth video and submit the fal.ai generation job."""
        result_path = self._output_path + ".mp4"
        if not os.path.exists(result_path) and self._tmp_dir:
            for f in os.listdir(self._tmp_dir):
                if f.endswith(".mp4"):
                    result_path = os.path.join(self._tmp_dir, f)
                    break

        if not os.path.exists(result_path):
            self._restore_state(context)
            self.report({"ERROR"}, f"Depth video not found at {result_path}")
            return

        print(f"fal.ai: Depth video saved to {result_path}")

        self._restore_state(context)

        video_url = upload_file(result_path)
        params = self._model.parameters(
            prompt=self._prompt,
            enable_prompt_expansion=self._expand_prompt,
            video_url=video_url,
            num_frames=self._num_frames,
            image_url=self._first_frame_url,
            resolution=self._resolution,
            width=self._render_w,
            height=self._render_h,
        )
        params = self._merge_advanced_params(params)

        render_w, render_h = self._render_w, self._render_h
        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_video_result(
                job,
                target_width=render_w,
                target_height=render_h,
                scene=origin_scene,
            )

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Depth Video: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Depth rendered — generating video...")

    # ── Edge Video Mode — setup / finish ──────────────────────────────

    def _setup_edge_video(self, context: bpy.types.Context) -> None:
        """Configure Blender to render animation as PNG sequence for Canny processing."""
        scene = context.scene

        self._saved.update(
            {
                "file_format": scene.render.image_settings.file_format,
                "color_mode": scene.render.image_settings.color_mode,
                "filepath": scene.render.filepath,
                "use_compositing": scene.render.use_compositing,
            }
        )
        # Blender 5.x: save media_type
        if bpy.app.version >= (5, 0, 0):
            self._saved["media_type"] = scene.render.image_settings.media_type

        # Disable compositing — we just want a straight render
        scene.render.use_compositing = False

        self._tmp_dir = tempfile.mkdtemp(prefix="fal_edge_video_")
        self._frames_dir = os.path.join(self._tmp_dir, "frames")
        os.makedirs(self._frames_dir, exist_ok=True)
        self._output_path = os.path.join(self._tmp_dir, "edge")

        # Render as PNG image sequence (we'll Canny each frame then re-encode)
        if bpy.app.version >= (5, 0, 0):
            scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.filepath = os.path.join(self._frames_dir, "frame_")

    def _start_edge_video_canny(self, context: bpy.types.Context) -> None:
        """Start background Canny edge detection on rendered frames."""
        # Find rendered PNG frames
        frames = sorted(f for f in os.listdir(self._frames_dir) if f.endswith(".png"))

        if not frames:
            self._restore_state(context)
            self.report({"ERROR"}, "Edge video: no frames rendered")
            return

        # Store frames list for the encode step
        self._canny_frames = frames
        w, h = self._render_w, self._render_h
        frames_dir = self._frames_dir

        # Determine number of parallel workers
        # 0 = auto: use half of CPU cores (leave room for system/Blender)
        num_threads = self._parallel_threads
        if num_threads <= 0:
            cpu_cores = os.cpu_count() or 4
            num_threads = max(1, cpu_cores // 2)

        def process_single_frame(frame_file: str) -> float:
            """Process a single frame, return processing time."""
            frame_path = os.path.join(frames_dir, frame_file)
            frame_start = time.perf_counter()
            try:
                render_to_canny(frame_path, w, h)
            except Exception as e:
                print(f"fal.ai: Canny failed on {frame_file}: {e}")
            return time.perf_counter() - frame_start

        def process_frames_parallel():
            """Process all frames with Canny in parallel and report timing."""
            total_start = time.perf_counter()

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                frame_times = list(executor.map(process_single_frame, frames))

            total_time = time.perf_counter() - total_start
            avg_time = sum(frame_times) / len(frame_times) if frame_times else 0
            print(f"fal.ai: Canny edge detection complete")
            print(f"fal.ai:   Resolution: {w}x{h}")
            print(f"fal.ai:   Frames: {len(frames)}")
            print(f"fal.ai:   Threads: {num_threads}")
            print(f"fal.ai:   Total time: {total_time:.2f}s")
            print(f"fal.ai:   Avg per frame: {avg_time*1000:.1f}ms")
            print(f"fal.ai:   Throughput: {len(frames)/total_time:.1f} fps")

        # Start processing in background thread
        print(
            f"fal.ai: Starting Canny edge detection on {len(frames)} frames ({w}x{h}) with {num_threads} threads..."
        )
        executor = ThreadPoolExecutor(max_workers=1)
        self._canny_future = executor.submit(process_frames_parallel)
        executor.shutdown(wait=False)  # Don't block, let it run in background

    def _finish_edge_video_encode(self, context: bpy.types.Context) -> None:
        """Encode Canny frames to MP4 and submit to fal.ai (called after Canny completes)."""
        frames = self._canny_frames
        if not frames:
            self.report({"ERROR"}, "Edge video: no frames to encode")
            return

        # Restore scene state from first render pass
        self._restore_state(context)

        # Re-encode Canny frames to MP4 using Blender's internal ffmpeg
        # via a compositor-only render pass.
        scene = context.scene
        result_path = self._output_path + ".mp4"

        # Load first Canny frame as a Blender image sequence
        first_frame_path = os.path.join(self._frames_dir, frames[0])
        bpy_img = bpy.data.images.load(first_frame_path)
        bpy_img.source = "SEQUENCE"

        # Save state we'll modify for the encode pass
        encode_saved: dict[str, Any] = {
            "engine": scene.render.engine,
            "use_compositing": scene.render.use_compositing,
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "filepath": scene.render.filepath,
            "film_transparent": scene.render.film_transparent,
        }
        if bpy.app.version >= (5, 0, 0):
            encode_saved["media_type"] = scene.render.image_settings.media_type
        try:
            encode_saved["ffmpeg_codec"] = scene.render.ffmpeg.codec
            encode_saved["ffmpeg_format"] = scene.render.ffmpeg.format
        except AttributeError:
            pass

        # Set up compositor: Image Sequence -> Composite
        tree = ensure_compositor_enabled(scene)
        encode_comp_saved = snapshot_compositor(tree)
        for node in tree.nodes:
            tree.nodes.remove(node)

        img_node = tree.nodes.new("CompositorNodeImage")
        img_node.image = bpy_img
        img_node.frame_duration = len(frames)
        img_node.frame_start = scene.frame_start
        # Offset so scene frame N maps to the Nth Canny frame
        img_node.frame_offset = -(scene.frame_start - 1)

        comp_node = create_compositor_output_node(tree)
        tree.links.new(img_node.outputs["Image"], comp_node.inputs["Image"])

        # Configure for video output using EEVEE (fastest 3D pass)
        scene.render.engine = get_eevee_engine()
        scene.render.film_transparent = True
        scene.render.use_compositing = True
        if bpy.app.version >= (5, 0, 0):
            scene.render.image_settings.media_type = "VIDEO"
        else:
            scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.filepath = self._output_path

        # Synchronous render -- Blender encodes our Canny frames to video
        # using its built-in ffmpeg. The 3D pass is near-free (EEVEE +
        # transparent film) and the compositor replaces it with our frames.
        print(f"fal.ai: Encoding {len(frames)} Canny frames to video...")
        try:
            bpy.ops.render.render(animation=True)
        except Exception as e:
            print(f"fal.ai: Encode render error: {e}")

        # Restore encode-pass state
        for node in tree.nodes:
            tree.nodes.remove(node)
        restore_compositor(tree, encode_comp_saved)

        es = encode_saved
        scene.render.engine = es["engine"]
        scene.render.use_compositing = es["use_compositing"]
        scene.render.film_transparent = es["film_transparent"]
        if "media_type" in es and bpy.app.version >= (5, 0, 0):
            scene.render.image_settings.media_type = es["media_type"]
        scene.render.image_settings.file_format = es["file_format"]
        scene.render.image_settings.color_mode = es["color_mode"]
        scene.render.filepath = es["filepath"]
        try:
            if "ffmpeg_codec" in es:
                scene.render.ffmpeg.codec = es["ffmpeg_codec"]
            if "ffmpeg_format" in es:
                scene.render.ffmpeg.format = es["ffmpeg_format"]
        except AttributeError:
            pass

        # Clean up temp image data block
        bpy.data.images.remove(bpy_img)

        # Fallback: search temp dir for any .mp4 (Blender may name it differently)
        if not os.path.exists(result_path) and self._tmp_dir:
            for f in os.listdir(self._tmp_dir):
                if f.endswith(".mp4"):
                    result_path = os.path.join(self._tmp_dir, f)
                    print(f"fal.ai: Found video at {result_path}")
                    break

        if not os.path.exists(result_path):
            # Debug: list what's actually in the temp dir
            if self._tmp_dir and os.path.exists(self._tmp_dir):
                print(
                    f"fal.ai: Contents of {self._tmp_dir}: {os.listdir(self._tmp_dir)}"
                )
            self.report({"ERROR"}, f"Edge video not found at {result_path}")
            return

        print(f"fal.ai: Edge video saved to {result_path}")

        video_url = upload_file(result_path)
        params = self._model.parameters(
            prompt=self._prompt,
            enable_prompt_expansion=self._expand_prompt,
            video_url=video_url,
            num_frames=self._num_frames,
            image_url=self._first_frame_url,
            resolution=self._resolution,
            width=self._render_w,
            height=self._render_h,
        )
        params = self._merge_advanced_params(params)

        render_w, render_h = self._render_w, self._render_h
        origin_scene = context.scene

        def on_complete(job: FalJob) -> None:
            _handle_video_result(
                job,
                target_width=render_w,
                target_height=render_h,
                scene=origin_scene,
            )

        job = FalJob(
            endpoint=self._model.endpoint,
            arguments=params,
            on_complete=on_complete,
            label=f"Edge Video: {self._prompt[:30]}",
        )
        JobManager.get().submit(job)
        self.report({"INFO"}, "Edge video encoded — generating video...")

    # ── First frame capture (for video modes) ─────────────────────────

    def _capture_first_frame(self) -> str | None:
        """Capture the first-frame image before depth render overwrites state."""
        try:
            if self._first_frame_source == "FILE":
                if not self._first_frame_path.strip():
                    return None
                return upload_file(self._first_frame_path)
            elif self._first_frame_source == "TEXTURE":
                img = self._first_frame_texture  # Already an Image object
                if not img:
                    return None
                return upload_blender_image(img)
            else:  # RENDER
                render_img = bpy.data.images.get("Render Result")
                if not render_img or not render_img.has_data:
                    print("fal.ai: No render result available for first frame")
                    return None
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False, prefix="fal_first_frame_"
                )
                tmp.close()
                try:
                    render_img.save_render(tmp.name)
                except RuntimeError as e:
                    print(f"fal.ai: Failed to save first frame: {e}")
                    return None
                print(f"fal.ai: First frame captured to {tmp.name}")
                return upload_file(tmp.name)
        except Exception as e:
            print(f"fal.ai: Failed to capture first frame: {e}")
            return None

    def _disable_empty_compositor(self, scene: bpy.types.Scene) -> None:
        """Turn off ``use_compositing`` when the tree has no output node.

        Blender 5.x fresh scenes default ``use_compositing=True`` with an
        empty compositor group, which makes ``bpy.ops.render.render()`` raise
        "No Group Output or File Output nodes in scene". Setup paths that
        don't build their own compositor (refine, sketch) would otherwise hit
        this.
        """
        if scene.render.use_compositing and not has_usable_compositor(scene):
            self._saved.setdefault("use_compositing", scene.render.use_compositing)
            scene.render.use_compositing = False

    # ── Unified state restoration ──────────────────────────────────────

    def _restore_state(self, context: bpy.types.Context) -> None:
        """
        Restore all saved scene state (works for all modes).
        """
        scene = context.scene
        view_layer = context.view_layer
        world = scene.world
        s = self._saved

        # Restore compositor
        tree = get_compositor_node_tree(scene)
        if self._saved_compositor and tree:
            for node in tree.nodes:
                tree.nodes.remove(node)
            restore_compositor(tree, self._saved_compositor)
            self._saved_compositor = []

        # Restore render settings
        if "engine" in s:
            scene.render.engine = s["engine"]
        if "film_transparent" in s:
            scene.render.film_transparent = s["film_transparent"]
        if "res_x" in s:
            scene.render.resolution_x = s["res_x"]
        if "res_y" in s:
            scene.render.resolution_y = s["res_y"]
        if "res_pct" in s:
            scene.render.resolution_percentage = s["res_pct"]
        if "use_compositing" in s:
            scene.render.use_compositing = s["use_compositing"]
        # Blender 4.x only: restore use_nodes (deprecated in 5.x)
        if "use_nodes" in s and bpy.app.version < (5, 0, 0):
            scene.use_nodes = s["use_nodes"]
        if "use_pass_mist" in s:
            view_layer.use_pass_mist = s["use_pass_mist"]

        # Mist settings
        if world:
            if "mist_start" in s:
                world.mist_settings.start = s["mist_start"]
            if "mist_depth" in s:
                world.mist_settings.depth = s["mist_depth"]

        # View settings
        if "view_transform" in s:
            scene.view_settings.view_transform = s["view_transform"]
        if "look" in s:
            scene.view_settings.look = s["look"]
        if "world_color" in s and world:
            set_world_color(world, s["world_color"])
        if self._saved_world_links and world:
            restore_world_color_links(world, self._saved_world_links)
            self._saved_world_links = []
        if "use_freestyle" in s:
            scene.render.use_freestyle = s["use_freestyle"]
        if "vl_use_freestyle" in s:
            view_layer.use_freestyle = s["vl_use_freestyle"]

        # Video render settings
        # Blender 5.x: restore media_type first (affects available file_format values)
        if "media_type" in s and bpy.app.version >= (5, 0, 0):
            scene.render.image_settings.media_type = s["media_type"]
        if "file_format" in s:
            scene.render.image_settings.file_format = s["file_format"]
        if "color_mode" in s:
            scene.render.image_settings.color_mode = s["color_mode"]
        if "filepath" in s:
            scene.render.filepath = s["filepath"]

        try:
            if "ffmpeg_codec" in s:
                scene.render.ffmpeg.codec = s["ffmpeg_codec"]
            if "ffmpeg_format" in s:
                scene.render.ffmpeg.format = s["ffmpeg_format"]
        except AttributeError:
            pass

        # Sketch-specific: restore materials
        for obj_name, mat_list in self._old_materials.items():
            obj = scene.objects.get(obj_name)
            if not obj:
                continue
            for slot_idx, orig_mat in mat_list:
                if slot_idx == -1:
                    if obj.data.materials:
                        obj.data.materials.pop()
                elif slot_idx < len(obj.material_slots):
                    obj.material_slots[slot_idx].material = orig_mat
        self._old_materials.clear()

        for mat in self._sketch_mats:
            bpy.data.materials.remove(mat)
        self._sketch_mats.clear()

        # Restore lights
        for obj in self._hidden_lights:
            obj.hide_render = False
        self._hidden_lights.clear()

        self._saved.clear()


# ---------------------------------------------------------------------------
# Result handlers (module-level — must not reference operator self)
# ---------------------------------------------------------------------------
def _handle_image_result(
    job: FalJob,
    render_w: int = 0,
    render_h: int = 0,
) -> None:
    """Download generated image and load into Blender."""
    if job.status == "error":
        print(f"fal.ai: Render failed: {job.error}")
        return

    result = job.result or {}
    image_url = None

    if "images" in result and result["images"]:
        image_url = result["images"][0].get("url")
    elif "image" in result:
        img = result["image"]
        image_url = img.get("url") if isinstance(img, dict) else img
    elif "output" in result:
        out = result["output"]
        if isinstance(out, dict) and "url" in out:
            image_url = out["url"]

    if not image_url:
        print("fal.ai: No image in response")
        return

    local_path = download_file(image_url, suffix=".png")
    if render_w > 0 and render_h > 0:
        resize_image_to_target(local_path, render_w, render_h)
    import_image_to_editor(local_path, name="fal_render")
    print("fal.ai: Render complete!")


def _notify_video_ready(job_label: str) -> None:
    """Show a one-shot popup so the user knows the generated video is in the VSE.

    Called from ``JobManager._poll`` (main thread timer), so ``popup_menu`` is
    safe. Best-effort — if no window is available we just fall back to stdout.
    """
    lines = [
        "Video added to the VSE at the current frame.",
        "Switch to the Video Editing workspace to preview it.",
    ]

    def draw(menu: Any, _context: bpy.types.Context) -> None:
        menu.layout.label(text=f"✓ {job_label} complete")
        for line in lines:
            menu.layout.label(text=line)

    try:
        bpy.context.window_manager.popup_menu(
            draw, title="fal.ai — Video Ready", icon="FILE_MOVIE"
        )
    except Exception as e:
        print(f"fal.ai: Could not show video-ready popup: {e}")


def _handle_video_result(
    job: FalJob,
    *,
    target_width: int | None = None,
    target_height: int | None = None,
    scene: bpy.types.Scene | None = None,
) -> None:
    """Download video result and import to VSE, scaled to the requested target."""
    if job.status == "error":
        print(f"fal.ai: Video generation failed: {job.error}")
        return

    result = job.result or {}
    video_url = None
    for key in ["video", "output", "video_url"]:
        val = result.get(key)
        if isinstance(val, dict) and "url" in val:
            video_url = val["url"]
            break
        elif isinstance(val, str) and val.startswith("http"):
            video_url = val
            break

    if not video_url:
        print("fal.ai: No video in response")
        return

    local_path = download_file(video_url, suffix=".mp4")
    add_video_to_vse(
        local_path,
        name="fal_video",
        target_width=target_width,
        target_height=target_height,
        scene=scene,
    )
    print("fal.ai: Video imported to VSE!")
    _notify_video_ready(job.label or "Video")
