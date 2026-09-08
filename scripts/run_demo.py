"""Launch the scripted build in a new Blender process."""
import argparse
import shutil
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--train-motion', action='store_true', help='Animate the existing trains in the anchored railway scene')
    parser.add_argument('--anchors', type=Path, help='Prior railway status JSON for style-anchored regeneration')
    parser.add_argument('--closeup', action='store_true', help='Tight station framing for the railway scene')
    parser.add_argument('--scene', choices=['ship', 'railway', 'market'], default='ship')
    parser.add_argument('--env', type=Path, default=Path('.env'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--generate', action='store_true', help='Enable paid generation: ship 32 requests, railway 9 requests, market 16 requests')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.generate and not args.dry_run:
        parser.error('Pass --generate to run paid generation, or --dry-run to inspect the command.')
    executable = shutil.which(args.blender)
    if not executable:
        parser.error('Blender executable not found; pass --blender with its full path.')
    output = args.output.resolve()
    script = Path(__file__).with_name({'ship':'fresh_moving_build.py','railway':'railway_demo.py','market':'market_demo.py'}[args.scene])
    command = [executable, '--factory-startup', '--online-mode', '--python', str(script), '--',
               '--env', str(args.env.resolve()), '--output', str(output)]
    command += ['--generate'] if args.scene in ['railway','market'] else ['--grid', '--start-stage', '5']
    if args.scene == 'market': command += ['--resolution', '768P']
    if args.closeup and args.scene == 'railway': command.append('--closeup')
    if args.anchors and args.scene == 'railway': command += ['--anchors', str(args.anchors.resolve())]
    if args.train_motion and args.scene == 'railway': command.append('--train-motion')
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return
    if not args.env.is_file():
        parser.error('Create the specified env file from .env.example first.')
    if not shutil.which('ffmpeg'):
        parser.error('FFmpeg is required on PATH for moving preview excerpts.')
    if output.exists() and any(output.iterdir()):
        parser.error('Use a new, empty output directory for each build.')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'blender.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(180):
        if process.poll() is not None:
            raise SystemExit('Blender exited before setup; inspect the output log.')
        if (output / 'ready.flag').exists():
            (output / 'start-build.flag').write_text('start', encoding='utf-8')
            print(f'Build started in Blender. Outputs: {output}')
            return
        time.sleep(.5)
    raise SystemExit('Setup timed out; inspect Blender before creating start-build.flag manually.')


if __name__ == '__main__':
    main()
