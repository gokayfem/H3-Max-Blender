"""Four concurrent H3 reference renders from one captured geometry revision."""
import queue
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

import bpy
from bpy.app.handlers import persistent

from . import live_preview as live
from . import image_guidance
from .preferences import get_api_key, get_output_dir

ENDPOINT = 'https://fal.run/minimax/h3-max/reference-to-video'
from . import surface_prompts
STYLES = tuple(zip(('CARTOON', 'CLAYMATION', 'REALISTIC', 'STYLIZED / GOUACHE'), surface_prompts.STYLES))
GEOMETRY_RULES = ('Image 1 is a coarse design proxy for a real manufactured object, not the final surface. '
    'Preserve the existing major components, their count, placement, proportions and overall design envelope. '
    'Interpret each component according to its physical function: reconstruct smooth continuous manufactured surfaces '
    'from the coarse proxy, with believable curvature, rounded fabrication transitions, realistic thickness and material response. '
    'Visible polygon boundaries, flat-shading facets and blockout bevel bands are modeling artifacts; they must not appear '
    'as panel lines, hard creases or exposed mesh edges in the finished object. '
    'Surface refinement is allowed; inventing additional major components is not. '
    'Keep the current level of assembly: an unfinished assembly stays unfinished, but every existing part looks real. '
    'Add only restrained surface-scale physical detail appropriate to the components already present. '
    'Preserve empty spaces and uncluttered broad areas. Match camera, framing and overall silhouette. '
    'Locked camera. The object stays stationary; only water moves gently. ')

_session = None
_workers = []
_playing = {}


def prompts_for(base, has_style_references=False, mode='IMAGE'):
    if mode == 'PER_STYLE_TEXT':
        roles = ['Images 1, 2 and 3 repeat the same target geometry and camera. ', 'Image 1 is the target geometry and camera. Image 2 is camera-space surface normals. Image 3 is the exact visible silhouette mask, black object on white background. ', 'Image 1 is the target geometry and camera. ', 'Image 1 is the target geometry and camera. Image 2 contains enlarged geometry details, never a different framing. ']
        return [roles[i] + surface_prompts.TEMPORAL + surface_prompts.REALISM + surface_prompts.STYLES[i] + ' STYLE is defined entirely by the chosen-medium description. CURRENT GEOMETRY HAS HIGHEST PRIORITY: ' + base for i in range(4)]
    if mode == 'PER_STYLE':
        common = ('One single full-frame view of the input geometry. Image 1 alone determines camera projection, viewpoint, framing, silhouette, object size and exact pixel positions. No zoom, pan, tilt, roll, orbit, dolly or reframing. No object movement, rocking or deformation. Only subtle water motion outside the hull. Transfer only palette, light and surface material character from the designated STYLE image. Never copy composition or object scale from STYLE. ')
        roles = ['Images 1, 2 and 3 repeat the exact same target camera and geometry. Image 4 is STYLE only. ', 'Image 2 encodes camera-space surface normals; use it only for face orientation and boundaries. Image 3 is the exact visible silhouette mask: black ship, white background. Match it. Image 4 is STYLE only. ', 'Image 2 is STYLE only. ', 'Image 2 is an aspect-preserved 3x3 detail sheet. Its crops explain components only, not camera framing. Image 3 is STYLE only. ']
        return [role + common + base for role in roles]
    style_number = 3 if mode in {'DETAIL','MATERIAL'} else 2
    binding = (f' Image {style_number} is a fixed object-free style reference. Use it only for its palette, '
        'lighting character, material response, texture scale and photographic aesthetic. '
        'Keep that same visual treatment consistent between generations. All object identity, '
        'components, framing and layout come exclusively from Image 1, never the style reference. ') if has_style_references else ''
    rules = GEOMETRY_RULES
    if mode in {'DETAIL','MATERIAL'}:
        rules = ('Image 1 alone defines the target camera projection, framing, silhouette, object size and pixel positions. '
            'Image 2 is a 3x3 aspect-preserved detail sheet of that same geometry. Its center is the full frame; '
            'other tiles explain components only. Never copy the grid, its labels or its crop framing. '
            'Preserve component count, relative heights, surface borders, roof outline and empty spaces. '
            'Window-frame rectangles indicate glazing: make their interiors dark reflective glass without moving the borders. '
            'No zoom, pan, tilt, roll, orbit, dolly, reframing, object motion or deformation. '
            'The camera is stationary; only subtle environmental motion outside the object is allowed. ')
    if mode == 'MATERIAL':
        rules += ('This is material replacement on an existing CG render, not reconstruction of a new object. '
            'Change surface color, roughness, reflection and illumination only. Remove tessellation shading artifacts '
            'without remodeling the geometry. ')
    return [rules + binding + '\nSURFACE AND ENVIRONMENT: ' + treatment + '\nCURRENT GEOMETRY - highest priority: ' + base for _, treatment in STYLES]


def _submit_batch(image, styles, mode, seed, prompts, resolution, key, folder, events, token, capture_seconds, buffers=None):
    """One preparation worker supervises four parallel requests; no Blender access."""
    started = time.perf_counter()
    try:
        bundle = image_guidance.prepare(image, styles, mode, buffers)
        preparation_seconds = time.perf_counter() - started
        workers = []
        for index, prompt in enumerate(prompts):
            payload = image_guidance.payload(bundle, prompt, resolution, seed, index)
            worker = threading.Thread(target=live.generate, args=(key, payload, folder, events,
                (token,index), capture_seconds+preparation_seconds, ENDPOINT), daemon=True)
            workers.append(worker)
            worker.start()
        for worker in workers:
            worker.join()
    except Exception as exc:
        for index in range(4):
            events.put(((token,index), 'error', f'Image guidance preparation failed: {type(exc).__name__}'))


def load_style_references(manifest_path):
    if not manifest_path:
        return []
    path = Path(bpy.path.abspath(manifest_path)).resolve()
    manifest = json.loads(path.read_text(encoding='utf-8'))
    entries = manifest.get('styles', [])
    if [e.get('id') for e in entries] != ['expedition', 'storm', 'orbital', 'miniature']:
        raise ValueError('Style manifest must contain the four expected styles in order')
    images = []
    for entry in entries:
        image_path = (path.parent/entry['file']).resolve()
        if not image_path.is_relative_to(path.parent):
            raise ValueError('Style image must be inside its manifest directory')
        image = image_path.read_bytes()
        if not image.startswith((b'\xff\xd8', b'\x89PNG\r\n\x1a\n')):
            raise ValueError('Style reference must be a JPEG or PNG image')
        if hashlib.sha256(image).hexdigest() != entry['sha256']:
            raise ValueError('Style reference changed; create a new manifest before using it')
        images.append(image)
    return images


def create_layout(window, ready):
    """Split on separate UI ticks so Blender has updated area coordinates."""
    def split(area, direction, factor):
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.area_split(direction=direction, factor=factor)

    def step(index=0):
        views = sorted([a for a in window.screen.areas if a.type == 'VIEW_3D'], key=lambda a:a.x)
        if index == 0:
            if len(views) != 1:
                raise RuntimeError('Create the grid in a workspace with one 3D viewport')
            split(views[0], 'VERTICAL', .34)
        elif index == 1:
            split(views[-1], 'VERTICAL', .5)
        elif index == 2:
            split(views[1], 'HORIZONTAL', .5)
        elif index == 3:
            split(max(views, key=lambda a:a.x), 'HORIZONTAL', .5)
        else:
            source = min(views, key=lambda a:a.x)
            areas = sorted([a for a in views if a != source], key=lambda a:(-a.y,a.x))
            for area in areas:
                area.type = 'CLIP_EDITOR'
                area.spaces.active.show_region_ui = False
                area.spaces.active.show_region_toolbar = False
            ready(source, areas)
            return None
        bpy.app.timers.register(lambda: step(index+1), first_interval=.2)
        return None
    bpy.app.timers.register(step, first_interval=.1)


def start(window, source, areas):
    global _session, _workers
    from . import live_stream
    if _session or live._session or live_stream._stream or any(w.is_alive() for w in _workers + live_stream._workers) or (live._worker and live._worker.is_alive()):
        raise RuntimeError('Stop the current render session and wait for requests to finish')
    if len(areas) != 4:
        raise RuntimeError('Four Movie Clip Editor areas are required')
    key = get_api_key()
    if not key or not bpy.app.online_access:
        raise RuntimeError('Configure a fal key and enable online access')
    manifest_path = window.scene.fal_h3_live.style_manifest
    style_images = load_style_references(manifest_path)
    _session = dict(window=window, area=source, scene=window.scene, areas=areas,
        key=key, folder=get_output_dir(), token=uuid.uuid4().hex, events=queue.Queue(),
        busy=False, pending=set(), results={}, errors={}, observed=None, submitted=None,
        changed=time.perf_counter(), count=0, completed=0, history=[],
        style_images=style_images, style_manifest=manifest_path)
    window.scene.fal_h3_live.status = 'Grid ready — waiting for geometry'
    return _session


def _play(index, path, session):
    area = session['areas'][index]
    previous = _playing.get(index)
    clip = bpy.data.movieclips.load(path, check_existing=True)
    area.spaces.active.clip = clip
    _playing[index] = dict(area=area, clip=clip, started=time.perf_counter())
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=session['window'], area=area, region=region):
        bpy.ops.clip.view_all(fit_view=True)
    if previous and previous['clip'].users == 0:
        bpy.data.movieclips.remove(previous['clip'])


def _tick():
    global _session, _workers
    for index, playing in list(_playing.items()):
        try:
            area, clip = playing['area'], playing['clip']
            if area.type != 'CLIP_EDITOR':
                del _playing[index]
                continue
            frame = int((time.perf_counter()-playing['started'])*clip.fps)
            area.spaces.active.clip_user.frame_current = 1 + frame % max(1, clip.frame_duration)
            area.tag_redraw()
        except (ReferenceError, RuntimeError, AttributeError):
            del _playing[index]
    s = _session
    if not s:
        return 1/24
    try:
        p = s['scene'].fal_h3_live
        if 'style_manifest' in s and p.style_manifest != s['style_manifest']:
            raise RuntimeError('Style manifest changed; restart the grid to load the new reference set')
        if s['window'].scene != s['scene'] or s['area'].type != 'VIEW_3D' or any(a.type != 'CLIP_EDITOR' for a in s['areas']):
            raise RuntimeError('Grid layout changed; restart the session')
        signature = live._signature(s)
        now = time.perf_counter()
        if signature != s['observed']:
            s['observed'], s['changed'] = signature, now
        while not s['events'].empty():
            token, kind, data = s['events'].get_nowait()
            batch_token, index = token
            if batch_token != s['batch_token']:
                continue
            if kind == 'status':
                continue
            s['pending'].discard(index)
            if kind == 'error':
                s['errors'][index] = data
            else:
                s['results'][index] = data
                if signature == s['submitted']:
                    _play(index, data['video_path'], s)
            if not s['pending']:
                s['busy'] = False
                if s['errors']:
                    p.status = 'Grid stopped: ' + next(iter(s['errors'].values()))
                    _session = None
                    break
                if signature == s['submitted']:
                    s['completed'] += 1
                    row = dict(batch=s['count'], wall_seconds=now-s['batch_started'],
                        styles=[dict(style=STYLES[i][0], **s['results'][i]) for i in range(4)])
                    s['history'].append(row)
                    p.last_video = s['results'][0]['video_path']
                    p.timing = f"4 parallel renders | all visible {row['wall_seconds']:.2f}s"
                    p.status = f"Grid {s['count']} ready — edit to refresh"
                else:
                    p.status = 'Geometry changed — obsolete batch discarded'
                if s['count'] >= p.max_requests:
                    _session = None
                    break
        if _session is s and not s['busy'] and signature != s['submitted'] and now-s['changed'] >= p.settle_seconds:
            s['batch_started'] = time.perf_counter()
            buffers = None
            if p.grid_guidance in {'PER_STYLE','PER_STYLE_TEXT'}:
                from . import camera_guidance
                image, normal, mask = camera_guidance.capture(s)
                buffers = (normal, mask)
            else:
                image = live._capture(s)
            capture_seconds = time.perf_counter()-s['batch_started']
            s.update(submitted=live._signature(s), busy=True, pending=set(range(4)),
                results={}, errors={}, batch_token=uuid.uuid4().hex, count=s['count']+1)
            styles = s.get('style_images', [])
            mode = p.grid_guidance
            worker = threading.Thread(target=_submit_batch, args=(image, styles, mode, p.grid_seed,
                prompts_for(p.prompt, bool(styles), mode), p.resolution, s['key'], s['folder'],
                s['events'], s['batch_token'], capture_seconds, buffers), daemon=True)
            _workers = [worker]
            worker.start()
            p.status = f"Grid {s['count']} — preparing image guidance, then four inferences"
        elif _session is s and s['busy']:
            p.status = f"Grid {s['count']} — {4-len(s['pending'])}/4 views ready"
    except Exception as exc:
        try:
            s['scene'].fal_h3_live.status = f'Grid stopped: {type(exc).__name__}: {exc}'
        except ReferenceError:
            pass
        _session = None
    return 1/24


class FAL_OT_H3GridLayout(bpy.types.Operator):
    bl_idname = 'fal.h3_grid_layout'
    bl_label = 'Open four-style layout'
    def execute(self, context):
        views = [a for a in context.screen.areas if a.type == 'VIEW_3D']
        clips = [a for a in context.screen.areas if a.type == 'CLIP_EDITOR']
        if len(views) != 1 or clips:
            self.report({'ERROR'}, 'Use a fresh workspace with one 3D viewport and no clip editors')
            return {'CANCELLED'}
        create_layout(context.window, lambda source, areas: None)
        return {'FINISHED'}


class FAL_OT_H3GridStart(bpy.types.Operator):
    bl_idname = 'fal.h3_grid_start'
    bl_label = 'Start four-style grid'
    bl_description = 'Four paid H3 requests per settled edit; session limit counts batches'
    def execute(self, context):
        if context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        try:
            areas = sorted([a for a in context.screen.areas if a.type == 'CLIP_EDITOR'], key=lambda a:(-a.y,a.x))
            start(context.window, context.area, areas)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class FAL_OT_H3GridStop(bpy.types.Operator):
    bl_idname = 'fal.h3_grid_stop'
    bl_label = 'Stop four-style grid'
    def execute(self, context):
        global _session
        _session = None
        context.scene.fal_h3_live.status = 'Grid stopped — submitted requests may finish'
        return {'FINISHED'}


@persistent
def _on_load(_):
    global _session
    _session = None
    _playing.clear()


def register():
    for cls in (FAL_OT_H3GridLayout, FAL_OT_H3GridStart, FAL_OT_H3GridStop):
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_pre.append(_on_load)
    bpy.app.timers.register(_tick, persistent=True)


def unregister():
    _on_load(None)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)
    for cls in (FAL_OT_H3GridStop, FAL_OT_H3GridStart, FAL_OT_H3GridLayout):
        bpy.utils.unregister_class(cls)
