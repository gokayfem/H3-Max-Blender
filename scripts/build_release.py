"""Build a HyperFrames project from a recorded Blender showcase."""
import argparse
import html
import json
from pathlib import Path
import shutil


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Folder produced by record_four_films.py')
    parser.add_argument('--output',type=Path,required=True,help='HyperFrames project folder')
    parser.add_argument('--music',type=Path,help='Optional instrumental audio file')
    parser.add_argument('--height',type=int,choices=[720,1080],default=1080)
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    assets=out/'assets';assets.mkdir(parents=True,exist_ok=True)
    receipt=json.loads((source/'recording.json').read_text(encoding='utf-8'))
    shutil.copy2(source/'blender-45s-recording.mp4',assets/'recording.mp4')
    width=args.height*16//9;audio=''
    if args.music:
        filename='music'+args.music.suffix
        shutil.copy2(args.music,assets/filename)
        audio=f'<audio id="score" src="assets/{html.escape(filename,quote=True)}" data-start="0" data-duration="45" data-track-index="2" data-volume="0.72"></audio>'
    markup=f'''<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>*{{margin:0;padding:0;box-sizing:border-box}}html,body,#root{{width:{width}px;height:{args.height}px;overflow:hidden;background:#191919}}#root{{position:relative}}video{{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}}</style></head><body>
<div id="root" data-composition-id="blender-release" data-width="{width}" data-height="{args.height}" data-duration="45" data-start="0">
<video id="recording" class="clip" src="assets/recording.mp4" data-start="0" data-duration="45" data-media-start="{float(receipt['media_start'])}" data-track-index="1" muted playsinline></video>{audio}
</div><script>window.__timelines=window.__timelines||{{}};window.__timelines['blender-release']=gsap.timeline({{paused:true}});</script></body></html>'''
    (out/'index.html').write_text(markup,encoding='utf-8')
    (out/'source.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('HyperFrames project ready: '+str(out))


if __name__=='__main__':main()
