"""Process every source video in InProgress/ -> InProgress/{name}-output.mp4

Source = any video in InProgress/ whose name does NOT end with "-output"
(a trailing "-current" is optional and is dropped from the output name).
Re-running overwrites the outputs, so you can keep adjusting until you're happy, then run done.py.

usage:
  python process.py                      # all sources in InProgress/
  python process.py --pull               # first copy inqueue/* into InProgress/ (originals stay)
  python process.py clip1 clip2          # only these names
  python process.py --ai --sharpen 0.5   # any option of clean.py
  python process.py --workspace D:/other/project
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

from _common import VIDEO_EXT, workspace
from clean import add_args, clean, opts


def base_name(p: Path) -> str:
    return p.stem.removesuffix("-current")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="only these videos (with or without extension / -current)")
    ap.add_argument("--pull", action="store_true", help="copy inqueue/* into InProgress/ first")
    ap.add_argument("--workspace", help="folder holding inqueue/ InProgress/ Done/ (default: repo root)")
    add_args(ap)
    a = ap.parse_args()
    ws = workspace(a.workspace)
    inp = ws / "InProgress"
    inp.mkdir(parents=True, exist_ok=True)

    if a.pull:
        for f in sorted((ws / "inqueue").glob("*")):
            if f.is_file() and f.suffix.lower() in VIDEO_EXT and not (inp / f.name).exists():
                print(f"copy   inqueue/{f.name} -> InProgress/")
                shutil.copy2(f, inp / f.name)

    sources = sorted(p for p in inp.iterdir()
                     if p.is_file() and p.suffix.lower() in VIDEO_EXT and not p.stem.endswith("-output"))
    if a.names:
        wanted = {base_name(Path(n)) if Path(n).suffix.lower() in VIDEO_EXT else n.removesuffix("-current")
                  for n in a.names}
        sources = [s for s in sources if base_name(s) in wanted]
    if not sources:
        sys.exit(f"No source videos in {inp} (files ending in -output are results, not sources).")

    failed = []
    for src in sources:
        dst = inp / f"{base_name(src)}-output.mp4"
        print(f"[{src.name}] -> {dst.name} ...", flush=True)
        t = time.time()
        try:
            n = clean(src, dst, **opts(a))
            print(f"  ok, {n} frames in {time.time() - t:.0f}s" + " " * 10)
        except (Exception, SystemExit) as e:
            failed.append(src.name)
            print(f"  FAILED: {e}")

    print(f"\n{len(sources) - len(failed)}/{len(sources)} done." + (f" Failed: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
