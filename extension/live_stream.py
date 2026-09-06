"""Camera-animation look-ahead with paired base64 frames and ordered playback."""
import json
import queue
import threading
import time
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from . import live_preview
from .preferences import get_api_key, get_output_dir
from .stream_buffer import ClipBuffer

_stream = None
_workers = []


def capture_pair(session, first, last):
    """Restore the timeline on failure. Reuse the exact shared boundary PNG."""
    scene = session["scene"]
    original = scene.frame_current
    start = time.perf_counter()
    try:
        if session.get("boundary_frame") == first:
            first_image = session["boundary_image"]
        else:
            scene.frame_set(first)
            first_image = live_preview._capture(session, camera_view=True)
        scene.frame_set(last)
        last_image = live_preview._capture(session, camera_view=True)
        session["boundary_frame"], session["boundary_image"] = last, last_image
        return first_image, last_image, time.perf_counter()-start
    finally:
        scene.frame_set(original)


def _show(session, metadata):
    area = session["preview_area"]
    old = session.get("playing")
    clip = bpy.data.movieclips.load(metadata["video_path"], check_existing=True)
    area.spaces.active.clip = clip
    area.spaces.active.show_region_ui = False
    area.spaces.active.show_region_toolbar = False
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=session["window"], area=area, region=region):
        bpy.ops.clip.view_all(fit_view=True)
    session["playing"] = dict(clip=clip, metadata=metadata, started=time.perf_counter(), underrun=False)
    session["history"].append(metadata)
    if old and old["clip"].users == 0:
        bpy.data.movieclips.remove(old["clip"])
    p = session["scene"].fal_h3_live
    p.last_video = metadata["video_path"]
    gpu = (metadata.get("provider_timings") or {}).get("inference")
    gpu_text = f"{gpu:.3f}s" if isinstance(gpu, (int, float)) else "n/a"
    p.timing = f"GPU {gpu_text} | API {metadata['api_seconds']:.2f}s | total {metadata['total_seconds']:.2f}s"


def _write_status(s, message, force=False):
    s["scene"].fal_h3_live.stream_status = message
    if force or time.perf_counter()-s["last_log"] >= 1:
        data = dict(status=message, submitted=s["submitted"], completed=s["completed"],
                    buffered=len(s["buffer"]), in_flight=len(s["pending"]),
                    playing=s["playing"]["metadata"]["index"] if s["playing"] else None,
                    underruns=s["underruns"], history=s["history"])
        Path(s["folder"], "stream-status.json").write_text(json.dumps(data, indent=2), encoding="utf8")
        s["last_log"] = time.perf_counter()


def _tick():
    global _stream
    s = _stream
    if not s:
        return 1/24
    try:
        if s["window"].scene != s["scene"] or s["area"].type != "VIEW_3D" or s["preview_area"].type != "CLIP_EDITOR":
            raise RuntimeError("Scene or preview editor changed")
        p = s["scene"].fal_h3_live
        while not s["events"].empty():
            index, kind, data = s["events"].get_nowait()
            if kind == "error":
                raise RuntimeError(data)
            if kind == "complete":
                data.update(index=index, first_frame=s["pending"][index]["first"], last_frame=s["pending"][index]["last"])
                Path(data["video_path"]).with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf8")
                s["buffer"].put(index, data)
                del s["pending"][index]
                s["completed"] += 1
        finished = s["submitted"] >= s["limit"] and not s["pending"]
        playing = s["playing"]
        if playing:
            elapsed = time.perf_counter()-playing["started"]
            duration = playing["clip"].frame_duration/max(1, playing["clip"].fps)
            frame = min(playing["clip"].frame_duration, 1+int(elapsed*playing["clip"].fps))
            s["preview_area"].spaces.active.clip_user.frame_current = frame
            source_frame = min(playing["metadata"]["last_frame"], playing["metadata"]["first_frame"]+int(min(elapsed, duration)*s["fps"]))
            if s["scene"].frame_current != source_frame:
                s["scene"].frame_set(source_frame)
            if elapsed >= duration:
                next_clip = s["buffer"].pop(final=finished)
                if next_clip:
                    _show(s, next_clip)
                elif finished:
                    _write_status(s, f"Finished: {s['completed']} clips / {s['underruns']} buffer waits", force=True)
                    _stream = None
                elif not playing["underrun"]:
                    playing["underrun"] = True
                    s["underruns"] += 1
        else:
            next_clip = s["buffer"].pop(final=finished)
            if next_clip:
                _show(s, next_clip)
        if _stream is s:
            # Two HTTP requests and three queued/in-flight clips at most.
            if s["submitted"] < s["limit"] and len(s["pending"]) < 2 and len(s["buffer"])+len(s["pending"]) < 3:
                index = s["submitted"]
                first = s["start_frame"] + index*s["step"]
                last = first+s["step"]
                p.stream_status = f"Capturing keyframes {first} → {last}"
                first_image, last_image, capture_seconds = capture_pair(s, first, last)
                payload = live_preview.build_payload(first_image, p.prompt, p.resolution, last_image)
                s["pending"][index] = dict(first=first, last=last)
                s["submitted"] += 1
                worker = threading.Thread(target=live_preview.generate,
                    args=(s["key"], payload, s["folder"], s["events"], index, capture_seconds), daemon=True)
                _workers.append(worker)
                worker.start()
            _workers[:] = [w for w in _workers if w.is_alive()]
            state = "Playing" if s["playing"] else "Prefilling"
            current = s["playing"]["metadata"]["index"]+1 if s["playing"] else 0
            _write_status(s, f"{state} {current}/{s['limit']} | buffer {len(s['buffer'])} | requests {len(s['pending'])} | waits {s['underruns']}")
        s["area"].tag_redraw()
        s["preview_area"].tag_redraw()
    except Exception as exc:
        try:
            _write_status(s, f"Stream stopped: {exc}", force=True)
        except Exception:
            pass
        _stream = None
    return 1/24


class FAL_OT_H3StreamStart(bpy.types.Operator):
    bl_idname = "fal.h3_stream_start"
    bl_label = "Stream camera animation"
    bl_description = "Capture first/last camera frames ahead of playback; two parallel requests and an ordered video buffer"

    def execute(self, context):
        global _stream
        from . import live_grid
        if live_grid._session or any(w.is_alive() for w in live_grid._workers):
            self.report({'WARNING'}, 'Stop the grid and wait for its requests to finish')
            return {'CANCELLED'}
        if _stream or live_preview._session or any(w.is_alive() for w in _workers) or (live_preview._worker and live_preview._worker.is_alive()):
            self.report({"WARNING"}, "Stop the existing preview and wait for its requests to finish")
            return {"CANCELLED"}
        scene = context.scene
        if not scene.camera or context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Use a viewport in a scene with an animated camera")
            return {"CANCELLED"}
        preview = next((a for a in context.screen.areas if a.type == "CLIP_EDITOR"), None)
        key = get_api_key()
        if not preview or not key or not bpy.app.online_access:
            self.report({"ERROR"}, "Open the side-by-side preview and configure online access and a fal key")
            return {"CANCELLED"}
        p = scene.fal_h3_live
        if not p.prompt.strip():
            self.report({"ERROR"}, "Enter a motion prompt")
            return {"CANCELLED"}
        live_preview._preview = None
        fps = scene.render.fps/scene.render.fps_base
        step = round(5*fps)
        available = (scene.frame_end-scene.frame_current)//step
        limit = min(p.max_requests, available)
        if limit < 1:
            self.report({"ERROR"}, "Need at least five seconds remaining in the scene frame range")
            return {"CANCELLED"}
        _stream = dict(window=context.window, scene=scene, area=context.area, preview_area=preview,
                       folder=get_output_dir(), key=key, events=queue.Queue(), buffer=ClipBuffer(2),
                       pending={}, submitted=0, completed=0, playing=None, start_frame=scene.frame_current,
                       step=step, fps=fps, limit=limit, underruns=0, history=[], last_log=0)
        p.stream_status = "Capturing first/last frames; preparing two clips"
        return {"FINISHED"}


class FAL_OT_H3StreamStop(bpy.types.Operator):
    bl_idname = "fal.h3_stream_stop"
    bl_label = "Stop stream"

    def execute(self, context):
        global _stream
        if _stream:
            _write_status(_stream, "Stopped; submitted requests may finish, no further captures", force=True)
        _stream = None
        return {"FINISHED"}


class FAL_PT_H3Stream(bpy.types.Panel):
    bl_idname = "FAL_PT_H3Stream"
    bl_label = "First + Last Frame Stream"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "H3 Live"
    bl_order = -10

    def draw(self, context):
        layout = self.layout
        p = context.scene.fal_h3_live
        layout.label(text="Animated camera → paired base64 frames")
        layout.prop(p, "max_requests")
        if _stream:
            layout.operator("fal.h3_stream_stop", icon="PAUSE")
        else:
            layout.operator("fal.h3_stream_start", icon="PLAY")
        for line in p.stream_status.split(" | "):
            layout.label(text=line)
        layout.label(text="2 parallel requests · 2-clip prefill")
        layout.label(text="Source timeline follows generated playback")


@persistent
def _on_load(_):
    global _stream
    _stream = None


_classes = (FAL_OT_H3StreamStart, FAL_OT_H3StreamStop, FAL_PT_H3Stream)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_pre.append(_on_load)
    bpy.app.timers.register(_tick, persistent=True)


def unregister():
    _on_load(None)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
