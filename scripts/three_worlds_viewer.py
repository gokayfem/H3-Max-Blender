"""Open saved three-reference experiments in Blender. No API requests."""
import argparse
import json
from pathlib import Path
import sys
import time

import bpy
import blf

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'three-observatories.blend'))
window=bpy.context.window
results=sorted(json.loads((out/'experiment.json').read_text())['results'],key=lambda r:r['id'])
state=dict(index=0,started=0,area=None,sources={})


def choose(index):
    area=state['area'];r=results[index]
    clip=bpy.data.movieclips.load(r['video_path'],check_existing=True)
    area.spaces.active.clip=clip
    state.update(index=index,clip=clip,started=time.perf_counter())
    region=next(r for r in area.regions if r.type=='WINDOW')
    with bpy.context.temp_override(window=window,area=area,region=region):bpy.ops.clip.view_all(fit_view=True)


class THREE_OT_choose(bpy.types.Operator):
    bl_idname='three_worlds.choose'
    bl_label='Play experiment'
    index:bpy.props.IntProperty()
    def execute(self,context):
        choose(self.index);return {'FINISHED'}


bpy.utils.register_class(THREE_OT_choose)


def buttons(self,context):
    if context.area==state['area']:
        row=self.layout.row(align=True)
        for i,name in enumerate(['THREE AT ONCE','THREE SHOTS','ONE BUILDING']):
            op=row.operator('three_worlds.choose',text=name,depress=i==state['index']);op.index=i


bpy.types.CLIP_HT_header.append(buttons)


def label():
    area=bpy.context.area
    if area==state['area']:
        r=results[state['index']];gpu=(r.get('provider_timings') or {}).get('inference')
        lines=[r['title'].upper(),'3 Blender images / 1 H3 Max request',f"GPU {gpu:.2f}s | API {r['api_wait_seconds']:.2f}s | file ready {r['request_to_file_seconds']:.2f}s"]
    elif area.as_pointer() in state['sources']:
        lines=[state['sources'][area.as_pointer()]+' / GRAY BLENDER GEOMETRY']
    else:return
    blf.size(0,15)
    for j,line in enumerate(lines):
        blf.color(0,0,0,0,1);blf.position(0,15,bpy.context.region.height-27-j*23,0);blf.draw(0,line)
        blf.color(0,1,1,1,1);blf.position(0,14,bpy.context.region.height-26-j*23,0);blf.draw(0,line)


def tick():
    if state.get('clip'):
        clip=state['clip'];a=state['area']
        a.spaces.active.clip_user.frame_current=1+int((time.perf_counter()-state['started'])*clip.fps)%max(1,clip.frame_duration)
        a.tag_redraw()
    return 1/30


def split(area,direction,factor):
    with bpy.context.temp_override(window=window,area=area):bpy.ops.screen.area_split(direction=direction,factor=factor)


def layout(step=0):
    views=sorted([a for a in window.screen.areas if a.type=='VIEW_3D'],key=lambda a:(a.x,-a.y))
    if step==0:split(views[0],'VERTICAL',.23)
    elif step==1:split(views[0],'HORIZONTAL',1/3)
    elif step==2:split(max([a for a in views if a.x==views[0].x],key=lambda a:a.height),'HORIZONTAL',.5)
    else:
        main=max(views,key=lambda a:a.x);state['area']=main
        main.type='CLIP_EDITOR';main.spaces.active.show_region_ui=False;main.spaces.active.show_region_toolbar=False
        for area,name in zip(sorted([a for a in views if a!=main],key=lambda a:-a.y),['ABYSS','HELIOS','CANOPY']):
            area.type='IMAGE_EDITOR';space=area.spaces.active
            space.image=bpy.data.images.load(str(out/(name.lower()+'.png')),check_existing=True)
            space.show_region_ui=False;space.show_region_toolbar=False
            state['sources'][area.as_pointer()]=name
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(window=window,area=area,region=region):bpy.ops.image.view_all(fit_view=True)
        bpy.types.SpaceImageEditor.draw_handler_add(label,(),'WINDOW','POST_PIXEL')
        bpy.types.SpaceClipEditor.draw_handler_add(label,(),'WINDOW','POST_PIXEL')
        choose(0);bpy.app.timers.register(tick)
        def save():
            bpy.ops.wm.save_as_mainfile(filepath=str(out/'three-worlds-review.blend'))
            bpy.ops.screen.screenshot(filepath=str(out/'blender-review.png'))
        bpy.app.timers.register(save,first_interval=2)
        return None
    bpy.app.timers.register(lambda:layout(step+1),first_interval=.3)


def prepare(step=0):
    global window
    if window is None:
        windows=bpy.context.window_manager.windows
        if not windows:return .2
        window=windows[0]
    areas=list(window.screen.areas)
    try:
        if step==0:source=next(a for a in areas if a.type=='PROPERTIES');target=next(a for a in areas if a.type=='OUTLINER')
        elif step==1:source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='DOPESHEET_EDITOR')
        elif step==2:source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='PROPERTIES')
        else:layout();return None
        with bpy.context.temp_override(window=window,area=source):
            bpy.ops.screen.area_join(source_xy=(source.x+source.width//2,source.y+source.height//2),target_xy=(target.x+target.width//2,target.y+target.height//2))
    except (StopIteration,RuntimeError) as exc:print('Layout:',exc,flush=True)
    bpy.app.timers.register(lambda:prepare(step+1),first_interval=.3)


bpy.app.timers.register(prepare,first_interval=1)
