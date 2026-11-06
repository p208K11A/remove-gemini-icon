# clean-video: remove the Gemini watermark + upscale

[Tiếng Việt](README.vi.md)

Removes the sparkle watermark that Gemini / Veo puts in the bottom-right corner of 1280x720 videos,
then exports a high-quality Full HD (or 4K) file.

Companion repo: **make-video** builds finished videos (intro / promo) from the cleaned clips.

## Install

- **ffmpeg** on PATH (Windows: `winget install Gyan.FFmpeg`)
- **Python 3.10+**, then `pip install -r requirements.txt` (numpy, Pillow)
- Optional, for `--ai`: `python setup_realesrgan.py` (downloads Real-ESRGAN ncnn-vulkan into `bin/`, runs on any Vulkan GPU)

## One file

```bash
python clean.py input.mp4 output.mp4                    # Lanczos upscale to 1920x1080 (fast, ~1x realtime)
python clean.py input.mp4 output.mp4 --ai               # Real-ESRGAN AI upscale (sharper, much slower)
python clean.py input.mp4 output.mp4 --size 3840x2160 --sharpen 0
python clean.py input.mp4 output.mp4 --no-watermark     # only upscale, any resolution
```

| Option | Default | |
|---|---|---|
| `--size WxH` | `1920x1080` | output size |
| `--sharpen N` | `0.8` (`0.3` with `--ai`) | unsharp amount, `0` = off, `1.2` = strong |
| `--ai` | off | upscale with Real-ESRGAN (run `python setup_realesrgan.py` once) |
| `--ai-model` | `realesr-animevideov3` | or `realesrgan-x4plus` (better on photos, ~50x slower on an integrated GPU) |
| `--crf N` | `16` | x264 quality, lower = better and bigger |
| `--no-watermark` | | skip watermark removal |

Speed measured on an Intel UHD 770 iGPU: Lanczos ~8 s per 10 s clip; `--ai` with animevideov3 ~2.5 s per frame
(~10 min per 10 s clip). Quality ceiling: Gemini renders 720p at ~2 Mbps, so upscaling cleans and sharpens
but can't invent real detail.

## Workflow for many files

The workspace (default: this folder, or `--workspace DIR`, or env `VIDKIT_WORKSPACE`) has three folders,
created on demand and git-ignored:

```
inqueue/      drop new videos here (originals are never touched)
InProgress/   working copies + results ({name}-output.mp4)
Done/         finished videos
```

```bash
python process.py --pull          # copy inqueue/* -> InProgress/, process every source
python process.py clip1 --ai      # re-process one clip with other options (overwrites its output)
python done.py --dry-run          # show the plan
python done.py                    # InProgress/{name}-output.mp4 -> Done/{name}.mp4, empty InProgress/
```

Any video in `InProgress/` whose name does not end in `-output` is a source (a trailing `-current` is
optional and dropped). `done.py` never overwrites: it adds `_2`, `_3`... Windows: double-click
`process.bat` / `done.bat` (done asks y/N).

## How the watermark removal works

Gemini blends a white star onto the frame: `shown = a*255 + (1-a)*real`. With a calibrated alpha mask
(`gemini_star_alpha_720p.npy`, 112x112 at x=1104, y=544, peak alpha ~0.30) the real pixel is recovered exactly:
`real = (shown - a*255) / (1 - a)`. A ~2px band along the star outline is then softened, because the H.264
ringing at the sharp edge leaves a faint dotted outline. This beats blur/inpaint filters (ffmpeg `delogo`
leaves a visible smudge on textured backgrounds).

**Other resolutions** need a new mask. Collect clips where the star sits over flat, dark areas, then:

```bash
python calibrate_mask.py new_mask.npy clip1.mp4 clip2.mp4 ...
```

and adjust `OX, OY, MASK_FRAME` in `clean.py`. Always check zoomed crops of the corner on several shots.

## License

MIT. Real-ESRGAN (downloaded separately) is BSD-3-Clause. Make sure you have the rights to the videos you process.
