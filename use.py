"""Switch the active ruleset and rebuild the tables.

    python use.py                 # list presets and show the active one
    python use.py standard        # switch + rebuild
    python use.py clubhouse       # back to the default
    python use.py my-variant --no-build

A preset is just a file in presets/.  Copy one to config.json, edit it, and run
solve.py yourself if you want a custom variant.
"""
import shutil
import subprocess
import sys

import rules as R


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        active = None
        try:
            active = R.load().preset
        except SystemExit:
            pass
        print(f"active: {active or '(none)'}\n")
        print("presets:")
        for f in sorted(R.PRESETS.glob("*.json")):
            rs = R.load_preset(f.stem)
            mark = " *" if f.stem == active else "  "
            print(f" {mark} {f.stem:<12} {rs.title}  ({rs.n_cat} 栏)")
        print("\nusage: python use.py <preset>")
        return

    name = args[0]
    src = R.PRESETS / f"{name}.json"
    if not src.exists():
        avail = ", ".join(f.stem for f in sorted(R.PRESETS.glob("*.json")))
        raise SystemExit(f"没有预设 {name!r}；可用: {avail}")

    shutil.copyfile(src, R.CONFIG)
    rs = R.load()
    print(f"config.json <- presets/{name}.json")
    print(rs.describe())

    if "--no-build" not in sys.argv:
        print("\nrebuilding tables...")
        subprocess.run([sys.executable, str(R.BASE / "solve.py")], check=True)


if __name__ == "__main__":
    main()
