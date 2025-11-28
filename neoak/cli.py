import argparse
from pathlib import Path

from .runner import run_file
from .docsgen import generate_docs


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
    sub = parser.add_subparsers(dest='cmd')

    p_run = sub.add_parser('run', help='Run a NeOak project (default)')
    p_run.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to NeOak source or directory (default: scan for Main.nk or Main.nk.java)",
    )
    p_run.add_argument(
        "--emit", action="store_true", help="Emit transpiled Python instead of running"
    )

    p_docs = sub.add_parser('docs', help='Generate HTML docs (JavaDoc-style)')
    p_docs.add_argument('path', nargs='?', default='.', help='Path to source dir or file')
    p_docs.add_argument('--out', default='docs', help='Output directory (default: docs)')

    args = parser.parse_args(argv)

    if args.cmd == 'docs':
        generate_docs(args.path, args.out)
        print(f"Docs generated in {args.out}")
        return 0

    # default to run
    path = getattr(args, 'path', None)
    emit = getattr(args, 'emit', False)
    src = _resolve_default_path(path)
    return run_file(src, emit=emit)


if __name__ == "__main__":
    raise SystemExit(main())
