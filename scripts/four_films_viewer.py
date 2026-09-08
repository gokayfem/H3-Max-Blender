"""Four film results beside three Blender reference captures; polls saved API results."""
import argparse,json,time,sys
from pathlib import Path
import bpy,blf

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
out=p.parse_args(sys.argv[sys.argv.index('--')+1:]).output.resolve()
bpy.ops.wm.open_mainfile(filepath=str(out/'three-observatories.blend'))
styles=json.loads((out/'styles.json').read_text())
state=dict(window=None,areas=[],sources={},loaded={},results={},status={},synced=False,scheduled_start=None)

def text_overlay():
    a=bpy.context.area
    if a.as_pointer() in state['sources']:
        name=state['sources'][a.as_pointer()]
        lines=[name+' / BLENDER GEOMETRY']
        if name=='ABYSS':
            status=state['status'];elapsed=status.get('elapsed_seconds',0)
            if status.get('state')=='generating':elapsed=time.time()-status['started_at']
            if styles[0].get('duration',15)>15:
                lines += ['4 STYLES / 3 WORLDS', '45-second films / native playback']
            else:lines += ['3 images per request / 4 requests',f"{len(state['loaded'])}/4 films ready | {elapsed:.1f}s"]
    elif a in state['areas']:
        i=state['areas'].index(a);r=state['results'].get(i)
        lines=[styles[i]['title']+f" / {styles[i].get('duration',15)}s / 3 SCENES"]
        if r and r.get('shots'):lines += [f"H3 MAX / {r.get('resolution','768P')} / 24 fps"]
        elif r:lines += [f"GPU {r['provider_timings']['inference']:.2f}s | API {r['api_wait_seconds']:.2f}s"]
        else:lines += ['Generating...' if state['status'].get('state')=='generating' else 'Ready to generate']
    else:return
    blf.size(0,14)
    for j,t in enumerate(lines):
        blf.position(0,13,bpy.context.region.height-25-j*21,0);blf.color(0,0,0,0,1);blf.draw(0,t)
        blf.position(0,12,bpy.context.region.height-24-j*21,0);blf.color(0,1,1,1,1);blf.draw(0,t)

def tick():
    try:status=json.loads((out/'live-status.json').read_text());state['status']=status
    except (OSError,ValueError):return .1
    for r in status.get('results',[]):
        i=next(i for i,s in enumerate(styles) if s['id']==r['id'])
        if i in state['loaded']:continue
        a=state['areas'][i];clip=bpy.data.movieclips.load(r['video_path'],check_existing=True)
        a.spaces.active.clip=clip;state['loaded'][i]=dict(clip=clip,started=time.perf_counter());state['results'][i]=r
        region=next(r for r in a.regions if r.type=='WINDOW')
        with bpy.context.temp_override(window=state['window'],area=a,region=region):bpy.ops.clip.view_all(fit_view=True)
    if len(state['loaded'])==4 and not state['synced']:
        started=time.perf_counter()
        for data in state['loaded'].values():data['started']=started
        state['synced']=True
        (out/'all-visible.json').write_text(json.dumps(dict(visible_at=time.time(),seconds_since_batch=time.time()-status.get('started_at',time.time()))))
        def save():
            bpy.ops.wm.save_as_mainfile(filepath=str(out/'four-films-review.blend'))
            bpy.ops.screen.screenshot(filepath=str(out/'four-films-blender.png'))
        bpy.app.timers.register(save,first_interval=2)
    schedule=out/'playback-start.json'
    if schedule.exists():
        try:
            epoch=json.loads(schedule.read_text())['epoch']
            if epoch!=state['scheduled_start']:
                state['scheduled_start']=epoch
                for data in state['loaded'].values():data['started']=time.perf_counter()+epoch-time.time()
        except (OSError,ValueError,KeyError):pass
    hold=(out/'playback-hold.flag').exists()
    for i,data in state['loaded'].items():
        clip=data['clip'];elapsed=max(0,time.perf_counter()-data['started'])
        state['areas'][i].spaces.active.clip_user.frame_current=1 if hold else 1+int(elapsed*clip.fps)%max(1,clip.frame_duration)
    for a in state['window'].screen.areas:a.tag_redraw()
    return 1/30

def split(a,direction,factor):
    with bpy.context.temp_override(window=state['window'],area=a):bpy.ops.screen.area_split(direction=direction,factor=factor)

def layout(step=0):
    views=sorted([a for a in state['window'].screen.areas if a.type=='VIEW_3D'],key=lambda a:(a.x,-a.y))
    if step==0:split(views[0],'VERTICAL',.23)
    elif step==1:split(views[0],'HORIZONTAL',1/3)
    elif step==2:split(max([a for a in views if a.x==views[0].x],key=lambda a:a.height),'HORIZONTAL',.5)
    elif step==3:split(max(views,key=lambda a:a.x),'VERTICAL',.5)
    elif step==4:split([a for a in views if a.x>views[0].x][0],'HORIZONTAL',.5)
    elif step==5:split(max(views,key=lambda a:a.x),'HORIZONTAL',.5)
    else:
        sx=min(a.x for a in views)
        state['areas']=sorted([a for a in views if a.x>sx],key=lambda a:(-a.y,a.x))
        for a in state['areas']:
            a.type='CLIP_EDITOR';a.spaces.active.show_region_ui=False;a.spaces.active.show_region_toolbar=False
        for a,name in zip(sorted([a for a in views if a.x==sx],key=lambda a:-a.y),['ABYSS','HELIOS','CANOPY']):
            a.type='IMAGE_EDITOR';a.spaces.active.image=bpy.data.images.load(str(out/(name.lower()+'.png')))
            a.spaces.active.show_region_ui=False;a.spaces.active.show_region_toolbar=False
            state['sources'][a.as_pointer()]=name
            region=next(r for r in a.regions if r.type=='WINDOW')
            with bpy.context.temp_override(window=state['window'],area=a,region=region):bpy.ops.image.view_all(fit_view=True)
        bpy.types.SpaceImageEditor.draw_handler_add(text_overlay,(),'WINDOW','POST_PIXEL')
        bpy.types.SpaceClipEditor.draw_handler_add(text_overlay,(),'WINDOW','POST_PIXEL')
        bpy.app.timers.register(tick);(out/'viewer-ready.flag').write_text('ready')
        return None
    bpy.app.timers.register(lambda:layout(step+1),first_interval=.25)

def prepare(step=0):
    if state['window'] is None:
        if not bpy.context.window_manager.windows:return .2
        state['window']=bpy.context.window_manager.windows[0]
    areas=list(state['window'].screen.areas)
    try:
        if step==0:source=next(a for a in areas if a.type=='PROPERTIES');target=next(a for a in areas if a.type=='OUTLINER')
        elif step==1:source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='DOPESHEET_EDITOR')
        elif step==2:source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='PROPERTIES')
        else:layout();return None
        with bpy.context.temp_override(window=state['window'],area=source):
            bpy.ops.screen.area_join(source_xy=(source.x+source.width//2,source.y+source.height//2),target_xy=(target.x+target.width//2,target.y+target.height//2))
    except (StopIteration,RuntimeError) as exc:print('Layout:',exc,flush=True)
    bpy.app.timers.register(lambda:prepare(step+1),first_interval=.3)

bpy.app.timers.register(prepare,first_interval=1)
