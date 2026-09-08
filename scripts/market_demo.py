"""Blender UI: gray railway district beside nine concurrent H3 video styles."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import bpy
import blf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).parent))
from market_scene import build

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--env',type=Path)
parser.add_argument('--generate',action='store_true')
parser.add_argument('--scene-only',action='store_true')
parser.add_argument('--train-motion',action='store_true',help='Animate trains from the styled first frame; camera and architecture stay fixed')
parser.add_argument('--anchors',type=Path,help='Prior sixteen-grid-status.json; use each finished style as identical first/last images')
parser.add_argument('--closeup',action='store_true',help='Fill the frame with the station district; exclude diorama edges')
parser.add_argument('--replay',action='store_true',help='Play saved outputs without generating')
parser.add_argument('--resolution',choices=['480P','768P'],default='480P')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if args.train_motion and not args.anchors:parser.error('--train-motion requires --anchors')
if args.replay and args.generate:parser.error('Choose --replay or --generate')
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if args.env:
    for line in args.env.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('FAL_KEY='):
            os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('"\'')
build(closeup=args.closeup)
scene=bpy.context.scene
scene.name='CONSERVATORY MARKET / SIXTEEN NEURAL WORLDS'
scene.render.filepath=str(out/'geometry.png')
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'conservatory-market.blend'))
stats=dict(modeled_parts=scene['modeled_parts'],mesh_faces=scene['mesh_faces'],people_count=scene['people_count'])
(out/'geometry-stats.json').write_text(json.dumps(stats,indent=2))

STYLES=[('PHOTOREAL', 'Ultra-photoreal architectural documentary. Real people in everyday clothing, authentic cast iron, limestone, glass, fruit and foliage. Natural daylight, fine skin and fabric texture. No miniature or illustration.'), ('CLAYMATION', 'Handmade plasticine stop-motion world. Chunky rounded pastel clay architecture, lumpy clay shoppers with expressive clay faces, fingerprints and sculpting marks. Mint, peach and lilac. Everything visibly clay.'), ('BOLD CARTOON', 'Flat 2D cartoon animation. Thick black contours, saturated primary colors, two-tone cel shadows, graphic cartoon people. No realistic materials or photographic shading.'), ('WATERCOLOR', 'Loose translucent watercolor animation on rough white paper. Indigo and ochre pigment blooms, bleeding edges, delicate pencil lines, washed silhouettes of people.'), ('NEON NOIR', 'Rain-dark cyberpunk night market. Electric cyan, magenta and violet light on wet black surfaces, luminous fruit displays, people in futuristic streetwear. Keep the original architecture.'), ('PORCELAIN', 'Entire world made of glossy ivory and cobalt-blue porcelain, including ceramic people. Blue painted botanical ornament, fine glaze crazing, cool studio highlights.'), ('CARVED WALNUT', 'Entire world carved from walnut, maple and cherry, including carved wooden people. Strong wood grain, gouge marks, intricate miniature joinery and warm workshop light. No paint.'), ('PAPER THEATER', 'Layered cut-paper theater with folded card buildings, paper plants and articulated paper people. Cream, scarlet, teal. Visible cut edges, paper shadows, matte surfaces.'), ('NEEDLE FELT', 'Everything needle-felted from wool. Fuzzy wool shoppers, fibrous soft market stalls, fluffy felt plants and rounded fleece architecture. Tactile pastel wool everywhere.'), ('BRICK TOYS', 'World constructed from interlocking plastic toy bricks. Visible studs and block seams, bright glossy primary colors, rigid toy minifigure shoppers. Preserve scene layout.'), ('VOXEL WORLD', 'Detailed voxel game environment made entirely from tiny cubic blocks. Cubic people and plants, stepped block geometry, bright game lighting. No smooth surfaces.'), ('OIL PAINTING', 'Animated thick impasto oil painting. Visible palette-knife ridges, expressive brushwork, luminous amber and ultramarine, painterly people. Entire image is painted.'), ('STAINED GLASS', 'Stained-glass artwork brought to life. Jewel-like translucent ruby, emerald and sapphire shapes separated by dark lead outlines. People and hall all made of glass mosaics.'), ('BLACK AND WHITE', 'Black-and-white silver gelatin cinematic documentary. Real people, deep blacks, luminous highlights, rich grayscale and subtle film grain. Absolutely no color.'), ('ANIME FILM', 'Lush hand-painted anime film background with expressive 2D anime shoppers. Delicate linework, warm golden light, pastel botanical colors, soft painted architecture and cinematic cel animation.'), ('COPPER ENGRAVING', 'Animated antique copperplate engraving. Fine dense crosshatching, etched architecture and people, sepia ink on aged cream paper. No painted color, photoreal shading or 3D materials.')]

RULES='Image 1 is the exact camera and geometry of a grand conservatory market with two gallery levels, iron arches, stalls, produce, trees, a central fountain and many human figures. Preserve camera projection, framing, architecture, stall positions and crowd distribution. Convert the gray human proxies into complete people appropriate to the medium with natural anatomy, clothing and faces. The finished chosen style must cover the entire frame from the first frame to the last. Locked camera: no zoom, pan, orbit or reframing. Buildings crossing the frame continue outside it; do not pull back to reveal a model base. No gray-to-style reveal, transition, dissolve, morph, montage, split screen, text or labels. People make small natural gestures, vendors move their hands, a few shoppers take one leisurely step along the aisle; foliage stirs and fountain water flows. Architecture and stalls remain rigid and fixed. Preserve the same style throughout; no material switching. No exposed polygon edges. MEDIUM: '

# Finish coarse Blender proxies as fully art-directed scenes, rather than recoloring meshes.
DETAILS = (" The source is an untextured structural blockout, NOT a finished surface to recolor. "
"KEEP the camera and large-scale layout, but reconstruct every visible proxy as its fully finished counterpart. "
"Each human needs a coherent face, hair, layered clothing, collars, sleeves, trouser folds, shoes and articulated hands appropriate to the chosen medium. "
"No blank wooden mannequin faces, naked jointed dolls or segmented body cylinders except deliberately designed toy styles. "
"Give neighboring vendors different clothing silhouettes and natural poses. "
"Stalls contain meticulously arranged varied produce: leafy herbs, citrus, apples, flowers, baskets, bread and stacked ceramics; avoid rows of identical generic balls. "
"Add believable wicker weave, crate joinery, folded and stitched awning fabric, leaf veins, carved fountain ornament, water droplets and small ripples. "
"Finish the iron hall with intricate brackets, flange joints, rivets, cast decorative capitals, glazed pane seams and ornate balustrade details. "
"All of this detail must be expressed in the chosen medium, never borrowed from another style. "
"Rich contact shadows separate every small object. Deep focus and carefully resolved foreground-to-background detail; no blur used to hide geometry. "
"The first frame is already fully finished. No construction or detail appearing over time. "
"Medium identity must be unmistakable across every surface and every person at thumbnail size. ")
STYLES = [(name, style + {
 'PHOTOREAL':' Full-size live-action photograph, never a scale model. Individual adult faces with natural skin, detailed fabric garments and realistic hands; mineral stone, scratched iron paint, dusty glazing, woven baskets and organic imperfect fruit.',
 'CLAYMATION':' Every head, stall and arch is hand-sculpted colored plasticine with thick soft forms, dense fingerprints and visible tool marks. Elaborate miniature costume seams and sculpted hair. Zero conventional CGI smooth plastic.',
 'BOLD CARTOON':' Exceptionally intricate hand-drawn 2D animation background with hundreds of individually inked props, designed cartoon faces and clothing folds. Confident dark contours and flat cel colors, no 3D gradients.',
 'WATERCOLOR':' Dense masterful watercolor brushwork and layered pigment granulation depict tiny baskets, faces, leaves and architecture; clearly visible paper grain, never a photographic image with a watercolor filter.',
 'NEON NOIR':' Dense rain-wet cinematic material detail, reflective puddles, layered fashionable clothing on real people, practical cyan fixtures and magenta rimlight. Rich blacks preserve detail.',
 'PORCELAIN':' Every part and every person has ornate cobalt motifs, hairline glaze cracks, sculpted ceramic folds and raised relief ornaments. Entire scene is unmistakably glossy porcelain.',
 'CARVED WALNUT':' Detailed wooden marionette people with carved faces and carved clothing folds, tiny gouge marks on every prop, contrasting wood inlays and intricate joinery.',
 'PAPER THEATER':' Tiny stacked paper folds, feather-cut leaves, cut-paper faces and clothing layers, visible edge thickness on every object. Matte colored construction paper only.',
 'NEEDLE FELT':' Thick visibly fuzzy wool fibers protrude from every silhouette; chunky needle-felt people have stitched eyes, wool hair and wool garments. All arches and stalls are soft wool sculpture, no hard wood or metal.',
 'BRICK TOYS':' Every surface consists of richly detailed interlocking bricks with obvious studs and seams, smiling toy people, intricate small brick-built produce and botanical pieces.',
 'VOXEL WORLD':' Every arch, person, leaf and produce item is visibly built from small cubic voxels. Detailed cubic silhouettes, stepped forms and voxel facial features. No conventional smooth 3D people.',
 'OIL PAINTING':' Dense expressive impasto brushstrokes model individual faces, cloth, plants and still-life merchandise. Raised oil pigment ridges catch painted light; every pixel belongs to a painting.',
 'STAINED GLASS':' Dense jewel-colored glass tesserae and thick dark lead joints form all people, produce and architecture. Bright transmitted ruby emerald and sapphire light; clear flat stained-glass identity.',
 'BLACK AND WHITE':' Detailed silver-gelatin reportage, real human faces and natural garments, deep tonal separation, iron patina and moisture; rich grayscale only.',
 'ANIME FILM':' Exceptionally detailed painted anime environment, expressive designed anime faces, delicate costume folds, tiny painted props and foliage, cinematic warm light with crisp cel characters.',
 'COPPER ENGRAVING':' Extremely fine copperplate crosshatching defines faces, clothing, baskets, leaves and architectural ornament; sepia ink on cream paper, entirely etched linework.'
}[name]) for name,style in STYLES]
RULES += DETAILS

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
            lines=['CONSERVATORY MARKET / GRAY GEOMETRY',f"{stats['modeled_parts']:,} modeled parts / {stats['mesh_faces']:,} faces",('16 saved H3 Max views / ' if args.replay else '16 parallel H3 Max views / ')+args.resolution]
            if args.anchors:lines.append('STYLE-ANCHORED REGENERATION')
            if len(state['results'])==16 and not args.replay:
                lines.append(f"All visible: {max(r['visible_seconds'] for r in state['results'].values()):.2f}s")
            if state['started']:
                lines.append(f"{16-len(state['pending'])}/16 ready" + (f" / {time.perf_counter()-state['started']:.1f}s elapsed" if state['pending'] else ''))
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
        state.update(started=time.perf_counter(),batch=state['batch']+1,results={},errors={},pending=set(range(16)))
        scene.render.filepath=str(out/'geometry.png');bpy.ops.render.render(write_still=True)
        capture=time.perf_counter()-state['started']
        bundle=image_guidance.prepare((out/'geometry.png').read_bytes(),[],'IMAGE')
        workers.clear()
        prior=json.loads(args.anchors.read_text()) if args.anchors else None
        for i,(name,style) in enumerate(STYLES):
            endpoint=live_grid.ENDPOINT
            if prior:
                anchor=out/f'anchor-{i}.jpg'
                subprocess.run(['ffmpeg','-y','-v','error','-ss','4','-i',prior['styles'][name]['video_path'],'-frames:v','1','-q:v','2',str(anchor)],check=True)
                data=anchor.read_bytes()
                prompt=('Locked-off architectural render hold. The first and last images are identical and already fully finished. Preserve that exact image composition, materials, palette, brightness, sharpness and lighting for the entire duration. All buildings, train cars, rails and stairs stay absolutely stationary. No camera motion, object motion, style change, reveal, relighting, fade, dissolve, morph, construction or transition. Only microscopic natural texture shimmer, if any. The entire clip should look like the same finished render. ')
                if args.train_motion:
                    prompt=('A single locked-off architectural shot of this exact finished scene. Only the existing commuter train moves: all connected carriages travel together very slowly and smoothly along their existing rails toward the LOWER-RIGHT corner of the image, advancing approximately one carriage length over five seconds. Screen-space direction is mandatory: the train nose moves RIGHTWARD and DOWNWARD, from image left toward image right; it never travels leftward or upward. Wheels roll naturally, cars remain rigid and coupled, and the train stays precisely on its current track. Preserve the train design and carriage count; do not create another train. All buildings, station roof, stairs, platforms, poles, overhead cables, trees, shadows and lighting remain completely stationary. Preserve the exact camera projection, framing, material style and color palette from the first frame. No zoom, pan, orbit, scene transition, dissolve, style transformation, architectural deformation or relighting. The finished rendering style is present throughout. Continuous gentle train movement only.')
                payload=live_preview.build_payload(data,prompt,args.resolution,end_image_bytes=None if args.train_motion else data)
                payload['seed']=161803+i
                endpoint=live_preview.ENDPOINT
            else:
                payload=image_guidance.payload(bundle,RULES+style,args.resolution,int(time.time())+i*103,i)
            t=threading.Thread(target=live_preview.generate,args=(key,payload,str(out),state['events'],i,capture,endpoint),daemon=True)
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
            (out/'sixteen-grid-status.json').write_text(json.dumps(report,indent=2))
            if not state['pending']:
                bpy.ops.wm.save_as_mainfile(filepath=str(out/'conservatory-market.blend'))
                bpy.app.timers.register(lambda: bpy.ops.screen.screenshot(filepath=str(out/'sixteen-grid.png')) and None, first_interval=.5)
        refresh=out/'refresh.flag'
        if args.generate and refresh.exists() and not state['pending']:
            refresh.unlink();submit()
        for a in [state['source'],*state['areas']]:a.tag_redraw()
        return .05

    def split(area,direction,factor):
        with bpy.context.temp_override(window=window,area=area):bpy.ops.screen.area_split(direction=direction,factor=factor)

    def layout(step=0):
        views=sorted([a for a in window.screen.areas if a.type=='VIEW_3D'],key=lambda a:(a.x,-a.y))
        if step==0:split(views[0],'VERTICAL',.28)
        elif step==1:split(views[-1],'VERTICAL',.25)
        elif step==2:split(views[-1],'VERTICAL',1/3)
        elif step==3:split(views[-1],'VERTICAL',.5)
        elif step<16:
            col=(step-4)//3; part=(step-4)%3
            xs=sorted(set(a.x for a in views))[1:]
            column=[a for a in views if a.x==xs[col]]
            split(max(column,key=lambda a:a.height),'HORIZONTAL',[.25,1/3,.5][part])
        else:
            source=min(views,key=lambda a:a.x);state['source']=source
            state['areas']=sorted([a for a in views if a!=source],key=lambda a:(-round(a.y/10),a.x))
            assert len(state['areas'])==16
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
                saved=json.loads((out/'sixteen-grid-status.json').read_text())
                for i,(name,_) in enumerate(STYLES):
                    if name in saved['styles']:
                        r=saved['styles'][name];state['results'][i]=r
                        live_grid._play(i,r['video_path'],dict(areas=state['areas'],window=window))
                def save_replay():
                    bpy.ops.wm.save_as_mainfile(filepath=str(out/'conservatory-market.blend'))
                    bpy.app.timers.register(lambda: bpy.ops.screen.screenshot(filepath=str(out/'sixteen-grid.png')) and None, first_interval=.5)
                bpy.app.timers.register(save_replay,first_interval=2)
            (out/'ready.flag').write_text('ready')
            return None
        bpy.app.timers.register(lambda:layout(step+1),first_interval=.18)
        return None
    def prepare_layout(step=0):
        try:
            areas=list(window.screen.areas)
            if step==0:
                source=next(a for a in areas if a.type=='PROPERTIES');target=next(a for a in areas if a.type=='OUTLINER')
            elif step==1:
                source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='DOPESHEET_EDITOR')
            elif step==2:
                source=next(a for a in areas if a.type=='VIEW_3D');target=next(a for a in areas if a.type=='PROPERTIES')
            else:
                layout();return None
            with bpy.context.temp_override(window=window,area=source):
                bpy.ops.screen.area_join(source_xy=(source.x+source.width//2,source.y+source.height//2),target_xy=(target.x+target.width//2,target.y+target.height//2))
        except (StopIteration,RuntimeError) as error:
            print('Layout cleanup:',error)
        bpy.app.timers.register(lambda:prepare_layout(step+1),first_interval=.3)
        return None
    bpy.app.timers.register(prepare_layout,first_interval=.5)

if not args.scene_only:
    if bpy.app.background:raise RuntimeError('Run without --background for the nine-pane UI')
    launch_ui()
