import runpy
import sys
import tempfile
import traceback
from pathlib import Path

from .transpiler import transpile


ACCEPTED_FILENAMES = (".nk", ".nk.java", ".java")


def _looks_like_source(name: str) -> bool:
    return any(name.endswith(ext) for ext in ACCEPTED_FILENAMES)


def _resolve_main_in_dir(d: Path) -> Path | None:
    # Search recursively for a Main.* entrypoint in stable order
    patterns = ("Main.nk", "Main.nk.java", "Main.java")
    candidates: list[Path] = []
    for pat in patterns:
        for p in d.rglob(pat):
            if p.is_file():
                candidates.append(p)
        if candidates:
            # Sort by relative path for determinism and pick first
            candidates.sort(key=lambda p: str(p.relative_to(d)))
            return candidates[0]
    return None


def _gather_sources(entry: Path) -> str:
    base_dir = entry if entry.is_dir() else entry.parent
    if entry.is_dir():
        main_file = _resolve_main_in_dir(base_dir)
        if main_file is None:
            raise FileNotFoundError("No Main.nk/Main.nk.java/Main.java found under directory")
    else:
        main_file = entry

    # Gather all accepted sources recursively under base_dir
    files = [
        p
        for p in base_dir.rglob("*")
        if p.is_file() and _looks_like_source(p.name)
    ]
    # Sort deterministically by relative path
    files.sort(key=lambda p: str(p.relative_to(base_dir)))

    parts = []
    for p in files:
        rel = str(p.relative_to(base_dir))
        parts.append(f"/* NEOAK_FILE: {rel} */\n" + p.read_text(encoding="utf-8"))
    # Ensure main file content present (should be by above, but keep safety)
    main_src = main_file.read_text(encoding="utf-8")
    if not any(s == main_src for s in parts):
        parts.insert(0, main_src)
    return "\n\n".join(parts)


def run_file(path: str, emit: bool = False) -> int:
    src_path = Path(path)
    if not src_path.exists():
        print(f"NeOak error: file not found: {path}")
        return 2

    try:
        source = _gather_sources(src_path)
    except Exception as e:
        print(f"NeOak error: {e}")
        return 2

    try:
        py_code = transpile(source)
    except Exception as e:
        print(f"NeOak transpile error: {e}")
        return 3

    if emit:
        sys.stdout.write(py_code)
        return 0

    # Execute the generated Python in an isolated module namespace
    # Write to a temp file so tracebacks have a filename
    with tempfile.TemporaryDirectory() as td:
        temp_py = Path(td) / "__neoak_main__.py"
        temp_py.write_text(py_code, encoding="utf-8")
        try:
            runpy.run_path(str(temp_py), run_name='__main__')
            return 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            return code
        except Exception as e:
            # Pretty-print a NeOak-aware traceback using mapping comments
            try:
                tb = e.__traceback__
                neoak_frames = []
                while tb is not None:
                    f = tb.tb_frame
                    if f.f_code.co_filename == str(temp_py):
                        neoak_frames.append((tb.tb_lineno, f.f_code.co_name))
                    tb = tb.tb_next
                src_lines = temp_py.read_text(encoding="utf-8").splitlines()
                def find_src_marker(py_line_no: int) -> str | None:
                    # Search backwards from the failing Python line for a mapping marker
                    i = min(max(py_line_no - 1, 0), len(src_lines) - 1)
                    while i >= 0:
                        ln = src_lines[i].strip()
                        if ln.startswith('# NEOAK_SRC:'):
                            return ln[len('# NEOAK_SRC:'):].strip()
                        i -= 1
                    return None
                print("NeOak runtime error:")
                for ln, fn in neoak_frames:
                    marker = find_src_marker(ln)
                    if marker:
                        print(f"  at {marker} (in {fn})")
                    else:
                        print(f"  at generated:{ln} (in {fn})")
                print(f"  cause: {e}")
            except Exception:
                # Fallback
                print(f"NeOak runtime error: {e}")
            return 4
