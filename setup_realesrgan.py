"""Download Real-ESRGAN (ncnn-vulkan, portable, any Vulkan GPU incl. Intel iGPU) into clean-video/bin/realesrgan/.

usage: python setup_realesrgan.py [--dest DIR]

Source: https://github.com/xinntao/Real-ESRGAN (BSD-3-Clause). Not committed to git.
"""
import argparse
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from _common import HERE

BASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-"
ZIP = {"win32": "windows.zip", "darwin": "macos.zip"}.get(sys.platform, "ubuntu.zip")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(HERE / "bin" / "realesrgan"))
    dest = Path(ap.parse_args().dest)
    exe = "realesrgan-ncnn-vulkan" + (".exe" if sys.platform == "win32" else "")
    if (dest / exe).exists():
        print(f"already installed: {dest / exe}")
        return
    url = BASE + ZIP
    print(f"downloading {url} ...")
    data = urllib.request.urlopen(url, timeout=120).read()
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
    found = next(tmp.rglob(exe))
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(found.parent), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    if sys.platform != "win32":
        (dest / exe).chmod(0o755)
    print(f"installed: {dest / exe}")


if __name__ == "__main__":
    main()
