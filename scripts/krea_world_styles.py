"""Object-free Krea 2 Turbo medium references for the four scene films."""
import argparse,json,os,secrets,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import fal_client
from three_worlds_experiment import write_json

STYLES={
 '01-photoreal':('PHOTOREAL','A full-frame abstract photographic study of premium physical surfaces: brushed dark titanium with fine directional scratches, optical glass with a clear luminous edge, warm brass with minute engraved grooves, porous honey limestone, wet fine-grained teak. The surfaces intersect as enormous cropped abstract bands. Cinematic controlled illumination, deep blue-green shadows and warm amber highlights, physically convincing specular reflections, minute surface imperfections and razor-resolved microtexture. Every part is impeccably photographic, elegant high-end architectural material library. No CGI plastic.'),
 '02-clay':('CLAYMATION','An extraordinary full-frame abstract plasticine relief, entirely handmade sculpted clay. Interlocking softly rounded fields and slow rolling ridges in sage mint, peach, butter yellow and dusty lavender. Thousands of visible fine fingerprints, tiny pressed seams, sculpting-tool nicks and matte waxy clay texture. Soft miniature studio lighting, warm contact shadows, every surface palpably hand-molded. Premium stop-motion feature-film craft. Dense tactile detail, not smooth computer-generated geometry.'),
 '03-cartoon':('CEL CARTOON','An exceptionally designed abstract hand-drawn 2D animation color script. Interlocking graphic fields of deep navy, turquoise, coral red, warm ochre and pale cream. Bold elegantly varied black ink outlines, angular and curved hand-drawn edges, flat cel color and a strict two-tone shadow system. Fine intentional ink details and subtle painted cel texture, crisp high-quality animated feature production design. Absolutely no 3D shading, photography, clay or rendered volume.'),
 '04-paper':('PAPER THEATER','An extraordinarily intricate full-frame abstract cut-paper relief, thousands of delicately cut and folded layers of heavyweight matte colored paper. Restrained deep teal, vermilion, warm ivory and mustard palette. Visible fibrous cut edges, fine scoring, folds, tiny layer offsets and beautiful physical shadow gaps. Raking warm light makes each paper layer tangible. Meticulous stop-motion paper-theater production craftsmanship. No plastic, no painted 3D surface, no illustration of paper; actual physical paper macro photography.')
}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--env',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    for line in args.env.read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('FAL_KEY='):os.environ['FAL_KEY']=line.split('=',1)[1].strip().strip('\"\'')
    def generate(item):
        sid,(title,direction)=item;record=out/(sid+'.json')
        if record.exists():return json.loads(record.read_text())
        prompt='Create an object-free art-direction reference image, not a scene or a poster. '+direction+' Composition fills the image edge to edge as abstract material and color. No identifiable objects, no architecture, no landscapes, no people, no faces, no plants, no animals, no characters, no lettering, no labels, no logos, no borders, no palette chips or swatch grid. Only exquisite abstract surface, light, medium and palette.'
        payload=dict(prompt=prompt,seed=secrets.randbelow(2_000_000_000),image_size='square_hd',num_images=1,acceleration='none',enable_prompt_expansion=False,enable_safety_checker=True,output_format='jpeg')
        req=out/(sid+'-request.json');start=time.perf_counter()
        if req.exists():
            saved=json.loads(req.read_text())
            if not saved.get('request_id'):raise RuntimeError('Uncertain prior Krea submission')
            result=fal_client.result('fal-ai/krea-2/turbo',saved['request_id'])
        else:
            saved=dict(model='fal-ai/krea-2/turbo',payload=payload);write_json(req,saved)
            handle=fal_client.submit('fal-ai/krea-2/turbo',arguments=payload)
            saved['request_id']=handle.request_id;write_json(req,saved);result=handle.get()
        url=result['images'][0]['url'];image=out/(sid+'.jpg')
        with urllib.request.urlopen(url,timeout=120) as r:image.write_bytes(r.read())
        row=dict(id=sid,title=title,path=str(image),url=url,seconds=time.perf_counter()-start,request_id=saved['request_id'],seed=result.get('seed'),timings=result.get('timings'))
        write_json(record,row);print(json.dumps(row),flush=True);return row
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(generate,STYLES.items()))
    write_json(out/'manifest.json',dict(model='fal-ai/krea-2/turbo',styles=rows))

if __name__=='__main__':main()
