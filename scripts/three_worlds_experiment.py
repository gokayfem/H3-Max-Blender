"""Three images -> one H3 video, tested with three distinct composition strategies.

Submits once per variant and persists request IDs before waiting. A resumed run
retrieves an existing request instead of submitting another paid generation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
from pathlib import Path
import secrets
import time
import urllib.request

import fal_client
from PIL import Image

ENDPOINT='minimax/h3-max/reference-to-video'
DOCS='https://fal.ai/models/minimax/h3-max/reference-to-video/llms.txt'

REFERENCES='''Image 1 is ABYSS: a deep-ocean research observatory, its repeated pressure-hull arches, giant circular rear viewing window, jellyfish beyond the glass, central sample table and adult researchers.
Image 2 is HELIOS: a desert astronomical observatory, the central three-ring brass armillary sphere, terraced stone courtyard, two side colonnades, solar mirror arrays and adult astronomers.
Image 3 is CANOPY: a tropical rainforest research station, living central tree, spiral stair, three annular elevated galleries, suspended plants, seedling benches and adult botanists.
These are THREE DIFFERENT LOCATIONS, not three views of one object. Every image is an untextured gray Blender architectural proxy. Preserve each location's defining geometry and its own human scale. Replace gray proxies with fully finished photoreal materials and natural adult people in work clothes, with coherent hands, faces and fabric folds. Do not reproduce gray polygon meshes, a tabletop diorama, or the empty gray background. Complete each environment beyond its structures.'''

FINISH='''ABYSS has dark titanium pressure frames, thick clear optical glass, cyan deep-water caustics, floating translucent jellyfish and illuminated amber instruments. HELIOS has sun-warmed sandstone with fine chipped edges, engraved brushed brass mechanisms, sharp desert sunlight and cobalt sky. CANOPY has wet teak, weathered steel, dense living fern and orchid foliage, humid emerald light and tiny rain droplets. Resolve joints, screws, glass reflections, fabric, leaf venation and fine texture. Fully finished color, lighting and materials exist from the very first frame. No gray-to-color reveal, construction, style morphing, typography, logos or subtitles. Tasteful high-end architectural cinematography, deep focus, realistic scale.'''

VARIANTS=[
    dict(id='01-simultaneous',title='Three worlds / one inference',duration=5,aspect_ratio='21:9',
         direction='''Create one single video with THREE FIXED, EQUAL VERTICAL PANELS arranged horizontally, all visible simultaneously throughout five seconds. This is a triptych, never a sequential montage. The left panel exclusively depicts Image 1 ABYSS; the middle exclusively depicts Image 2 HELIOS; the right exclusively depicts Image 3 CANOPY. There are exactly two thin stationary black vertical separators at one-third and two-thirds of the frame. Compose each complete environment inside its own panel; never allow architecture or objects to cross separators. Match the reference camera within each panel as closely as the portrait panel allows. No panel duplication, no location blending, no cuts or transitions. All three cameras are locked. Left: jellyfish visibly pulse upward behind the window and a researcher slowly reaches across the table. Middle: the solid brass armillary inner ring turns a modest ten degrees and an astronomer takes one step. Right: leaves sway, rain falls outside the galleries and a botanist walks two steps on the lower walkway. These three independent actions occur at the SAME TIME, smoothly for the entire clip.'''),
    dict(id='02-three-shot-film',title='Three references / three shots',duration=9,aspect_ratio='16:9',
         direction='''A precisely ordered three-shot architectural short film. Each scene occupies the ENTIRE video frame. No split screen or collage. [Shot 1] From 0 to 3 seconds, Image 1 ABYSS only: a gentle camera push toward its circular underwater window while jellyfish pulse in the blue water and the researchers work. [Shot 2] At exactly 3 seconds make a clean hard cut to Image 2 HELIOS only: a gentle camera push toward the brass armillary sphere as its inner ring slowly rotates under intense desert sunlight. [Shot 3] At exactly 6 seconds make a clean hard cut to Image 3 CANOPY only: a gentle camera push toward the rainforest spiral stair as leaves move in the rain and a botanist walks across a gallery. End at 9 seconds in CANOPY. Exactly three shots in that order, never return to an earlier shot. Changes between scenes are instantaneous editorial cuts, not morphs, dissolves or simulated travel. Within each shot the scene and its material treatment remain stable.'''),
    dict(id='03-impossible-building',title='One building / three climates',duration=5,aspect_ratio='21:9',
         direction='''A single wide architectural sectional view of one impossible museum with three adjacent, equal-sized tall exhibition rooms. We see all three rooms simultaneously through their open front wall. The left room contains Image 1 ABYSS, the central room contains Image 2 HELIOS, and the right room contains Image 3 CANOPY. Thick structural piers and glazed partitions physically separate the rooms; this is one continuous building, not an editorial split screen. A single continuous floor slab and roof beam connect all three rooms. Adapt reference viewpoints to one coherent front three-quarter architectural perspective while preserving each room's distinctive centerpiece, repeated structures and internal layout. Blue underwater light stays in the left room, warm desert sunlight in the middle, emerald rainy forest in the right. Inhabitants stay inside their respective rooms. During the continuous locked camera shot, jellyfish pulse, the brass armillary inner ring rotates slowly, and hanging leaves sway with falling rain. All three environments move simultaneously. No camera motion, cuts, reveals, transitions, material changes, blended ecosystems or objects migrating between rooms.''')
]


def write_json(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(path)


def generate_variant(out,variant,urls):
    folder=out/variant['id'];folder.mkdir(exist_ok=True)
    record=folder/'result.json'
    if record.exists():return json.loads(record.read_text())
    request_file=folder/'request.json'
    started=time.perf_counter()
    if request_file.exists():
        saved=json.loads(request_file.read_text())
        if not saved.get('request_id'):
            raise RuntimeError(f"{variant['id']}: prior submission has no confirmed ID; inspect it before resubmitting")
        handle=fal_client.SyncClient().get_handle(ENDPOINT,saved['request_id'])
        resumed=True
    else:
        payload=dict(prompt=variant.get('priority','')+'\n\n'+REFERENCES+'\n\n'+variant['direction']+'\n\n'+FINISH,
                     reference_image_urls=urls,duration=variant['duration'],resolution=variant.get('resolution','768P'),
                     aspect_ratio=variant['aspect_ratio'],seed=variant.get('seed',secrets.randbelow(2_000_000_000)),
                     prompt_expansion_mode=variant.get('prompt_expansion_mode','balanced'),sync_mode=False,enable_safety_checker=True)
        saved=dict(endpoint=ENDPOINT,verified_docs=DOCS,payload=payload,submitted_at=time.time())
        write_json(request_file,saved)
        handle=fal_client.submit(ENDPOINT,arguments=payload)
        saved['request_id']=handle.request_id;write_json(request_file,saved)
        resumed=False
        print(f"SUBMITTED {variant['id']}",flush=True)
    response=handle.get()
    api_seconds=time.perf_counter()-started
    # Persist the response before download so an interrupted download never loses it.
    write_json(folder/'response.json',response)
    video=folder/'video.mp4'
    with urllib.request.urlopen(response['video']['url'],timeout=180) as stream:
        video.write_bytes(stream.read())
    result=dict(id=variant['id'],title=variant['title'],video_path=str(video.resolve()),
                duration=variant['duration'],resolution=saved['payload']['resolution'],seed=response.get('seed'),
                request_id=saved['request_id'],api_wait_seconds=api_seconds,
                download_seconds=time.perf_counter()-started-api_seconds,
                request_to_file_seconds=time.perf_counter()-started,
                resumed=resumed,provider_timings=response.get('timings'))
    write_json(record,result)
    print(json.dumps(result),flush=True)
    return result


def gallery(out,results,sources):
    cards=[]
    for r in sorted(results,key=lambda r:r['id']):
        timing=r.get('provider_timings') or {}
        cards.append(f'''<article><h2>{html.escape(r['title'])}</h2>
        <video src="{r['id']}/video.mp4" controls loop muted playsinline preload="metadata"></video>
        <p>{r['duration']}s · 768p · API wait {r['api_wait_seconds']:.2f}s · GPU inference {timing.get('inference','unreported')}s</p></article>''')
    (out/'index.html').write_text('''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Three worlds · H3 Max</title>
    <style>body{margin:40px auto;max-width:1500px;background:#101211;color:#eee;font:16px system-ui;padding:0 24px}h1{font-size:44px;font-weight:500}h2{font-weight:500}p{color:#aaa;line-height:1.6}video{width:100%;display:block;background:#000}article{margin:50px 0}aside{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}img{width:100%}a{color:#c9dfae}</style>
    <h1>Three worlds. Three images. One request per film.</h1><p>Blender defines the geometry. H3 Max interprets three image references together. These are generative approximations, not physically exact renders. Source capture and upload are separate from API timing.</p><aside>'''+
    ''.join(f'<div><img src="{s["name"].lower()}.png"><p>{s["name"]} · {s["faces"]:,} faces</p></div>' for s in sources['scenes'])+
    '</aside>'+''.join(cards)+'</html>',encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--env',type=Path);p.add_argument('--generate',action='store_true')
    p.add_argument('--upload-only',action='store_true',help='Upload scene images without generating videos')
    args=p.parse_args();out=args.output.resolve()
    sources=json.loads((out/'sources.json').read_text())
    if not args.generate and not args.upload_only:raise SystemExit('Use --generate for videos or --upload-only to prepare scene references.')
    if args.env:
        for line in args.env.read_text(encoding='utf-8-sig').splitlines():
            if line.strip().startswith('FAL_KEY='):os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('\"\'')
    if not os.environ.get('FAL_KEY'):raise RuntimeError('FAL_KEY is missing')
    cached_run=all((out/v['id']/'result.json').exists() for v in VARIANTS)
    batch=time.perf_counter()
    upload_file=out/'uploaded-references.json'
    if upload_file.exists():uploads=json.loads(upload_file.read_text())
    else:
        urls=[];t=time.perf_counter()
        for scene in sources['scenes']:
            jpg=out/(scene['name'].lower()+'.jpg')
            Image.open(scene['image']).convert('RGB').save(jpg,quality=92)
            urls.append(fal_client.upload_file(str(jpg)))
        uploads=dict(urls=urls,upload_seconds=time.perf_counter()-t);write_json(upload_file,uploads)
    if args.upload_only:
        print('Scene references ready: '+str(upload_file));return
    results=[];errors={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(generate_variant,out,v,uploads['urls']):v for v in VARIANTS}
        for future in as_completed(futures):
            v=futures[future]
            try:results.append(future.result())
            except Exception as exc:
                errors[v['id']]=type(exc).__name__
                print(f"ERROR {v['id']}: {type(exc).__name__}",flush=True)
    if not cached_run or not (out/'experiment.json').exists():
        write_json(out/'experiment.json',dict(results=results,errors=errors,
                   batch_wall_seconds=time.perf_counter()-batch,upload_seconds=uploads['upload_seconds'],
                   run_kind='cached_review' if cached_run else 'generation_or_resume'))
    gallery(out,results,sources)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
