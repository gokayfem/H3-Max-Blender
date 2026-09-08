# H3 Max Blender

A neural rendering demo built with **GPT-6 Astra + H3 Max on fal**.

A simple gray ship grows into a detailed vessel in Blender, with **cartoon, claymation, realistic, and painted** video previews updating alongside it.

[![Watch the Blender demo](demo/cover.png)](https://github.com/gokayfem/H3-Max-Blender/raw/refs/heads/main/demo/blender-neural-renderer.mp4)

[Watch the video](https://github.com/gokayfem/H3-Max-Blender/raw/refs/heads/main/demo/blender-neural-renderer.mp4)

## Run it

Requires **Blender 5.1.2 on Windows**, Python, FFmpeg on PATH, and a fal API key.

Clone this repo, copy `.env.example` to `.env`, and fill in `FAL_KEY`.

Install dependencies into the source folder using Blender's Python (PowerShell):

```powershell
$blenderPython = "C:/Program Files/Blender Foundation/Blender 5.1/5.1/python/bin/python.exe"
& $blenderPython -m ensurepip
& $blenderPython -m pip install -r requirements.txt --target extension/vendor
python scripts/run_demo.py --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --output outputs/demo-01 --generate
```

The demo loads the code in `extension/` directly. No ZIP or separately installed add-on is needed.

This opens a fresh Blender scene and builds the ship automatically. A full run makes **32 paid generation requests**. Use a new output folder for each run.

Experimental: previews update asynchronously and generated details can vary. The recording skips the first wait and loops 1.8-second moving excerpts of five-second outputs.

Demo scripts by GPT-6 Astra; video generation by H3 Max. Extension source included, based on [fal-ai/fal-blender-extension](https://github.com/fal-ai/fal-blender-extension). GPL-3.0-or-later.

## Nine-style railway district

A dense hillside station district: **25,251 modeled parts**, **156,974 mesh faces**, neutral gray geometry, and nine simultaneous H3 Max styles in a 3x3 Blender grid.

```sh
python scripts/run_demo.py --scene railway --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --output outputs/railway-01 --generate --closeup
```

One batch makes **nine paid 480p requests**. Each pane shows API and request-to-visible time; full five-second clips play without trimming. Source geometry and measurements are saved in the output folder. Edit the scene and create `refresh.flag` in that folder to request another batch. H3 interprets a captured image, so mesh complexity is not equivalent to neural inference cost.

To reduce transitions in an unchanged scene, add `--anchors outputs/railway-01/nine-grid-status.json` and choose a new output folder. This extracts each finished style at four seconds and uses it as **both first and last frame** for H3 Max Turbo image-to-video. It preserves the existing render rather than interpreting new geometry; displayed timings cover this second stage only.

Add `--train-motion` with `--anchors` to let trains move along the rails while retaining the finished style. This uses the styled first frame only; the train is free to advance instead of returning to an identical last frame.


## Sixteen-style conservatory market

A dense gray conservatory market with 140 shoppers and vendors, 23,368 modeled parts and 619,262 mesh faces. One locked camera feeds sixteen concurrent H3 Max reference-to-video requests at 768p; the results play in a 4x4 grid beside the Blender geometry.

```powershell
python scripts/run_demo.py --scene market --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --output outputs/market-01 --generate
```

Styles: photoreal, claymation, bold cartoon, watercolor, neon noir, porcelain, carved walnut, paper theater, needle felt, brick toys, voxel world, oil painting, stained glass, black and white, anime film, and copper engraving. People make small gestures while the architecture and camera remain fixed. One batch makes 16 paid requests. Generated movement and geometry consistency can vary.

The output contains `conservatory-market.blend`, `geometry.png`, `geometry-stats.json`, individual MP4s and request metadata, plus `sixteen-grid-status.json` and a Blender screenshot. Create `refresh.flag` in the output directory to generate another batch. The script loads extension source directly; no add-on ZIP is required.

## Three scenes in one H3 request

Three gray observatories—underwater, desert and rainforest—become a simultaneous triptych, a three-shot film, or one impossible building. Each variant sends **three JPEG references in one request**, using H3 Max's 768P setting. The wide outputs may have a shorter height than 768 pixels.

```powershell
& "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python scripts/three_worlds_scene.py -- --output outputs/three-worlds
python -m pip install fal-client Pillow
python scripts/three_worlds_experiment.py --output outputs/three-worlds --env .env --generate
& "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --factory-startup --python scripts/three_worlds_viewer.py -- --output outputs/three-worlds
```

The experiment makes **three paid requests total** and saves their IDs for resuming. The viewer only plays existing files; its three header buttons switch experiments. All three editable scenes are in `three-observatories.blend`, with videos, timings and a local `index.html` beside it. Keep the output folder with the Blender file.

This explores generative scene composition, not exact physical rendering: cameras and details can be reinterpreted. Timings distinguish GPU inference, API wait, download and source preparation. No Cycles speed comparison is implied.

## Four strong styles, three worlds

`krea_world_styles.py` creates object-free Krea 2 Turbo references. `strong_style_films.py` resolves each scene in photoreal, claymation, colorful cartoon and paper, then generates four 15-second films. Detailed medium, palette, character and lighting descriptions are included in every prompt. Look development and final generation timings are recorded separately.

After installing the Python requirements and FFmpeg, prepare the scenes and styles (4 paid Krea requests and 12 paid H3 look-development requests):

```powershell
& "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python scripts/three_worlds_scene.py -- --output outputs/three-worlds
python scripts/three_worlds_experiment.py --output outputs/three-worlds --env .env --upload-only
python scripts/krea_world_styles.py --output outputs/styles --env .env
python scripts/strong_style_films.py --stage prepare --source outputs/three-worlds --styles outputs/styles/manifest.json --output outputs/four-films-strong-v3 --env .env
python scripts/strong_style_films.py --stage anchors --source outputs/three-worlds --styles outputs/styles/manifest.json --output outputs/four-films-strong-v3 --env .env
```

To make **four 45-second films** from a completed strong-style output:

```powershell
python scripts/forty_five_style_films.py --source outputs/four-films-strong-v3 --output outputs/four-films-45s --env .env
```

This makes 12 new native 768p requests: three continuous 15-second shots per style. FFmpeg joins them at normal speed with hard cuts. Reviewed single-scene image anchors avoid accidentally sampling a transition from a multi-scene film. The output includes four MP4s, a synchronized gallery, prompts, request IDs and a review contact sheet. Use the same output directory to resume existing requests without resubmitting them.

Show the four films together inside the actual Blender UI:

```powershell
& "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --factory-startup --python scripts/four_films_viewer.py -- --output outputs/four-films-45s
```

`record_four_films.py --output <same-folder> --hwnd <Blender-window-handle>` records that Blender client window and synchronizes playback. Its timing receipt identifies the 45-second source range; local paths in the Windows title bar are excluded from capture.

For fresh seeds with H3 Max's 1080P setting, reuse the approved prompts and references in a new folder:

```powershell
python scripts/forty_five_style_films.py --source outputs/four-films-strong-v3 --recipe outputs/four-films-45s --resolution 1080P --output outputs/four-films-1080p --env .env
```

This submits 12 new requests. H3 Max documents 1080P as latent refinement from its native 768P source; the supplied files are 1920×1080 for this 16:9 setup.

Export the recorded Blender UI with optional instrumental music using Node.js and HyperFrames:

```powershell
python scripts/build_release.py --source outputs/four-films-1080p --output outputs/release --height 1080 --music path/to/instrumental.mp3
$env:NODE_OPTIONS='--max-old-space-size=12288'
npx --yes hyperframes@0.8.31 render outputs/release --quality high --workers 4 --video-frame-format png --output outputs/release.mp4
```
