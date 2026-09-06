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
python scripts/run_demo.py --scene railway --blender "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --output outputs/railway-01 --generate
```

One batch makes **nine paid 480p requests**. Each pane shows API and request-to-visible time; full five-second clips play without trimming. Source geometry and measurements are saved in the output folder. Edit the scene and create `refresh.flag` in that folder to request another batch. H3 interprets a captured image, so mesh complexity is not equivalent to neural inference cost.
