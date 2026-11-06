"""Finish the current job: move final video(s) from InProgress/ to Done/, then empty InProgress/.

InProgress/{name}-output.mp4 -> Done/{name}.mp4 (never overwrites: adds _2, _3 ...).
Everything else in InProgress/ is deleted, including the sources (originals stay in inqueue/).

usage: python done.py [--dry-run] [--workspace DIR]
"""
import argparse
import shutil
import sys

from _common import workspace

SUFFIX = "-output.mp4"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="only show what would happen")
    ap.add_argument("--workspace")
    a = ap.parse_args()
    ws = workspace(a.workspace)
    inp, done = ws / "InProgress", ws / "Done"

    finals = sorted(inp.glob("*" + SUFFIX)) if inp.exists() else []
    if not finals:
        sys.exit(f"No *{SUFFIX} in {inp} - nothing finished yet. InProgress left untouched.")

    done.mkdir(exist_ok=True)
    for f in finals:
        base = f.name.removesuffix(SUFFIX)
        target, n = done / f"{base}.mp4", 2
        while target.exists():
            target, n = done / f"{base}_{n}.mp4", n + 1
        print(f"move   {f.relative_to(ws)} -> {target.relative_to(ws)}")
        if not a.dry_run:
            shutil.move(str(f), str(target))

    for p in sorted(inp.iterdir()):
        if a.dry_run and p.name.endswith(SUFFIX):
            continue
        print(f"delete {p.relative_to(ws)}")
        if not a.dry_run:
            shutil.rmtree(p) if p.is_dir() else p.unlink()

    print("dry run - nothing changed" if a.dry_run else "done: InProgress/ is empty")


if __name__ == "__main__":
    main()
