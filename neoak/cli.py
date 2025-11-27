import argparse
from pathlib import Path

from .runner import run_file


def _resolve_default_path(p: str | None) -> str:
    if p:
        given = Path(p)
        if given.is_dir():
            # Search inside given dir for Main.*; if not found, return the directory
            for cand in (given / "Main.nk", given / "Main.nk.java", given / "Main.java"):
                if cand.exists():
                    return str(cand)
            return str(given)
        # Use provided path as-is
        return str(given)

    # No path provided: search CWD
    cwd = Path.cwd()
    for name in ("Main.nk", "Main.nk.java", "Main.java"):
        cand = cwd / name
        if cand.exists():
            return str(cand)
    # Default to directory for recursive search
    return str(cwd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="neoak", description="NeOak language runner")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to NeOak source or directory (default: scan for Main.nk or Main.nk.java)",
    )
    parser.add_argument(
        "--emit", action="store_true", help="Emit transpiled Python instead of running"
    )
    args = parser.parse_args(argv)

    src = _resolve_default_path(args.path)
    return run_file(src, emit=args.emit)


if __name__ == "__main__":
    raise SystemExit(main())
