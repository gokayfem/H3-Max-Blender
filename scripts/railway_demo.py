"""Blender UI: gray railway district beside nine concurrent H3 video styles."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

import bpy
import blf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent))
from railway_scene import build

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--env',type=Path)
parser.add_argument('--generate',action='store_true')
parser.add_argument('--scene-only',action='store_true')
parser.add_argument('--closeup',action='store_true',help='Fill the frame with the station district; exclude diorama edges')
parser.add_argument('--replay',action='store_true',help='Play saved outputs without generating')
parser.add_argument('--resolution',choices=['480P','768P'],default='480P')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if args.replay and args.generate:parser.error('Choose --replay or --generate')
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if args.env:
    for line in args.env.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('FAL_KEY='):
            os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('"\'')
build(closeup=args.closeup)
scene=bpy.context.scene
scene.name='HILLSIDE JUNCTION / NINE NEURAL WORLDS'
scene.render.filepath=str(out/'geometry.png')
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'hillside-junction.blend'))
stats=dict(modeled_parts=scene['modeled_parts'],mesh_faces=scene['mesh_faces'])
(out/'geometry-stats.json').write_text(json.dumps(stats,indent=2))

STYLES=[
 ('PHOTOREAL','Architectural photography of a real lived-in hillside railway district. Warm limestone, aged brick, dark metal rails, convincing glass, terracotta roofs. Clear late-afternoon sunlight, natural scale, physically plausible materials.'),
 ('CLAYMATION','Handcrafted stop-motion clay miniature city. Warm pastel polymer clay, soft thumbprint texture, carefully sculpted miniature facades and train cars, tactile matte surfaces. All architectural details remain precisely in place.'),
 ('ANIME','Meticulously painted Japanese animated feature background. Clean hand-inked architectural contours, warm cream stucco, turquoise shadows, restrained cel shading, rich painterly sunlight. Preserve every layer of the dense railway district.'),
 ('WATERCOLOR','Finished architectural watercolor on cold-pressed paper. Precise fine pen architecture, translucent burnt-sienna and ultramarine washes, delicate granulation. All paint is already dry and complete at the first frame; no drawing or painting animation.'),
 ('CYBERPUNK','Same railway architecture rendered as a believable rainy neon city at blue hour. Weathered concrete, dark steel, restrained magenta and cyan illumination integrated into existing facade surfaces, luminous windows and wet paving. No added towers or signs obscuring architecture.'),
 ('PORCELAIN','Entire architectural district crafted in luminous glazed porcelain. Ivory ceramic facades, cobalt blue decorative surface accents, finely modeled roof tiles and tiny ceramic train, subtle glaze pooling and gentle studio daylight. Preserve the scene layout.'),
 ('CARVED WOOD','Intricate museum-quality carved wooden architectural model. Warm walnut buildings, pale maple rails and window frames, visible fine woodgrain and polished endgrain, subtle joinery and soft workshop daylight. Every existing component stays separate and legible.'),
 ('RETRO SCI-FI','A practical miniature film set from an optimistic 1970s science-fiction film. Same station and dense residential architecture, cream enamel, muted orange trim, brushed aluminum, smoked glass and restrained luminous window panels. No new spacecraft or invented megastructures.'),
 ('SCALE MODEL','Photograph of an exquisitely detailed architectural scale model. Basswood facades, ivory card roofs, frosted acrylic glazing, precisely cut miniature railway and market furniture. Deep focus so the entire city remains legible, soft museum lighting.')]
RULES=('Image 1 is the exact camera and geometry of one coherent hillside railway district. '
       'Preserve its full-frame composition, projection, framing, scale, horizon, building count, roof outlines, window placements, station vault, train position and all stairs. '
       'The reference is a close architectural crop when buildings intersect the frame boundaries. Continue those buildings naturally beyond the frame; do not pull back to show them. No surrounding landscape, display plinth, tabletop, model base or extra foreground. '
       'One finished image treatment is present from the very first frame through the last frame. '
       'Never reveal the gray input, build the scene, switch styles, dissolve, crossfade, wipe, morph, zoom, pan or orbit. '
       'Keep all architecture and parked trains stationary. Only barely perceptible ambient light and foliage movement. '
       'This is a single continuous view, not a montage. No split screens or labels. '
       'Interpret the fine modeled geometry as finished architectural surfaces. No exposed wireframe or mesh edges. MEDIUM: ')

def launch_ui():
    spec=importlib.util.spec_from_file_location('fal_ai',ROOT/'extension/__init__.py',submodule_search_locations=[str(ROOT/'extension')])
    addon=importlib.util.module_from_spec(spec);sys.modules['fal_ai']=addon;spec.loader.exec_module(addon);addon.register()
    from fal_ai import live_preview, live_grid, image_guidance
    window=bpy.context.window
    state=dict(areas=[],source=None,events=queue.Queue(),pending=set(),results={},errors={},started=0,batch=0)
    workers=[]

    def label():
        area=bpy.context.area
        if area==state['source']:
            lines=['HILLSIDE JUNCTION / GRAY GEOMETRY',f"{stats['modeled_parts']:,} modeled parts / {stats['mesh_faces']:,} faces",'9 parallel H3 Max views / '+args.resolution]
            if len(state['results'])==9:
                lines.append(f"All visible: {max(r['visible_seconds'] for r in state['results'].values()):.2f}s")
            if state['started']:
                lines.append(f"{9-len(state['pending'])}/9 ready" + (f" / {time.perf_counter()-state['started']:.1f}s elapsed" if state['pending'] else ''))
        elif area in state['areas']:
            i=state['areas'].index(area);lines=[STYLES[i][0]]
            if i in state['pending']:lines.append('GENERATING')
            elif i in state['errors']:lines.append('REQUEST FAILED')
            elif i in state['results']:
                r=state['results'][i];gpu=(r.get('provider_timings') or {}).get('inference')
                lines.append((f'GPU {gpu:.2f}s / ' if gpu is not None else '') + f"API {r['api_seconds']:.2f}s")
        else:return
        for j,line in enumerate(lines):
            blf.size(0,13 if area in state['areas'] else 16)
            blf.color(0,1,1,1,1);blf.position(0,12,bpy.context.region.height-42-j*21,0);blf.draw(0,line)

    def submit():
        if state['pending'] or any(w.is_alive() for w in workers):return
        key=os.environ.get('FAL_KEY','')
        if not key:raise RuntimeError('FAL_KEY is required for --generate')
        state.update(started=time.perf_counter(),batch=state['batch']+1,results={},errors={},pending=set(range(9)))
        scene.render.filepath=str(out/'geometry.png');bpy.ops.render.render(write_still=True)
        capture=time.perf_counter()-state['started']
        bundle=image_guidance.prepare((out/'geometry.png').read_bytes(),[],'IMAGE')
        workers.clear()
        for i,(_,style) in enumerate(STYLES):
            payload=image_guidance.payload(bundle,RULES+style,args.resolution,271828,i)
            t=threading.Thread(target=live_preview.generate,args=(key,payload,str(out),state['events'],i,capture,live_grid.ENDPOINT),daemon=True)
            workers.append(t);t.start()

    def tick():
        while not state['events'].empty():
            i,kind,data=state['events'].get_nowait()
            if kind=='status':continue
            state['pending'].discard(i)
            if kind=='error':state['errors'][i]=data
            else:
                live_grid._play(i,data['video_path'],dict(areas=state['areas'],window=window))
                data['visible_seconds']=time.perf_counter()-state['started'];state['results'][i]=data
            report=dict(**stats,batch=state['batch'],pending=list(state['pending']),errors=state['errors'],styles={STYLES[j][0]:r for j,r in state['results'].items()})
            (out/'nine-grid-status.json').write_text(json.dumps(report,indent=2))
            if not state['pending']:
                bpy.ops.wm.save_as_mainfile(filepath=str(out/'hillside-junction.blend'))
                bpy.ops.screen.screenshot(filepath=str(out/'nine-grid.png'))
        refresh=out/'refresh.flag'
        if args.generate and refresh.exists() and not state['pending']:
            refresh.unlink();submit()
        for a in [state['source'],*state['areas']]:a.tag_redraw()
        return .05

    def split(area,direction,factor):
        with bpy.context.temp_override(window=window,area=area):bpy.ops.screen.area_split(direction=direction,factor=factor)

    def layout(step=0):
        views=sorted([a for a in window.screen.areas if a.type=='VIEW_3D'],key=lambda a:(a.x,-a.y))
        if step==0:split(views[0],'VERTICAL',.31)
        elif step==1:split(views[-1],'VERTICAL',1/3)
        elif step==2:split(views[-1],'VERTICAL',.5)
        elif step<9:
            # Split each of the three result columns into three rows.
            col=(step-3)//2; half=(step-3)%2
            xs=sorted(set(a.x for a in views))[1:]
            column=sorted([a for a in views if a.x==xs[col]],key=lambda a:a.y)
            split(column[-1] if half==0 else max(column,key=lambda a:a.height),'HORIZONTAL',1/3 if half==0 else .5)
        else:
            source=min(views,key=lambda a:a.x);state['source']=source
            state['areas']=sorted([a for a in views if a!=source],key=lambda a:(-round(a.y/10),a.x))
            assert len(state['areas'])==9
            for a in state['areas']:
                a.type='CLIP_EDITOR';a.spaces.active.show_region_ui=False;a.spaces.active.show_region_toolbar=False
            s=source.spaces.active;s.overlay.show_overlays=False;s.show_region_ui=False;s.show_region_toolbar=False
            s.shading.type='SOLID';s.shading.color_type='SINGLE';s.shading.single_color=(.57,.57,.57)
            s.shading.show_cavity=True;s.shading.cavity_type='BOTH'
            s.show_region_tool_header=False;s.show_gizmo=False
            s.region_3d.view_perspective='CAMERA';s.region_3d.view_camera_zoom=0
            bpy.types.SpaceView3D.draw_handler_add(label,(),'WINDOW','POST_PIXEL')
            bpy.types.SpaceClipEditor.draw_handler_add(label,(),'WINDOW','POST_PIXEL')
            bpy.app.timers.register(tick,first_interval=.1)
            if args.generate:submit()
            if args.replay:
                saved=json.loads((out/'nine-grid-status.json').read_text())
                for i,(name,_) in enumerate(STYLES):
                    if name in saved['styles']:
                        r=saved['styles'][name];state['results'][i]=r
                        live_grid._play(i,r['video_path'],dict(areas=state['areas'],window=window))
                def save_replay():
                    bpy.ops.wm.save_as_mainfile(filepath=str(out/'hillside-junction.blend'))
                    bpy.ops.screen.screenshot(filepath=str(out/'nine-grid.png'))
                bpy.app.timers.register(save_replay,first_interval=2)
            (out/'ready.flag').write_text('ready')
            return None
        bpy.app.timers.register(lambda:layout(step+1),first_interval=.18)
        return None
    bpy.app.timers.register(layout,first_interval=.5)

if not args.scene_only:
    if bpy.app.background:raise RuntimeError('Run without --background for the nine-pane UI')
    launch_ui()
