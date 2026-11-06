"""Remove the Gemini/Veo sparkle watermark and export a high-quality video (Full HD by default).

usage:
  python clean.py input.mp4 output.mp4                 # watermark off + Lanczos upscale to 1920x1080
  python clean.py in.mp4 out.mp4 --ai                  # AI upscale with Real-ESRGAN (slower, sharper)
  python clean.py in.mp4 out.mp4 --size 3840x2160 --sharpen 0
  python clean.py in.mp4 out.mp4 --no-watermark        # only upscale (any resolution)

Steps:
 1. Reverse alpha blending with the calibrated mask (gemini_star_alpha_720p.npy):
    real = (pixel - a*255) / (1 - a); then a ~2px band along the star outline is softened,
    because the source's H.264 ringing at the sharp edge leaves a faint dotted outline.
 2. Upscale: Lanczos (default) or Real-ESRGAN (--ai), then optional unsharp (--sharpen).
 3. x264 CRF 16 / preset slow / tune film, BT.709 tagged, faststart; audio copied.
Frames are streamed in chunks, so long videos don't need much RAM.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from _common import FFMPEG, FFPROBE, HERE

MASK = HERE / "gemini_star_alpha_720p.npy"
OX, OY = 1104, 544          # top-left of the 112x112 mask in a 1280x720 frame
MASK_FRAME = (1280, 720)
REALESRGAN = HERE / "bin" / "realesrgan" / ("realesrgan-ncnn-vulkan" + (".exe" if sys.platform == "win32" else ""))
AI_MODELS = {"realesrgan-x4plus": (4,), "realesr-animevideov3": (2, 3, 4)}
CHUNK = 48                  # frames per processing chunk


def probe(src):
    line = subprocess.check_output(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(src)], text=True).split()[0]
    w, h, fps = line.split(",")[:3]
    return int(w), int(h), fps


def box_blur(img, k=3):
    """k x k box blur over the two spatial axes of an (N, H, W, C) array."""
    p = k // 2
    q = np.pad(img, ((0, 0), (p, p), (p, p), (0, 0)), mode="edge")
    c = np.pad(q.cumsum(1).cumsum(2), ((0, 0), (1, 0), (1, 0), (0, 0)))
    return (c[:, k:, k:] - c[:, :-k, k:] - c[:, k:, :-k] + c[:, :-k, :-k]) / (k * k)


class Watermark:
    def __init__(self, mask=MASK):
        a = np.load(mask).astype(np.float32)
        self.S = a.shape[0]
        self.a = a[None, :, :, None]
        inside = (a > 0.15).astype(np.float32)[None, :, :, None]
        edge = np.clip(np.abs(inside - box_blur(inside)) * 4, 0, 1)   # ~1px each side of the outline
        self.edge = np.clip(box_blur(edge) * 1.5, 0, 1)                # widen + feather to ~2px

    def __call__(self, frames):
        """frames: (N, 720, 1280, 3) uint8, fixed in place."""
        S = self.S
        r = frames[:, OY:OY + S, OX:OX + S].astype(np.float32)
        fixed = (r - self.a * 255.0) / (1 - self.a)
        fixed = fixed * (1 - self.edge) + box_blur(fixed) * self.edge
        frames[:, OY:OY + S, OX:OX + S] = np.clip(fixed, 0, 255).round().astype(np.uint8)
        return frames


def read_chunks(src, w, h, n=CHUNK):
    p = subprocess.Popen([FFMPEG, "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = p.stdout.read(size * n)
        k = len(buf) // size
        if k == 0:
            break
        yield np.frombuffer(buf[:k * size], np.uint8).reshape(k, h, w, 3).copy()
    if p.wait():
        raise RuntimeError(f"decoding {src} failed")


class AIUpscaler:
    """Runs realesrgan-ncnn-vulkan on a chunk of frames through a temp folder of PNGs."""

    def __init__(self, model, scale, tmp):
        if not REALESRGAN.exists():
            raise SystemExit(f"Real-ESRGAN not found at {REALESRGAN}. Run: python setup_realesrgan.py")
        self.model, self.scale = model, scale
        self.inp, self.out = Path(tmp) / "in", Path(tmp) / "out"

    def __call__(self, frames):
        from PIL import Image
        for d in (self.inp, self.out):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
        for i, f in enumerate(frames):
            Image.fromarray(f).save(self.inp / f"{i:05d}.png", compress_level=1)
        r = subprocess.run([str(REALESRGAN), "-i", str(self.inp), "-o", str(self.out), "-n", self.model,
                            "-s", str(self.scale), "-f", "png"], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("Real-ESRGAN failed:\n" + r.stderr[-2000:])
        return np.stack([np.asarray(Image.open(self.out / f"{i:05d}.png").convert("RGB"))
                         for i in range(len(frames))])


def clean(src, dst, size="1920x1080", sharpen=None, watermark=True, ai=False,
          ai_model="realesr-animevideov3", crf=16, log=print):
    src, dst = Path(src), Path(dst)
    w, h, fps = probe(src)
    if watermark and (w, h) != MASK_FRAME:
        raise SystemExit(f"{src.name}: the watermark mask is calibrated for 1280x720, this video is {w}x{h}. "
                         "Use --no-watermark to only upscale, or calibrate a new mask (see README).")
    if sharpen is None:
        sharpen = 0.3 if ai else 0.8
    ow, oh = (int(v) for v in size.lower().split("x"))

    steps = [Watermark()] if watermark else []
    in_w, in_h = w, h
    tmp = None
    if ai:
        scales = AI_MODELS[ai_model]
        scale = next((s for s in scales if w * s >= ow and h * s >= oh), scales[-1])
        tmp = tempfile.mkdtemp(prefix="clean-ai-")
        steps.append(AIUpscaler(ai_model, scale, tmp))
        in_w, in_h = w * scale, h * scale

    vf = f"scale={ow}:{oh}:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709"
    if sharpen > 0:
        vf += f",unsharp=5:5:{sharpen}:5:5:0"
    vf += ",format=yuv420p"
    enc = subprocess.Popen(
        [FFMPEG, "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{in_w}x{in_h}", "-r", fps, "-i", "-",
         "-i", str(src), "-map", "0:v", "-map", "1:a?", "-vf", vf,
         "-c:v", "libx264", "-crf", str(crf), "-preset", "slow", "-tune", "film", "-profile:v", "high",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(dst)],
        stdin=subprocess.PIPE)
    done = 0
    try:
        for frames in read_chunks(src, w, h):
            for step in steps:
                frames = step(frames)
            enc.stdin.write(np.ascontiguousarray(frames).tobytes())
            done += len(frames)
            if ai:
                log(f"  {done} frames", end="\r", flush=True)
    finally:
        enc.stdin.close()
        rc = enc.wait()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    if rc:
        raise RuntimeError(f"encoding {dst.name} failed (exit {rc})")
    return done


def add_args(ap):
    ap.add_argument("--size", default="1920x1080", help="output size, e.g. 1920x1080 or 3840x2160")
    ap.add_argument("--sharpen", type=float, help="unsharp amount, 0 = off .. 1.2 strong "
                                                  "(default 0.8, or 0.3 with --ai)")
    ap.add_argument("--no-watermark", dest="watermark", action="store_false",
                    help="skip watermark removal (only upscale)")
    ap.add_argument("--ai", action="store_true", help="upscale with Real-ESRGAN instead of Lanczos")
    ap.add_argument("--ai-model", default="realesr-animevideov3", choices=sorted(AI_MODELS),
                    help="realesr-animevideov3 (default, ~2.5 s/frame on an Intel iGPU) or realesrgan-x4plus "
                         "(general photo model, ~50x slower on an iGPU; use with a real GPU)")
    ap.add_argument("--crf", type=int, default=16, help="x264 quality, lower = better/bigger (default 16)")


def opts(a):
    return dict(size=a.size, sharpen=a.sharpen, watermark=a.watermark, ai=a.ai, ai_model=a.ai_model, crf=a.crf)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    add_args(ap)
    a = ap.parse_args()
    n = clean(a.src, a.dst, **opts(a))
    print(f"{n} frames -> {a.dst}")
