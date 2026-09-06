"""H3 viewport experiments: main-thread capture/playback, isolated HTTP worker."""

import base64
import hashlib
from array import array
import json
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from .preferences import get_api_key, get_output_dir

ENDPOINT = "https://fal.run/minimax/h3-max-turbo/image-to-video"
_session = None
_preview = None
_worker = None


def _image_uri(image_bytes):
    mime = "image/jpeg" if image_bytes.startswith(b"\xff\xd8") else "image/png"
    return "data:" + mime + ";base64," + base64.b64encode(image_bytes).decode()


def build_payload(image_bytes, prompt, resolution, end_image_bytes=None, reference_mode=False, style_image_bytes=None):
    if not prompt.strip():
        raise ValueError("Enter a motion prompt")
    if resolution not in {"480P", "768P"}:
        raise ValueError("Unsupported resolution")
    payload = dict(prompt=prompt.strip(), duration=5, resolution=resolution,
                prompt_expansion_mode="balanced", enable_safety_checker=True, sync_mode=False)
    if reference_mode:
        payload["reference_image_urls"] = [_image_uri(image_bytes)]
        if style_image_bytes is not None:
            payload["reference_image_urls"].append(_image_uri(style_image_bytes))
        payload["aspect_ratio"] = "16:9"
    else:
        if style_image_bytes is not None:
            raise ValueError("Style references require reference mode")
        payload["image_url"] = _image_uri(image_bytes)
    if end_image_bytes is not None:
        if reference_mode:
            raise ValueError("Reference mode has no last-frame field")
        payload["end_image_url"] = _image_uri(end_image_bytes)
    return payload


def generate(key, payload, folder, events, token, capture_seconds, endpoint=ENDPOINT):
    """No bpy access here. One POST, no automatic retries after uncertain completion."""
    started = time.perf_counter()
    try:
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                    headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
            request_id = response.headers.get("x-fal-request-id")
        api_seconds = time.perf_counter() - started
        url = result.get("video", {}).get("url")
        if not url or not url.startswith("https://"):
            raise ValueError("No HTTPS video returned")
        events.put((token, "status", "Downloading generated clip"))
        path = Path(folder) / ("h3-live-" + uuid.uuid4().hex[:12] + ".mp4")
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
        total = time.perf_counter() - started
        metadata = dict(model=endpoint.removeprefix("https://fal.run/"),
                        request_id=request_id, resolution=payload["resolution"], duration=5,
                        prompt=payload["prompt"], expanded_prompt=result.get("expanded_prompt"),
                        seed=result.get("seed", payload.get("seed")), provider_timings=result.get("timings"),
                        conditioning="reference" if "reference_image_urls" in payload else ("first_last" if "end_image_url" in payload else "first"),
                        capture_seconds=capture_seconds, api_seconds=api_seconds,
                        download_seconds=total-api_seconds, total_seconds=total+capture_seconds,
                        video_path=str(path))
        path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
        events.put((token, "complete", metadata))
    except urllib.error.HTTPError as exc:
        events.put((token, "error", f"fal HTTP {exc.code}; stopped. Check your fal dashboard before retrying."))
    except Exception as exc:
        # Never include request headers, credentials, or an arbitrary server response.
        events.put((token, "error", f"{type(exc).__name__}: request/download failed; no automatic retry."))


class H3LiveProperties(bpy.types.PropertyGroup):
    grid_guidance: bpy.props.EnumProperty(name="Image guidance", items=[('PER_STYLE_TEXT','Cartoon / clay / real / painted','Same fixed-camera geometry inputs; style described in text to avoid swatch leakage'),('PER_STYLE','Measured per-style / fixed camera','Image-only recipes for the four styles; orbital remains experimental'),('IMAGE','Full frame','Full geometry image and fixed style reference'),('DETAIL','Full frame + 3×3 details','Aspect-preserved detail crops; full frame stays authoritative'),('MATERIAL','Material replacement + details','Stronger surface-only instructions; experimental')], default='IMAGE')
    grid_seed: bpy.props.IntProperty(name="Fixed seed", default=73419, min=0)
    style_manifest: bpy.props.StringProperty(name="Fixed style references", subtype='FILE_PATH', default=str(Path(__file__).parent/'assets'/'h3-style-references'/'manifest.json'))
    preview_mode: bpy.props.EnumProperty(name="Preview model", items=[("I2V", "Turbo / anchored first frame", ""), ("REFERENCE", "H3 Max / interpret gray geometry", "")], default="I2V")
    source_format: bpy.props.EnumProperty(name="Capture", items=[("PNG", "PNG / 848px", ""), ("JPEG", "Small JPEG / 512px", "")], default="PNG")
    prompt: bpy.props.StringProperty(name="Motion prompt", default="Fixed camera. Preserve the input projection, framing, object position and size. No zoom, pan, tilt, orbit or object motion. Only subtle environmental motion outside the object.")
    resolution: bpy.props.EnumProperty(name="Resolution", items=[("480P", "480p / fast", ""), ("768P", "768p", "")], default="480P")
    max_requests: bpy.props.IntProperty(name="Session clip limit", default=10, min=1, max=100)
    settle_seconds: bpy.props.FloatProperty(name="Wait after changes", default=0.8, min=0.3, max=10, subtype="TIME")
    status: bpy.props.StringProperty(default="Ready — capture the viewport to animate it", options={"SKIP_SAVE"})
    stream_status: bpy.props.StringProperty(default="Ready for camera animation", options={"SKIP_SAVE"})
    timing: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    last_video: bpy.props.StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})


def _geometry_digest(scene):
    """Hash evaluated surfaces, not dependency-graph invalidation notifications.

    Capturing changes render settings and invalidates geometry without editing it.
    Content comparison also detects vertex edits that leave object transforms intact.
    This prototype favors correctness over performance on very large scenes.
    """
    digest = hashlib.blake2b(digest_size=16)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            coords = array('f', [0]) * (len(mesh.vertices) * 3)
            indices = array('i', [0]) * len(mesh.loops)
            mesh.vertices.foreach_get('co', coords)
            mesh.loops.foreach_get('vertex_index', indices)
            digest.update(obj.name.encode())
            digest.update(coords.tobytes())
            digest.update(indices.tobytes())
        finally:
            evaluated.to_mesh_clear()
    return digest.digest()


def _signature(session):
    space = session["area"].spaces.active
    scene = session["scene"]
    rv = space.region_3d
    values = [round(v, 4) for row in rv.view_matrix for v in row]
    values += [rv.view_distance, rv.view_camera_zoom, *rv.view_camera_offset, space.lens]
    for obj in scene.objects:
        values += [obj.name, obj.hide_viewport, obj.hide_render]
        values += [round(v, 4) for row in obj.matrix_world for v in row]
    props = scene.fal_h3_live
    return tuple(values) + (scene.frame_current, props.prompt, props.resolution, props.preview_mode, props.source_format, props.grid_guidance, props.grid_seed, _geometry_digest(scene))


def _capture(session, camera_view=False):
    scene, area, window = session["scene"], session["area"], session["window"]
    render = scene.render
    names = ("resolution_x", "resolution_y", "resolution_percentage", "filepath", "film_transparent", "use_sequencer", "use_compositing")
    saved = {name: getattr(render, name) for name in names}
    image_format = render.image_settings.file_format
    quality = render.image_settings.quality
    overlays = area.spaces.active.overlay.show_overlays
    region = next(r for r in area.regions if r.type == "WINDOW")
    jpeg = scene.fal_h3_live.source_format == "JPEG"
    path = Path(session["folder"]) / ("h3-input-" + uuid.uuid4().hex[:12] + (".jpg" if jpeg else ".png"))
    try:
        render.resolution_x, render.resolution_y, render.resolution_percentage = (512, 290, 100) if jpeg else (848, 480, 100)
        render.filepath = str(path)
        render.film_transparent = False
        render.use_sequencer = False
        render.use_compositing = False
        render.image_settings.file_format = "JPEG" if jpeg else "PNG"
        render.image_settings.quality = 80
        bpy.app.driver_namespace["fal_capture_active"] = True
        area.spaces.active.overlay.show_overlays = False
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.render.opengl(write_still=True, view_context=not camera_view)
        return path.read_bytes()
    finally:
        for name, value in saved.items():
            setattr(render, name, value)
        render.image_settings.file_format = image_format
        render.image_settings.quality = quality
        bpy.app.driver_namespace["fal_capture_active"] = False
        area.spaces.active.overlay.show_overlays = overlays


def _play(path, window):
    global _preview
    area = next((a for a in window.screen.areas if a.type == "CLIP_EDITOR"), None)
    if area is None:
        return
    old_clip = _preview["clip"] if _preview else None
    clip = bpy.data.movieclips.load(path, check_existing=True)
    area.spaces.active.clip = clip
    area.spaces.active.mode = "TRACKING"
    area.spaces.active.show_region_ui = False
    area.spaces.active.show_region_toolbar = False
    _preview = dict(area=area, clip=clip, started=time.perf_counter())
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.clip.view_all(fit_view=True)
    if old_clip and old_clip != clip and old_clip.users == 0:
        bpy.data.movieclips.remove(old_clip)


def _tick():
    global _session, _preview, _worker
    if _preview:
        try:
            p = _preview
            if p["area"].type != "CLIP_EDITOR":
                _preview = None
            else:
                frame = int((time.perf_counter()-p["started"])*p["clip"].fps)
                p["area"].spaces.active.clip_user.frame_current = 1 + frame % max(1, p["clip"].frame_duration)
                p["area"].tag_redraw()
        except (ReferenceError, RuntimeError, AttributeError):
            _preview = None
    s = _session
    if s:
        try:
            if s["window"].scene != s["scene"] or s["area"].type != "VIEW_3D":
                raise RuntimeError("Source viewport changed; start a new preview session")
            props = s["scene"].fal_h3_live
            while not s["events"].empty():
                token, kind, data = s["events"].get_nowait()
                if token != s["token"]:
                    continue
                if kind == "status":
                    props.status = data
                elif kind == "error":
                    props.status = data
                    _session = None
                    break
                else:
                    s["busy"] = False
                    if _signature(s) != s["submitted"]:
                        props.status = "Geometry changed — discarding obsolete result"
                        if s["count"] >= props.max_requests:
                            _session = None
                        continue
                    props.last_video = data["video_path"]
                    inference = (data["provider_timings"] or {}).get("inference")
                    gpu = f"{inference:.3f}s" if isinstance(inference, (int, float)) else "n/a"
                    props.timing = f"GPU {gpu} | API {data['api_seconds']:.2f}s | total {data['total_seconds']:.2f}s"
                    _play(data["video_path"], s["window"])
                    props.status = f"Clip {s['count']} ready — move the view to refresh"
                    if not s["auto"] or s["count"] >= props.max_requests:
                        props.status = f"Clip {s['count']} ready — session finished"
                        _session = None
            if _session is s:
                sig = _signature(s)
                now = time.perf_counter()
                if sig != s["observed"]:
                    s["observed"], s["changed"] = sig, now
                if not s["busy"] and sig != s["submitted"] and now-s["changed"] >= props.settle_seconds:
                    props.status = "Capturing viewport"
                    start = time.perf_counter()
                    image = _capture(s)
                    reference = props.preview_mode == "REFERENCE"
                    payload = build_payload(image, props.prompt, props.resolution, reference_mode=reference)
                    endpoint = "https://fal.run/minimax/h3-max/reference-to-video" if reference else ENDPOINT
                    s["submitted"], s["busy"] = _signature(s), True
                    s["count"] += 1
                    props.status = f"Generating clip {s['count']} / {props.max_requests}"
                    _worker = threading.Thread(target=generate, args=(s["key"], payload, s["folder"], s["events"], s["token"], time.perf_counter()-start, endpoint), daemon=True)
                    _worker.start()
            s["area"].tag_redraw()
        except Exception as exc:
            try:
                s["scene"].fal_h3_live.status = f"Preview stopped: {type(exc).__name__}: {exc}"
            except ReferenceError:
                pass
            _session = None
    return 1/24


class FAL_OT_H3Layout(bpy.types.Operator):
    bl_idname = "fal.h3_layout"
    bl_label = "Open side-by-side preview"

    def execute(self, context):
        if any(a.type == "CLIP_EDITOR" for a in context.screen.areas):
            return {"FINISHED"}
        original = context.area
        if original.type != "VIEW_3D":
            return {"CANCELLED"}
        before = {a.as_pointer() for a in context.screen.areas}
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.52)
        added = next(a for a in context.screen.areas if a.as_pointer() not in before)
        right = max((original, added), key=lambda a: a.x)
        right.type = "CLIP_EDITOR"
        return {"FINISHED"}


class FAL_OT_H3Start(bpy.types.Operator):
    bl_idname = "fal.h3_start"
    bl_label = "Start live preview"
    bl_description = "Send viewport images to fal after changes settle; each clip is a paid generation"
    auto: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        global _session
        from . import live_stream, live_grid
        if live_grid._session or any(w.is_alive() for w in live_grid._workers):
            self.report({"WARNING"}, "Stop the grid and wait for its requests to finish")
            return {"CANCELLED"}
        if live_stream._stream or any(w.is_alive() for w in live_stream._workers):
            self.report({"WARNING"}, "Stop the camera stream and wait for its requests to finish")
            return {"CANCELLED"}
        if _session:
            return {"CANCELLED"}
        if _worker and _worker.is_alive():
            self.report({"WARNING"}, "Previous request is still finishing; wait before starting another")
            return {"CANCELLED"}
        key = get_api_key()
        if not key or not bpy.app.online_access:
            self.report({"ERROR"}, "Configure a fal key and enable Blender online access")
            return {"CANCELLED"}
        if context.area.type != "VIEW_3D" or not context.scene.fal_h3_live.prompt.strip():
            self.report({"ERROR"}, "Use a 3D viewport and enter a motion prompt")
            return {"CANCELLED"}
        _session = dict(window=context.window, area=context.area, scene=context.scene,
                        auto=self.auto, key=key, folder=get_output_dir(), events=queue.Queue(),
                        token=uuid.uuid4().hex, count=0, busy=False, observed=None,
                        submitted=None, changed=time.perf_counter())
        context.scene.fal_h3_live.status = "Waiting for viewport to settle"
        return {"FINISHED"}


class FAL_OT_H3Stop(bpy.types.Operator):
    bl_idname = "fal.h3_stop"
    bl_label = "Stop"
    bl_description = "Stop new requests; an already submitted generation may still be billed"

    def execute(self, context):
        global _session
        _session = None
        context.scene.fal_h3_live.status = "Stopped — any submitted request may finish on fal"
        return {"FINISHED"}


class FAL_PT_H3Live(bpy.types.Panel):
    bl_label = "H3 Max Turbo · Live Preview"
    bl_idname = "FAL_PT_H3Live"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "H3 Live"

    def draw(self, context):
        layout = self.layout
        p = context.scene.fal_h3_live
        layout.label(text="Viewport → 5-second AI video", icon="CAMERA_DATA")
        layout.operator("fal.h3_layout", icon="WINDOW")
        layout.prop(p, "prompt")
        layout.prop(p, "preview_mode")
        layout.prop(p, "source_format")
        layout.prop(p, "resolution")
        layout.prop(p, "settle_seconds")
        layout.prop(p, "max_requests")
        grid = layout.box()
        grid.label(text="Four styles / four requests per batch")
        grid.prop(p, 'style_manifest')
        grid.prop(p, 'grid_guidance')
        grid.prop(p, 'grid_seed')
        grid.operator('fal.h3_grid_layout', icon='WINDOW')
        grid.operator('fal.h3_grid_start', icon='PLAY')
        grid.operator('fal.h3_grid_stop', icon='PAUSE')
        if _session:
            layout.operator("fal.h3_stop", icon="PAUSE")
        else:
            row = layout.row(align=True)
            row.operator("fal.h3_start", text="Capture once", icon="RENDER_ANIMATION").auto = False
            row.operator("fal.h3_start", text="Auto refresh", icon="PLAY").auto = True
        box = layout.box()
        for offset in range(0, len(p.status), 42):
            box.label(text=p.status[offset:offset+42])
        if p.timing:
            for part in p.timing.split(" | "):
                box.label(text=part)
        layout.label(text="Each capture sends an image to fal.")
        layout.label(text="Paid clips; auto stops at session limit.")
        layout.label(text="AI motion can diverge from the scene.")


@persistent
def _on_load(_):
    global _session, _preview
    _session = _preview = None


_classes = (H3LiveProperties, FAL_OT_H3Layout, FAL_OT_H3Start, FAL_OT_H3Stop, FAL_PT_H3Live)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fal_h3_live = bpy.props.PointerProperty(type=H3LiveProperties)
    bpy.app.handlers.load_pre.append(_on_load)
    bpy.app.timers.register(_tick, persistent=True)


def unregister():
    _on_load(None)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for handlers, fn in ((bpy.app.handlers.load_pre, _on_load),):
        if fn in handlers:
            handlers.remove(fn)
    del bpy.types.Scene.fal_h3_live
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
