"""Extend the approved four styles into three native 15-second shots per film."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
import secrets
from pathlib import Path
import shutil
import subprocess
import time

import fal_client
from PIL import Image, ImageDraw
import three_worlds_experiment as core
from strong_style_films import MEDIA, SCENES

ACTION = {
    'abyss': '''A single uninterrupted observation of life in the ocean laboratory. Five jellyfish slowly pulse their bells and drift upward behind the circular window for the entire shot; their tentacles trail naturally, never rigid or multiplying. At the central table a researcher examines a small sample, carefully sets it down, and turns toward a colleague. Another researcher makes a restrained explanatory hand gesture. Gentle moving underwater light remains coherent with the medium. These small actions overlap organically rather than everyone moving at once. The camera makes only a very gentle five-percent push over all fifteen seconds, preserving the window and the complete table. No orbit, zoom jump or reframing. Architecture and equipment remain solid and stationary.''',
    'helios': '''A single uninterrupted observation of the astronomical courtyard. The armillary inner ring revolves steadily and slowly around its fixed mechanical axis for the entire fifteen seconds, turning about thirty degrees total; the outer support ring, central globe and pedestal stay structurally solid. An astronomer takes three deliberate steps along the courtyard, stops beside an instrument and looks toward the mechanism. Another astronomer checks a small handheld notebook. Subtle cloth motion and atmospheric dust create secondary movement without obscuring detail. Camera performs a very gentle lateral drift no more than three percent of the frame, keeping the entire armillary and the colonnades visible. No orbit, no dramatic zoom, no new structures or changing ring topology.''',
    'canopy': '''A single uninterrupted observation of the botanical station. Hanging leaves and broad foliage gently sway independently throughout all fifteen seconds. A botanist walks four unhurried steps along the lower gallery, pauses by a planting bench and gently touches one leaf; a second botanist checks a hanging basket. Fine droplets fall outside the galleries. The massive tree, spiral stairs and platforms remain perfectly stable and unchanged. The camera rises only a little, less than three percent of the frame, while gently approaching by three percent. Keep the same overall wide composition, all major galleries, and readable people. No orbit, sudden tilt, time-lapse growth or foliage transforming into another material.'''
}


def run(args):
    source=args.source.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    shots=out/'shots';shots.mkdir(exist_ok=True)
    for line in args.env.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('FAL_KEY='):
            os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('\"\'')
    core.REFERENCES='';core.FINISH=''
    jobs=[]
    clean_anchors=json.loads((source/'anchors.json').read_text())['rows']
    for sid,(title,medium) in MEDIA.items():
        for i,(name,scene) in enumerate(SCENES):
            folder=shots/(sid+'-'+name);folder.mkdir(exist_ok=True)
            anchor=folder/'approved-frame.jpg';meta=folder/'approved-frame.json'
            if not anchor.exists() and args.recipe:
                prior=args.recipe/'shots'/(sid+'-'+name)
                for filename in ['approved-frame.jpg','approved-frame.json']:
                    shutil.copy2(prior/filename,folder/filename)
            if not anchor.exists():
                # A fixed timestamp in a multi-scene generation can land inside a morph.
                # Prefer the individually reviewed, single-scene look-development frame.
                clean=next(r for r in clean_anchors if r['style_id']==sid and r['scene']==name)
                shutil.copy2(clean['anchor_path'],anchor)
                core.write_json(meta,dict(url=clean['url'],source=clean['anchor_path'],kind='reviewed_single_scene'))
            if meta.exists():url=json.loads(meta.read_text())['url']
            else:
                url=fal_client.upload_file(str(anchor))
                core.write_json(meta,dict(url=url,source=str(source/sid/'video.mp4'),source_second=1.5+i*5))
            prompt=f'''subject_definitions:
Image 1 is the APPROVED FINISHED {title} image of {name}. It defines the exact visual medium, characters, lighting, palette and architecture of this shot.
summary:
One uninterrupted fifteen-second {title} scene. Sustain natural, deliberately paced motion inside this already finished world from beginning to end.
retention_analysis:
Preserve Image 1's completed art direction, recognizable composition, character silhouettes, colors, architectural structure and degree of detail. Start directly inside its finished scene. There is only ONE location and ONE visual style in this entire video. Treat the reference as finished art to animate, not an image to reveal or transform. The same medium and palette must remain dominant in the very first, middle and final frames.
detailed_description:
{medium}
SCENE IDENTITY: {scene}
CHOREOGRAPHY: {ACTION[name]}
LIGHTING LOCK: Hold Image 1's time of day, exposure, sky brightness, light direction and color temperature absolutely unchanged for all fifteen seconds. No sunset, sunrise, day-to-night change, theatrical dimming, lighting reveal, spotlight takeover, flash or fade. The armillary moving does not change the sun or the sky. All existing areas remain clearly lit as in the reference until the last frame.
PACING: Fifteen seconds of real evolving action at native playback speed. Ease into motion during the first second, sustain independent movements through seconds 1-13, and let the gestures settle naturally during the last two seconds while environmental motion continues. Deliberate performances, not slow-motion footage. No repeated short loop, frozen ending, accelerated time-lapse or speed ramp.
CONTINUITY: One continuous shot with no internal cuts, dissolves, transitions, wipes, before-and-after treatment, material morphs or changes of location. Do not show a static photo, picture border, reference sheet, abstract swatch, split screen or text. Do not introduce another style. No grayscale blockout, unfinished geometry or mannequin people. Preserve small crafted or physical details in the reference while moving them coherently. Stay in the same location until the final frame; do not fade to black.
overall_soundscape: N/A
non_diegetic_music: N/A'''
            refs=[url];seed=secrets.randbelow(2_000_000_000)
            if args.recipe:
                prior=json.loads((args.recipe/'shots'/(sid+'-'+name)/'request.json').read_text())['payload']
                prompt=prior['prompt'];refs=prior['reference_image_urls']
                while seed==prior.get('seed'):seed=secrets.randbelow(2_000_000_000)
            if (folder/'request.json').exists():
                existing=json.loads((folder/'request.json').read_text())['payload']
                if existing['resolution']!=args.resolution:
                    raise ValueError('Use a new output folder when changing resolution.')
                seed=existing['seed']
            jobs.append((dict(id=sid+'-'+name,title=title+' / '+name.upper(),duration=15,aspect_ratio='16:9',direction=prompt,prompt_expansion_mode='disabled',resolution=args.resolution,seed=seed),refs))
    core.write_json(out/'plan.json',dict(resolution=args.resolution,films=4,shots_per_film=3,shot_seconds=15,film_seconds=45,source=str(source),jobs=[v for v,_ in jobs]))
    started=time.perf_counter();results=[];errors={}
    def status(state):core.write_json(out/'generation-status.json',dict(state=state,completed=len(results),total=12,errors=errors,elapsed=time.perf_counter()-started))
    status('generating')
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(core.generate_variant,shots,v,refs):v for v,refs in jobs}
        for f in as_completed(futures):
            try:results.append(f.result())
            except Exception as exc:errors[futures[f]['id']]=type(exc).__name__
            status('generating')
    run_record=dict(results=results,errors=errors,batch_seconds=time.perf_counter()-started,reference_preparation_excluded=True)
    if not (out/'generation.json').exists():
        core.write_json(out/'generation.json',run_record)
    else:
        core.write_json(out/'resume.json',run_record)
    if errors:status('failed');raise SystemExit(str(errors))
    films=[]
    for sid,(title,_) in MEDIA.items():
        dest=out/sid;dest.mkdir(exist_ok=True);file=dest/'video.mp4'
        parts=[shots/(sid+'-'+name)/'video.mp4' for name,_ in SCENES]
        if not file.exists():
            cmd=['ffmpeg','-y','-v','error']
            for path in parts:cmd+=['-i',str(path)]
            filters=';'.join(f'[{i}:v]trim=start=0:end=15,setpts=PTS-STARTPTS[v{i}]' for i in range(3))+';[v0][v1][v2]concat=n=3:v=1:a=0[v]'
            subprocess.run(cmd+['-filter_complex',filters,'-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(file)],check=True)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(file)],text=True))['streams'][0]
        assert abs(float(probe['duration'])-45)<.1,probe
        row=dict(id=sid,title=title,video_path=str(file),duration=45,resolution=args.resolution,probe=probe,shots=[r for r in results if r['id'].startswith(sid)])
        films.append(row);core.write_json(dest/'result.json',row)
    core.write_json(out/'films.json',dict(results=films,assembly='Three native 15-second generations, clean hard cuts, no retiming or loops.'))
    for name in ['three-observatories.blend','sources.json','abyss.png','helios.png','canopy.png']:
        if not (out/name).exists():shutil.copy2(source/name,out/name)
    core.write_json(out/'styles.json',[dict(id=r['id'],title=r['title'],duration=45,resolution=args.resolution) for r in films])
    core.write_json(out/'live-status.json',dict(state='complete',results=films,errors={},total=4))
    contact=Image.new('RGB',(1440,4*222),(20,20,20));draw=ImageDraw.Draw(contact)
    for y,row in enumerate(films):
        for x,t in enumerate([1,12,16,27,31,42]):
            jpg=out/row['id']/f'check-{t}.jpg'
            subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',row['video_path'],'-frames:v','1','-q:v','2',str(jpg)],check=True)
            im=Image.open(jpg);im.thumbnail((238,180));contact.paste(im,(x*240,y*222+27))
            draw.text((x*240+4,y*222+5),row['title']+' / '+str(t)+'s',fill='white')
    contact.save(out/'contact.jpg',quality=92)
    cards=''.join(f'<article><h2>{html.escape(r["title"])}</h2><video src="{r["id"]}/video.mp4" controls loop muted playsinline preload="metadata"></video><a href="{r["id"]}/video.mp4" download>Download 45-second film</a></article>' for r in films)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Four styles · 45 seconds</title><style>body{background:#151617;color:#f8f5eb;font:16px system-ui;max-width:1600px;margin:32px auto;padding:0 24px}h1{font-size:38px;font-weight:500}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}h2{font-size:19px;font-weight:500}video{width:100%;display:block;margin-bottom:12px}a{color:#daceaa}button{padding:12px 20px;cursor:pointer}</style><h1>Four styles. Three worlds. 45 seconds each.</h1><p>New native 768p H3 Max footage · three 15-second scenes per film · normal playback speed.</p><button onclick="document.querySelectorAll(\'video\').forEach(v=>{v.currentTime=0;v.play()})">Play all together</button><main>'+cards+'</main>',encoding='utf-8')
    status('complete');print('COMPLETE '+str(out/'index.html'),flush=True)
    gallery=out/'index.html';gallery.write_text(gallery.read_text(encoding='utf-8').replace('New native 768p H3 Max footage',f'New H3 Max {args.resolution} footage'),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--env',type=Path,required=True)
    parser.add_argument('--resolution',choices=['480P','768P','1080P'],default='768P');parser.add_argument('--recipe',type=Path,help='Reuse approved shot prompts and images, with fresh seeds, in a new output folder.')
    run(parser.parse_args())
