"""Resolve a strong style on each scene first, then animate three finished image anchors.

Look development: 12 five-second H3 requests, whose finished frames are cached.
Final animation: four 15-second requests, each receiving three finished images.
Prep and final generation timings are recorded separately, never conflated.
"""
import argparse,json,os,subprocess,time,shutil
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import fal_client
import three_worlds_experiment as core

MEDIA={
'01-photoreal':('PHOTOREAL', '''VISUAL MEDIUM: premium full-size live-action architectural cinema, with the fine physical credibility of a large-format feature film, not an architectural model. Optical glass has real thickness, restrained distortion at the edge and tiny surface imperfections. Metal has machined joints, screws, brushed grain and fine wear. Stone has subtle mineral variation, bevels, pores and mortar. Timber has a believable fine grain and dampness. Light bounces naturally through the room and resolves individual material surfaces. Keep deep detail throughout, without toy-like depth of field.
CHARACTERS: believable fictional adult researchers with individual human faces, natural eyes and hair, articulated fingers and complete tailored workwear. Clothes have seams, collars, stitched pockets and natural folds. No segmented mannequin limbs, featureless heads, plastic skin or identical generic people.
COLOR AND LIGHT: a refined photographic color grade with rich blue-green shadows and warm amber highlights. Each location has physically appropriate light but the same restrained cinematic contrast and material realism. Finish every surface and every person; never show flat gray blockout areas.'''),
'02-clay':('CLAYMATION', '''VISUAL MEDIUM: an exuberantly colorful, entirely handmade plasticine stop-motion feature film. Every single thing is made of thick soft sculpted clay. The material has visibly pressed fingerprints, thumb dents, tiny tool scrapes, rounded seams and slightly uneven hand-rolled edges. Architecture has exaggerated chunky proportions, gently bowed pillars and thick friendly rounded arches. All railings are hand-rolled clay cords. Floor tiles are thick irregular pastel clay squares. This must look like a hand-built stop-motion set photographed with a real camera, never a smooth 3D computer model wearing pastel colors.
PALETTE: luminous mint green, candy peach, buttery yellow and powder lavender, with restrained coral accents. Apply this palette to all three locations without reverting to gray concrete, brown wood, shiny metal or realistic green plants. Sky, water, instruments, trunks, leaves, furniture and people all use this same joyful clay palette.
CHARACTERS: charming chunky clay adults with large expressive sculpted heads, round noses, inset clay eyes, clay eyebrows, hand-sculpted hair, broad mitten-like hands, softly rounded shoes, overalls and little clay coat pockets. Use visible face expressions and appealing hand-designed silhouettes. Heads are about one-fifth of body height. No thin jointed mannequins.
LIGHT: warm miniature studio illumination with broad soft highlights and visible contact shadows. The clay remains matte and palpably waxy. Motion has the appealing deliberate poses of handcrafted stop-motion while the video plays at its native rate. Shapes remain rigid between poses. Every shot must be instantly recognizable as colorful claymation at thumbnail size.'''),
'03-cartoon':('COLORFUL CARTOON', '''VISUAL MEDIUM: spectacular colorful hand-drawn TWO-DIMENSIONAL cartoon animation with elaborate painted backgrounds. Every architectural contour has a bold confident dark-navy ink outline. Line widths vary intentionally: thick outer silhouettes, finer inner details. Surfaces are crisp opaque flat fields with only one sharply cut cel-shadow tone. No photographic reflections, no realistic 3D gradients, no generic shaded polygon render, no soft ambient-occlusion look. Perspective is carefully DRAWN, not visibly rendered in 3D.
PALETTE: saturated turquoise, electric sky blue, warm sunflower yellow, coral red and creamy ivory with deep navy contours. Every location shares this same high-energy animation color script. Large bright colored areas must dominate, not gray or brown. Water is graphic cyan with flat white reflection shapes; desert stone is golden yellow and coral; trees and plants are graphic turquoise and mint with navy contours.
CHARACTERS: expressive cartoon scientists with appealing exaggerated faces, clearly inked eyes and eyebrows, varied colorful hairstyles, bright coats or overalls, readable gloves and shoes. Heads are large and expressive, poses clear, hands deliberately drawn. Different adults have distinct silhouettes and outfits. Animation uses designed key poses and natural gestures. Never depict blank cylindrical heads or narrow mannequin limbs.
FINISH: intricate tiny inked architecture, hand-painted background accents, stylized clouds and designed foliage, clear layer separation. The entire frame looks like an expensive colorful cartoon feature, not a 3D scene with black outlines added. One consistent ink weight and palette throughout all three locations.'''),
'04-paper':('PAPER THEATER', '''VISUAL MEDIUM: an extraordinarily detailed PHYSICAL CUT-PAPER stop-motion film. Every structure and character is constructed from many layers of thick matte colored paper and folded cardstock. Close and medium details reveal paper fibers, blade-cut edges, scored folds, visible sheet thickness and stacked layers. Tall arches are laminated paper ribbons, columns are folded-card prisms, circular mechanisms are precisely cut card rings, leaves are individual folded paper shapes. Avoid smooth solid 3D tubes, metal, concrete or real wood: the construction medium is visibly paper everywhere.
PALETTE: bold vermilion, deep teal, warm ivory, golden mustard and a few dark indigo accents. The same limited paper stock colors recur in all scenes. Contrast large clean paper planes with tiny carefully cut details. Do not copy an abstract reference image's swirly composition into the scene.
CHARACTERS: articulated paper-doll adults with layered cut-paper faces, expressive eyes cut from dark paper, folded hair silhouettes, multiple costume layers, scored jacket folds and hinged paper arms. Their construction must remain flat or folded cardstock, not rounded clay bodies or realistic humans.
LIGHT AND MOTION: warm raking miniature studio light casts delicate physical shadows between paper layers, making every cut edge readable. Articulated stop-motion gestures and gentle paper foliage movement. Rich precise craftsmanship with no shiny plastic, no faded generic CGI and no gray unfinished surfaces.''')
}

SCENES=[
('abyss','A deep-ocean research observatory. Repeated concentric pressure-tunnel arches recede toward one giant circular rear observation window. Five jellyfish float behind that window. A broad central round sample table holds individual small instruments, and a few adult researchers stand around it. Low railings and instrument consoles run down both sides. The source defines this scene layout, but all visible construction must be rebuilt in the chosen medium. Keep the round window and arches readily recognizable. Jellyfish pulse upward, one researcher gently reaches across the table.'),
('helios','A desert astronomical observatory. A tall armillary sphere made of three intersecting circular rings around one central globe stands on a circular pedestal in the middle of a terraced rectangular courtyard. Colonnades frame the left and right sides. Small solar reflectors lie beyond. A few adult astronomers provide scale. Preserve the recognizable rings, central globe, pedestal and side colonnades while remaking their complete shape language in the chosen medium. The inner ring rotates slowly; an astronomer walks two steps.'),
('canopy','A lush tropical botanical research station. One enormous living tree is surrounded by a continuous spiral staircase and three circular elevated galleries with railings. Botanical benches, hanging baskets, broad-leaf plants and orchids fill the surroundings; a few adult botanists stand on the lower walkway. The source defines the central tree-and-spiral composition. Rebuild all of it in the chosen medium, including the tree, every leaf and every character. Leaves visibly sway and a botanist takes a few steps along the walkway.')]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--styles',type=Path,required=True);p.add_argument('--env',type=Path,required=True);p.add_argument('--stage',choices=['prepare','anchors','films'],required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.stage=='prepare':
        for name in ['three-observatories.blend','sources.json','abyss.png','helios.png','canopy.png']:
            if not (out/name).exists():shutil.copy2(args.source/name,out/name)
        sources=json.loads((out/'sources.json').read_text())
        for s in sources['scenes']:s['image']=str(out/(s['name'].lower()+'.png'))
        core.write_json(out/'sources.json',sources)
        core.write_json(out/'styles.json',[dict(id=sid,title=title,duration=15) for sid,(title,_) in MEDIA.items()])
        core.write_json(out/'live-status.json',dict(state='ready',results=[],errors={},total=4))
        return
    for line in args.env.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('FAL_KEY='):os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('\"\'')
    styles={r['id']:r for r in json.loads(args.styles.read_text())['styles']}
    gray=json.loads((args.source/'uploaded-references.json').read_text())['urls']
    core.REFERENCES='';core.FINISH=''
    if args.stage=='anchors':
        started=time.perf_counter();jobs=[]
        for sid,(title,medium) in MEDIA.items():
            for i,(name,scene) in enumerate(SCENES):
                # Repeated style images deliberately outweigh the single grayscale proxy.
                refs=[styles[sid]['url']]*6+[gray[i]]
                prompt=f'''subject_definitions:
Images 1 through 6 are identical views of the chosen abstract material and palette, used ONLY as style evidence. Image 7 is the spatial layout of {name}. These images do not describe a timeline.
summary:
A finished {title} interpretation of the scene in Image 7. Style controls the entire visual world.
retention_analysis:
Retain only Image 7's recognizable major spatial arrangement. REPLACE its gray surfaces, proxy human anatomy, geometric faceting and generic render appearance. Copy medium and palette from Images 1-6, never their abstract composition. All characters, architecture and surfaces use the chosen style.
detailed_description:
{medium}
{scene}
One continuous five-second shot with a locked camera, already fully finished from the first frame. Do not display the abstract style reference, no material swatch opening, no gray-to-style reveal, no morph or scene transition, no lettering. Every portion of the image must be resolved in the chosen medium. Fill the frame with the scene, no visible diorama base or empty gray background.
overall_soundscape: N/A
non_diegetic_music: N/A'''
                jobs.append((dict(id=sid+'-'+name,title=title+' / '+name,duration=5,aspect_ratio='16:9',direction=prompt,prompt_expansion_mode='disabled'),refs,sid,name))
        rows=[]
        def work(job):
            variant,refs,sid,name=job;r=core.generate_variant(out/'lookdev',variant,refs)
            anchor=out/'lookdev'/variant['id']/'anchor.jpg'
            subprocess.run(['ffmpeg','-y','-v','error','-ss','3.7','-i',r['video_path'],'-frames:v','1','-q:v','2',str(anchor)],check=True)
            meta=anchor.with_suffix('.json')
            if meta.exists():url=json.loads(meta.read_text())['url']
            else:url=fal_client.upload_file(str(anchor));core.write_json(meta,dict(url=url))
            return dict(style_id=sid,scene=name,anchor_path=str(anchor),url=url,result=r)
        (out/'lookdev').mkdir(exist_ok=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            for row in pool.map(work,jobs):rows.append(row)
        core.write_json(out/'anchors.json',dict(rows=rows,preparation_seconds=time.perf_counter()-started))
        core.write_json(out/'lookdev'/'experiment.json',dict(results=[r['result'] for r in rows]))
        print('ANCHORS COMPLETE',flush=True);return
    anchors=json.loads((out/'anchors.json').read_text())
    variants=[]
    for sid,(title,medium) in MEDIA.items():
        refs=[next(r['url'] for r in anchors['rows'] if r['style_id']==sid and r['scene']==name) for name,_ in SCENES]
        prompt=f'''subject_definitions:
Image 1 is the FINISHED {title} underwater observatory. Image 2 is the FINISHED {title} desert observatory. Image 3 is the FINISHED {title} botanical tree station.
summary:
A fifteen-second {title} film with THREE shots, five seconds each. The same medium, palette, character design and craftsmanship connect all three locations.
retention_analysis:
Preserve each reference image's finished medium, saturated palette, character design, material finish and recognizable scene layout. The references are finished art, not sketches. Do not reinterpret them as gray geometry or change art direction at a cut.
detailed_description:
{medium}
[Shot 1] From 0 to 5 seconds: the finished underwater scene of Image 1 fills the entire frame. Gentle slow camera push toward the round jellyfish window; jellyfish visibly rise and pulse; a researcher reaches across the table. Every surface retains the exact reference medium.
[Shot 2] At 5 seconds, HARD CUT to Image 2, the finished desert scene, full frame. The armillary inner ring turns slowly and an astronomer takes two steps. Gentle slow camera push. Preserve the same medium and art direction as Shot 1.
[Shot 3] At 10 seconds, HARD CUT to Image 3, the finished botanical station, full frame. Foliage sways, a botanist walks along a gallery. Gentle slow camera push. Preserve the same medium and art direction until the film ends at 15 seconds.
Exactly three full-frame scenes in order, two clean editorial cuts, no triptych, no split screen. No dissolve, no morph, no material reveal, no abstract style image, no text or logos. Only the location changes at the cuts; the visual medium never changes.
overall_soundscape: N/A
non_diegetic_music: N/A'''
        variants.append((dict(id=sid,title=title,duration=15,aspect_ratio='16:9',direction=prompt,prompt_expansion_mode='disabled'),refs))
    core.write_json(out/'styles.json',[v for v,_ in variants]);start=time.perf_counter();epoch=time.time();results=[];errors={}
    def status(mode):core.write_json(out/'live-status.json',dict(state=mode,started_at=epoch,elapsed_seconds=time.perf_counter()-start,results=sorted(results,key=lambda r:r['id']),errors=errors,total=4))
    status('generating')
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(core.generate_variant,out,v,refs):v for v,refs in variants}
        for f in as_completed(futures):
            try:results.append(f.result())
            except Exception as exc:errors[futures[f]['id']]=type(exc).__name__
            status('generating')
    status('complete');core.write_json(out/'experiment.json',dict(results=results,errors=errors,final_batch_seconds=time.perf_counter()-start,lookdev_seconds=anchors['preparation_seconds']))
    core.gallery(out,results,json.loads((args.source/'sources.json').read_text()))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
