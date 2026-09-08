"""Record the actual Blender client window and schedule synchronized playback."""
import argparse,json,subprocess,time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--hwnd',required=True)
a=p.parse_args();out=a.output.resolve();video=out/'blender-45s-recording.mp4'
cmd=['ffmpeg','-y','-v','warning','-f','gdigrab','-framerate','30','-draw_mouse','0','-i','hwnd='+a.hwnd,
     '-t','52','-vf','crop=trunc(iw/2)*2:trunc(ih/2)*2','-an','-c:v','libx264','-preset','veryfast',
     '-tune','zerolatency','-crf','18','-g','30','-pix_fmt','yuv420p','-fps_mode','cfr','-r','30',
     '-movflags','+faststart','-progress','pipe:1','-nostats',str(video)]
with (out/'recording-error.log').open('w') as err:
    process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True)
    receipt=None
    for line in process.stdout:
        if receipt is None and line.startswith('out_time_us='):
            stamp=line.strip().split('=',1)[1]
            if not stamp.isdigit():continue
            seconds=int(stamp)/1_000_000
            if seconds<=0:continue
            now=time.time();start=now+3
            schedule=out/'playback-start.json';temp=schedule.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(epoch=start)));temp.replace(schedule)
            (out/'playback-hold.flag').unlink(missing_ok=True)
            receipt=dict(recording=str(video),capture_start_epoch_estimate=now-seconds,
                         playback_start_epoch=start,media_start=3+seconds,duration=45,
                         kind='Actual Blender client capture; normal-speed synchronized playback')
            (out/'recording.json').write_text(json.dumps(receipt,indent=2))
            print(json.dumps(receipt),flush=True)
    code=process.wait()
if code:raise SystemExit(code)
if receipt is None:raise RuntimeError('Recording never reported a captured frame')
print('RECORDING COMPLETE',flush=True)
