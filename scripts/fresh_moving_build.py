"""Recorded, scripted geometry build. Start by creating OUTPUT/start-build.flag."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

import bpy
import blf
from mathutils import Vector

parser=argparse.ArgumentParser()
parser.add_argument('--env',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--grid',action='store_true')
parser.add_argument('--keep-live',action='store_true')
parser.add_argument('--start-stage',type=int,default=0,choices=range(7))
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
for line in Path(args.env).read_text(encoding='utf-8-sig').splitlines():
    if line.strip().startswith('FAL_KEY='):
        os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('\"\'');break
import importlib.util
extension_root = Path(__file__).resolve().parents[1] / 'extension'
spec = importlib.util.spec_from_file_location('fal_ai', extension_root / '__init__.py', submodule_search_locations=[str(extension_root)])
addon = importlib.util.module_from_spec(spec)
sys.modules['fal_ai'] = addon
spec.loader.exec_module(addon)
addon.register()
from fal_ai import live_preview, live_grid, stage_prompts
# Present moving late sections; retain full raw model outputs beside previews.
import subprocess
_original_generate=live_preview.generate
class MovingEvents:
    def __init__(self,target): self.target=target
    def put(self,event):
        token,kind,data=event
        if kind=='complete':
            begin=time.perf_counter()
            raw=Path(data['video_path']);preview=raw.with_name(raw.stem+'-moving.mp4')
            subprocess.run(['ffmpeg','-y','-v','error','-ss','3','-i',str(raw),'-t','1.8','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(preview)],check=True)
            data=dict(data,raw_video_path=str(raw),video_path=str(preview),preview_trim_start=3,preview_duration=1.8,preview_process_seconds=time.perf_counter()-begin)
            preview.with_suffix('.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
            event=(token,kind,data)
        self.target.put(event)
def moving_generate(key,payload,folder,events,token,capture_seconds,endpoint=live_preview.ENDPOINT):
    return _original_generate(key,payload,folder,MovingEvents(events),token,capture_seconds,endpoint)
live_preview.generate=moving_generate
bpy.context.preferences.view.show_splash=False
scene=bpy.context.scene;scene.name='IMAGE ONLY / MEASURED LIVE DEMO'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene.render.filepath=str(out)+os.sep
scene.render.resolution_x=848;scene.render.resolution_y=480;scene.render.resolution_percentage=100
scene.frame_start=1;scene.frame_end=120
scene.render.fps=24
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.name='Ground plane / interpreted as ocean'
bpy.context.object.color=(.16,.16,.16,1)
bpy.ops.object.camera_add(location=(17,-23,15))
camera=bpy.context.object;camera.name='Fixed comparison camera';camera.data.lens=47
camera.rotation_euler=(Vector((0,0,1.2))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.camera=camera
objects={}

def box(name,loc,scale):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    obj=bpy.context.object;obj.name=name;obj.scale=scale;obj.color=(.55,.55,.55,1)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=obj.modifiers.new('Soft fabrication edges','BEVEL');bevel.width=.04;bevel.segments=2
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return obj

def pipe(name,points,radius=.045):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=2
    sp=c.splines.new('POLY');sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    obj=bpy.data.objects.new(name,c);scene.collection.objects.link(obj);obj.color=(.55,.55,.55,1)
    return obj

def hull():
    stations=[(-5,1.2),(-4,1.75),(0,1.85),(3,1.3),(5.6,.03)]
    verts=[]
    for x,w in stations:
        verts += [(x,-w,1.35),(x,-w*.9,.06),(x,-w*.5,-.6),(x,w*.5,-.6),(x,w*.9,.06),(x,w,1.35)]
    faces=[]
    for i in range(len(stations)-1):
        for j in range(6):faces.append((i*6+j,i*6+(j+1)%6,(i+1)*6+(j+1)%6,(i+1)*6+j))
    faces += [tuple(reversed(range(6))),tuple(range(24,30))]
    mesh=bpy.data.meshes.new('Hull topology');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new('01 / Hull',mesh);scene.collection.objects.link(obj);obj.color=(.55,.55,.55,1)
    bevel=obj.modifiers.new('Hull chines','BEVEL');bevel.width=.06;bevel.segments=3
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    obj.scale.x=.65;objects['hull']=obj
    return [obj]

def lengthen():
    obj=objects['hull'];obj.scale.x=1
    return [obj]

def cabin():return [box('02 / Deckhouse',(-.6,0,1.98),(4.8,2.75,1.25))]

def bridge():
    result=[box('03 / Upper bridge',(.1,0,2.95),(3.2,2.95,.75)),box('Bridge roof',(.1,0,3.37),(3.5,3.18,.14))]
    # Geometry recesses/frames, not colored materials.
    for side in [-1,1]:
        for x in [-1.05,-.35,.35,1.05]:
            result.append(box('Window frame',(x,side*1.49,3.0),(.5,.045,.35)))
    return result

def mast():
    return [pipe('04 / Mast',[(-.65,0,3.45),(-.65,0,5.45)],.045),
            box('Radar',(-.65,0,5.0),(.18,1.45,.09)),
            box('Funnel',(-2.5,0,2.95),(.65,.7,1.4)),box('Funnel cap',(-2.5,0,3.67),(.78,.83,.14))]

def crane():
    return [pipe('05 / Articulated deck crane',[(-4,.7,1.4),(-4,.7,3.4),(-4.8,.7,3.8),(-6.3,.7,3.5)],.12),
            pipe('Crane cable',[(-6.3,.7,3.5),(-6.3,.7,1.6)],.017)]

def finish():
    result=[]
    for side in [-1,1]:
        result.append(box('06 / Rescue boat',(-2.9,side*1.38,1.78),(1.45,.58,.4)))
        points=[(-4.8,side*1.25,1.92),(-3.8,side*1.65,1.92),(0,side*1.78,1.92),(3,side*1.25,1.92),(5.5,0,1.92)]
        result.append(pipe('Deck handrail',points,.025))
        for x in [-4,-3,-2,-1,0,1,2,3]:
            y=side*(1.65 if x<1 else 1.45)
            result.append(pipe('Rail post',[(x,y,1.35),(x,y,1.92)],.02))
    return result

stages=[('Block out the hull',hull,'Bare-hull assembly stage. Only one low boat hull with an uninterrupted empty deck is present. Smoothly faired steel hull plating with gently curved sides, clean tapered bow, subtly rounded gunwale and flat finished deck. Zero raised structures. A real bare boat hull, not a polygonal slab. Keep all volume low within the reference envelope.'),
        ('Stretch the vessel',lengthen,'The same bare-hull assembly is now elongated. Only the longer low hull and uninterrupted empty deck exist. Smooth continuous curved hull plating, refined bow, rounded gunwale edge. Zero raised structures. Preserve the changed long proportions.'),
        ('Build the deckhouse',cabin,'The real hull now supports exactly one low deckhouse. Interpret the rectangular proxy as a welded steel enclosure with subtly rounded fabrication corners and solid blank walls. No openings are modeled in this enclosure yet. All remaining deck area stays clear. Only hull plus this one enclosure exist.'),
        ('Add the bridge',bridge,'The hull now supports a lower deckhouse and an upper wheelhouse with a roof. The modeled rectangular face frames define the actual windows: install dark reflective glazing within precisely those frames. Refine corners and roof thickness into plausible marine construction. Preserve the sparse two-level arrangement.'),
        ('Raise the mast',mast,'The existing hull, deckhouse, glazed wheelhouse and roof remain. The newly modeled thin vertical rod and crossbar are a slender metal mast, and the short rectangular stack is a marine exhaust. Interpret these existing parts realistically, retaining their exact arrangement and sparse scale.'),
        ('Assemble the crane',crane,'The existing assemblies remain. The newly modeled bent arm at the left rear is a small deck lifting crane, with the modeled hanging line as its cable. Refine it as manufactured hydraulic equipment within the existing arm envelope. Keep the rest of the deck clear.'),
        ('Fit out the deck',finish,'Interpret the currently visible components as the parts of a compact coastal workboat. Refine the hull into faired continuous plating, enclosure corners into welded marine construction, modeled window frames into proper glazing, slender rods and rails into metal tubes, and the lifting arm into a plausible small crane. The small side proxies are compact rescue tenders. Only realize components actually present in Image 1; removed parts stay absent and new visible parts follow their physical role. Keep the current sparse design and broad uncluttered areas.')]
"""Geometry stages injected into the established live demo runner."""
def refined_hull():
    obj=objects['hull']
    verts=[]; faces=[]; count=65; sides=25
    for i in range(count):
        t=i/(count-1); x=-6.3+13.5*t
        width=2.12*(.72+.28*math.sin(min(t/.55,1)*math.pi/2))
        if t>.62: width*=max(.008, math.cos((t-.62)/.38*math.pi/2))
        for j in range(sides):
            angle=math.pi+math.pi*j/(sides-1)
            verts.append((x,width*math.cos(angle),1.35+1.97*math.sin(angle)))
    for i in range(count-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    faces += [tuple(reversed(range(sides))),tuple(range((count-1)*sides,count*sides))]
    mesh=bpy.data.meshes.new('Faired hull / 65 stations');mesh.from_pydata(verts,[],faces);mesh.update()
    obj.data=mesh;obj.modifiers.clear();obj.scale=(1,1,1)
    for poly in mesh.polygons: poly.use_smooth=len(poly.vertices)==4 and poly.index%sides!=sides-1
    return []

def decks():
    result=[box('Extended aft equipment deck',(-3.95,0,1.47),(4.1,3.65,.18)),
            box('Forecastle raised deck',(3.2,0,1.6),(2.6,2.65,.5)),
            box('Aft laboratory',(-3.6,0,2.0),(1.55,2.3,.95))]
    for side in (-1,1):
        result.append(box('Bridge wing',(.1,side*1.8,2.57),(3.8,.72,.18)))
        for x in (-2,-1.25,-.5,.25,1):
            # Layered framing and inset inner pane are actual mesh.
            result.append(box('Deckhouse window surround',(x,side*1.391,2.1),(.55,.055,.43)))
            result.append(box('Recessed window pane',(x,side*1.424,2.1),(.44,.02,.32)))
    return result

def access():
    result=[]
    for side in (-1,1):
        for i in range(8):
            result.append(box('Stair tread',(-2.85+i*.17,side*1.68,1.42+i*.145),(.23,.52,.08)))
        for y in (side*1.4,side*1.94):
            result.append(pipe('Stair handrail',[(-2.9,y,2.05),(-1.55,y,3.18)],.025))
        for x in (-3.7,-2.7,-1.7,-.7,.3,1.3,2.3,3.3):
            result.append(pipe('Deck railing stanchion',[(x,side*1.98,1.45),(x,side*1.98,2.08)],.026))
        for z in (1.77,2.08):
            result.append(pipe('Continuous safety rail',[(-5.9,side*1.55,z),(-4,side*1.98,z),(2.4,side*1.98,z),(4.1,side*1.42,z),(6.8,0,z)],.026))
    return result

def machinery():
    result=crane()
    result.append(box('Crane rotating pedestal',(-4,.7,1.7),(.65,.65,.65)))
    result.append(pipe('Hydraulic ram',[(-4,.68,2.3),(-4.7,.68,3.65)],.07))
    for x in (-5.65,3.7):
        for side in (-1,1):
            result.append(box('Bollard base',(x,side*1.05,1.84),(.65,.4,.12)))
            for dx in (-.18,.18):
                result.append(pipe('Mooring bollard',[(x+dx,side*1.05,1.9),(x+dx,side*1.05,2.18)],.07))
    for i in range(7):
        result.append(box('Ventilation grille slat',(-3.6,-1.18,1.75+i*.07),(1,.08,.025)))
    return result

def outfitting():
    result=[]
    for side in (-1,1):
        for x in (-3.2,-1.6,0,1.6):
            bpy.ops.mesh.primitive_torus_add(major_segments=32,minor_segments=12,location=(x,side*2.06,.95),rotation=(math.pi/2,0,0),major_radius=.22,minor_radius=.075)
            o=bpy.context.object;o.name='Rubber hull fender';o.color=(.55,.55,.55,1)
            for f in o.data.polygons:f.use_smooth=True
            result.append(o)
        result.append(box('Rescue tender cradle',(-2.1,side*1.66,1.6),(1.65,.55,.15)))
        result.append(box('Rescue tender',(-2.1,side*1.66,1.84),(1.55,.52,.32)))
    for x,y in ((-.65,0),(.65,.6),(.8,-.6)):
        result.append(pipe('Navigation antenna',[(x,y,3.5),(x,y,4.6)],.018))
    for x in (2.2,2.9,3.6):result.append(box('Foredeck hatch',(x,0,1.9),(.52,.65,.08)))
    for obj in scene.objects:
        for mod in obj.modifiers:
            if mod.type=='BEVEL':mod.segments=4
        if obj.type=='CURVE':obj.data.bevel_resolution=4
    return result

stages=stages[:5]+[
    ('Enlarge and fair the hull',refined_hull,'Larger research vessel hull with smooth continuous rounded plating and a tapered bow. Preserve the existing wheelhouse and mast.'),
    ('Expand decks and laboratory',decks,'The visible raised foredeck, aft laboratory, bridge wings and layered window frames are now present. Preserve their exact dimensions.'),
    ('Build stairs and safety rails',access,'Real stair treads, inclined handrails, fine deck stanchions and continuous rails follow the visible geometry. Preserve every modeled deck level.'),
    ('Assemble working deck equipment',machinery,'The aft articulated crane has a pedestal, hydraulic ram and cable. Retain the modeled mooring bollards and ventilation grille.'),
    ('Finish fittings and refined surfaces',outfitting,'Fully outfitted research workboat with the visible fenders, compact tenders, navigation antennas, hatches, crane, fine rails and stairs. Detailed manufactured surfaces with clean smooth hull plating. No additional large structures.')]

def expedition_equipment():
    result=[]
    for side in (-1,1):
        result.append(pipe('Aft research gantry upright',[(-5.6,side*1.35,1.55),(-5.6,side*1.35,3.55)],.085))
        result.append(pipe('Gantry diagonal brace',[(-4.8,side*1.35,1.55),(-5.6,side*1.35,2.7)],.06))
        for x in (-3.9,-3.3):
            result.append(box('Canister cradle',(x,side*1.4,2.55),(.48,.45,.12)))
            bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=(x,side*1.4,2.78))
            o=bpy.context.object;o.name='Emergency raft canister';o.scale=(.3,.2,.2);o.color=(.55,.55,.55,1);result.append(o)
        for i in range(10):result.append(pipe('Access ladder rung',[(-3.95,side*1.18,1.6+i*.12),(-3.55,side*1.18,1.6+i*.12)],.018))
    result.append(pipe('Research gantry crossbeam',[(-5.6,-1.35,3.55),(-5.6,1.35,3.55)],.1))
    result.append(box('Gantry hoist',(-5.6,0,3.45),(.45,.5,.3)))
    result.append(pipe('Hoist cable',[(-5.6,0,3.3),(-5.6,0,1.8)],.014))
    for y in (-.6,.6):
        result.append(box('Winch plinth',(-4.9,y,1.6),(.7,.65,.22)))
        for i in range(12):result.append(pipe('Winch cable coil',[(-5.15+i*.04,y-.2,1.95),(-5.15+i*.04,y+.2,1.95)],.035))
    return result

def precision_fittings():
    result=[]
    for side in (-1,1):
        for x in (-2,-1.25,-.5,.25,1):
            for dx in (-.24,.24):
                for dz in (-.18,.18):result.append(box('Window fastener',(x+dx,side*1.445,2.1+dz),(.035,.025,.035)))
        for x in (-3.7,-2.7,-1.7,-.7,.3,1.3,2.3,3.3):
            result.append(box('Railing mounting flange',(x,side*1.98,1.47),(.14,.14,.035)))
        result.append(pipe('External service conduit',[(-2.9,side*1.4,1.7),(1.6,side*1.4,1.7),(1.6,side*1.4,2.45)],.025))
    for i in range(14):result.append(box('Foredeck anti-slip seam',(2.05+i*.11,0,1.862),(.012,2.25,.012)))
    result.append(box('Roof HVAC plinth',(.7,0,3.51),(.65,.8,.2)))
    for i in range(9):result.append(box('HVAC fin',(.43+i*.07,0,3.64),(.025,.7,.035)))
    return result

stages += [('Install expedition machinery',expedition_equipment,'Current geometry now includes an aft A-frame research gantry with crossbeam, cable and hoist, winches, raft canisters and access ladders. All previous fittings remain. Every visible new part must exist from the first frame; no assembly animation in generated clips.'),('Refine fabrication details',precision_fittings,'Preserve the entire detailed research vessel including gantry, crane, fenders, stairs, rails and tenders. Modelled window fasteners, rail flanges, service conduit, anti-slip deck seams and roof ventilation unit receive precise manufactured surface detail. No added geometry beyond the image.')]
stages.insert(5,('Starting ship',lambda: [],'Exactly the visible simple hull, deckhouse, wheelhouse, roof and slender mast. Keep all empty deck regions clear.'))
base_prompt='Preserve the existing component count, relative heights and boundaries. Window-frame rectangles indicate glazing: make interiors dark reflective glass without moving their borders. Preserve the roof outline, crane, mast, rails and empty deck areas. Do not invent equipment. Object category: small coastal workboat. CURRENT ASSEMBLY: '
p=scene.fal_h3_live;p.grid_guidance='PER_STYLE_TEXT';p.grid_seed=112358;p.style_manifest='' ;p.preview_mode='REFERENCE';p.source_format='JPEG';p.resolution='768P';p.max_requests=40;p.settle_seconds=.8
for _, create_initial, _ in stages[:args.start_stage]:
    create_initial()
state=dict(stage=args.start_stage-1,phase='waiting',started=0,phase_at=0,previous_video='',motion=[],history=[],done=False)
text=bpy.data.texts.new('LIVE BUILD / telemetry')
window=None;source=None;preview=None;grid_views=[]


def active_session():
    return live_grid._session if args.grid else live_preview._session

def header(label):
    if bpy.app.driver_namespace.get('fal_capture_active'):return
    if label=='GRID':
        index=next((i for i,a in enumerate(grid_views) if a==bpy.context.area),None)
        label=live_grid.STYLES[index][0] if index is not None else 'H3 / LIVE'
        session=active_session()
        if session and index in session.get('pending',set()): label += ' / UPDATING'
    blf.size(0,18 if args.grid else 22);blf.color(0,.94,.94,.94,1);blf.position(0,20,bpy.context.region.height-40,0);blf.draw(0,label)

def status_file():
    (out/'build-status.json').write_text(json.dumps(dict(initial_stage=args.start_stage,stage=state['stage'],phase=state['phase'],status=p.status,timing=p.timing,video=p.last_video,history=state['history'],done=state['done']),indent=2))

def tick():
    now=time.perf_counter()
    if (out/'stop-build.flag').exists():
        live_grid._session=None
        live_preview._session=None
        state['phase']='stopped';state['done']=True
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'research-ship.blend'))
        status_file();return None
    if state['phase']=='waiting':
        if not (out/'start-build.flag').exists():return .1
        state['started']=now;state['recording_epoch']=time.time();state['phase']='next';state['phase_at']=now+2
    if state['phase']=='next' and now>=state['phase_at']:
        state['stage']+=1
        if state['stage']>=len(stages):
            if not args.keep_live:
                with bpy.context.temp_override(window=window,area=source):
                    if args.grid:bpy.ops.fal.h3_grid_stop()
                    else:bpy.ops.fal.h3_stop()
            state['phase']='complete';state['done']=True
            text.clear();text.write(f'LIVE BUILD COMPLETE\n\n{len(state["history"])} geometry edits\n'+(f'{len(state["history"])*4} fresh clips\n4 parallel styles\n' if args.grid else f'{len(state["history"])} fresh clips\n')+'\nGray source geometry\nGenerated during recording\n\n'+p.timing+'\n\n'+('LIVE REFRESH IS ON\nEdit geometry to update\n' if args.keep_live else 'Start to keep editing\n')+'N > H3 Live\nStop four-style grid\n')
            bpy.ops.wm.save_as_mainfile(filepath=str(out/'research-ship.blend'))
            with bpy.context.temp_override(window=window):bpy.ops.screen.screenshot(filepath=str(out/'final-screen.png'))
            status_file();return None
        title,create,brief=stages[state['stage']]
        state['edit_started']=time.time()
        old_scale=objects['hull'].scale.copy() if state['stage']==1 else None
        new_objects=create();state['motion']=[]
        for obj in new_objects:
            target=obj.scale.copy();initial=old_scale if old_scale is not None else target*.015
            state['motion'].append((obj,initial.copy(),target));obj.scale=initial
        p.prompt=(stage_prompts.COMMON + brief) if args.grid else live_grid.prompts_for((stage_prompts.COMMON + brief))[0]
        state['previous_video']=p.last_video;state['phase']='building';state['phase_at']=now
        if active_session() is None:
            with bpy.context.temp_override(window=window,area=source):
                if args.grid:bpy.ops.fal.h3_grid_start()
                else:bpy.ops.fal.h3_start(auto=True)
    if state['phase']=='building':
        t=min(1,(now-state['phase_at'])/6.0);t=t*t*(3-2*t)
        for obj,initial,target in state['motion']:obj.scale=initial.lerp(target,t)
        if t>=1:state['phase']='rendering';state['phase_at']=now
    if state['phase']=='rendering':
        if p.last_video and p.last_video!=state['previous_video']:
            state['history'].append(dict(stage=state['stage']+1,title=stages[state['stage']][0],edit_started_epoch=state['edit_started'],visible_epoch=time.time(),edit_to_visible_seconds=now-state['phase_at'],video=p.last_video,timing=p.timing))
            if args.grid and active_session():state['history'][-1]['grid']=active_session()['history'][-1]
            state['phase']='next';state['phase_at']=now+8
        elif now-state['phase_at']>100 or (active_session() is None and ('failed' in p.status.lower() or 'stopped' in p.status.lower())):
            state['phase']='error';state['done']=True;status_file();return None
    elapsed=now-state['started'] if state['started'] else 0
    title=stages[state['stage']][0] if 0<=state['stage']<len(stages) else 'Preparing'
    text.clear();text.write('GRAY GEOMETRY\n'+('FOUR LIVE WORLDS' if args.grid else 'LIVE FILM')+'\n\nScripted live build\nContinuous recording\n\n'+f'STAGE {state["stage"]+1} / {len(stages)}\n'+title+'\n\n'+state['phase'].upper()+'\n'+p.status+'\n\n'+p.timing.replace(' | ','\n')+f'\n\nElapsed {elapsed:.1f}s\n\n832px camera images\nImage-only references\nH3 Max / 768p\n\nNo viewport materials\nMoving 1.8s excerpts\n\nN > H3 Live\nF3 > Stop\n')
    source.tag_redraw();preview.tag_redraw();status_file()
    return .075

def configure_final(grid_source=None,views=None):
    global source,preview,grid_views
    if args.grid:
        source=grid_source;grid_views=views;preview=views[0]
    else:
        areas=sorted([a for a in window.screen.areas if a.type in {'VIEW_3D','CLIP_EDITOR'}],key=lambda a:a.x)
        source,preview=areas[0],areas[1];source.type='VIEW_3D';preview.type='CLIP_EDITOR'
    space=source.spaces.active;space.overlay.show_overlays=False;space.show_region_ui=False
    space.show_region_toolbar=False;space.show_region_tool_header=False;space.show_gizmo=False
    space.shading.type='SOLID';space.shading.light='STUDIO';space.shading.color_type='OBJECT';space.shading.single_color=(.6,.6,.6)
    space.shading.background_type='VIEWPORT';space.shading.background_color=(.035,.035,.035)
    space.shading.show_shadows=True;space.shading.show_cavity=True;space.shading.cavity_type='BOTH'
    space.region_3d.view_perspective='CAMERA';space.region_3d.view_camera_zoom=-3 if args.grid else 22
    preview.spaces.active.show_region_ui=False;preview.spaces.active.show_region_toolbar=False
    for area in window.screen.areas:
        if area.type=='PROPERTIES':
            area.type='TEXT_EDITOR';area.spaces.active.text=text;area.spaces.active.font_size=16
            area.spaces.active.show_line_numbers=False;area.spaces.active.show_word_wrap=True
    bpy.types.SpaceView3D.draw_handler_add(header,('GRAY GEOMETRY / LIVE BUILD',),'WINDOW','POST_PIXEL')
    bpy.types.SpaceClipEditor.draw_handler_add(header,('GRID' if args.grid else 'H3 / GENERATED LIVE',),'WINDOW','POST_PIXEL')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'research-ship.blend'))
    text.write('GRAY GEOMETRY\nLIVE FILM\n\nReady for recording\n\nThe geometry will be\nbuilt here in stages.\n\nEach stage triggers a\nnew AI generation.\n')
    (out/'ready.flag').write_text('ready')
    bpy.app.timers.register(tick,first_interval=.2)
    return None

def configure():
    global window
    window=bpy.context.window_manager.windows[0]
    if args.grid:
        live_grid.create_layout(window,configure_final)
        return None
    area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
    with bpy.context.temp_override(window=window,area=area):bpy.ops.fal.h3_layout()
    bpy.app.timers.register(configure_final,first_interval=.3)
    return None

bpy.app.timers.register(configure,first_interval=2)



