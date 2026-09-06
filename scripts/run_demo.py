"""Launch the scripted build in a new Blender process."""
import argparse
import shutil
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--env', type=Path, default=Path('.env'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--generate', action='store_true', help='Enable the 32 paid model requests')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.generate and not args.dry_run:
        parser.error('Pass --generate to run paid generation, or --dry-run to inspect the command.')
    executable = shutil.which(args.blender)
    if not executable:
        parser.error('Blender executable not found; pass --blender with its full path.')
    output = args.output.resolve()
    script = Path(__file__).with_name('fresh_moving_build.py')
    command = [executable, '--factory-startup', '--online-mode', '--python', str(script), '--',
               '--env', str(args.env.resolve()), '--output', str(output), '--grid', '--start-stage', '5']
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
