"""Re-estimate the Gemini star alpha mask from frames where the background behind it is flat.

usage: python calibrate_mask.py out_mask.npy video1.mp4 [video2.mp4 ...]

For every frame, fit a smooth surface to the ring of pixels around the star (outside the star box).
Frames whose ring is flat (low residual) are used: alpha = (I - B) / (255 - B).
The per-pixel median over all usable frames, symmetrised (the star is symmetric), is saved.
Use clips with dark, flat areas behind the star (sky, walls, dark screens). RMS_MAX env = flatness limit.
"""
import os
import subprocess
import sys

import numpy as np

from _common import FFMPEG
from clean import OX, OY

S = 112
STAR = (26, 86)  # star lives in rows/cols [26, 86) of the 112x112 crop
RMS_MAX = float(os.environ.get("RMS_MAX", "2.5"))

if len(sys.argv) < 3:
    sys.exit(__doc__)
out, videos = sys.argv[1], sys.argv[2:]
yy, xx = np.mgrid[0:S, 0:S]


def box(lo, hi):
    return (yy >= lo) & (yy < hi) & (xx >= lo) & (xx < hi)


inner = box(STAR[0] - 2, STAR[1] + 2)
ring = box(STAR[0] - 8, STAR[1] + 8) & ~inner


def design(x, y):
    x, y = (x - 55.5) / 30, (y - 55.5) / 30
    return np.c_[np.ones(x.size), x, y, x * x, y * y, x * y]


A = design(xx[ring], yy[ring])
Afull = design(xx.ravel(), yy.ravel())

alphas = []
for v in videos:
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", v, "-vf", f"crop={S}:{S}:{OX}:{OY}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, S, S, 3).astype(np.float32)
    used = 0
    for f in fr:
        ok = True
        al = np.zeros((S, S, 3), np.float32)
        for c in range(3):
            coef, res, *_ = np.linalg.lstsq(A, f[..., c][ring], rcond=None)
            rms = np.sqrt(res[0] / ring.sum()) if res.size else 99
            B = (Afull @ coef).reshape(S, S)
            if rms > RMS_MAX or B.max() > 200:  # textured ring or too bright to measure well
                ok = False
                break
            al[..., c] = (f[..., c] - B) / (255.0 - B)
        if ok:
            alphas.append(al.mean(2))
            used += 1
    print(f"{os.path.basename(v)}: {used}/{len(fr)} flat frames")

if len(alphas) < 10:
    sys.exit(f"only {len(alphas)} usable frames - not enough to calibrate")
a = np.median(np.stack(alphas), axis=0)
a = (a + a[::-1] + a[:, ::-1] + a[::-1, ::-1]) / 4
a[~inner] = 0
a = np.clip(a, 0, 0.95)
a[a < 0.01] = 0
print(f"{len(alphas)} frames, interior alpha {a[50:62, 50:62].mean():.3f}, max {a.max():.3f}")
np.save(out, a.astype(np.float32))
