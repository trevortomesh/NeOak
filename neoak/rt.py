import threading
import copy
import sys
import re
import os
import time
try:
    import tkinter as _tk
except Exception:  # GUI may be unavailable; guard imports
    _tk = None


class Class:
    def __init__(self, py_cls: type):
        self._cls = py_cls

    def getName(self) -> str:
        return self._cls.__name__

    def __str__(self) -> str:
        return self.getName()


class Object:
    __slots__ = ("__cond",)

    def __init__(self):
        # Lazily created condition to support wait/notify
        self.__cond = None

    # Java Object API
    def getClass(self) -> Class:
        return Class(self.__class__)

    def hashCode(self) -> int:
        # Default identity-based hash code
        return hash(self)

    def equals(self, other) -> bool:
        # Default identity equality
        return self is other

    def toString(self) -> str:
        # Default: ClassName@<lower-hex-identity>
        return f"{self.__class__.__name__}@{id(self) & 0xFFFFFFFF:x}"

    # Python dunder bridging
    def __str__(self) -> str:
        return self.toString()

    def __repr__(self) -> str:
        return self.toString()

    def __eq__(self, other) -> bool:
        return self.equals(other)

    def __hash__(self) -> int:
        return self.hashCode()

    # Concurrency helpers (best-effort; no Java monitors)
    def _ensure_cond(self):
        if self.__cond is None:
            self.__cond = threading.Condition()
        return self.__cond

    def wait(self, timeout: float | None = None):
        # Best-effort wait; not tied to synchronized blocks
        cond = self._ensure_cond()
        with cond:
            cond.wait(timeout=timeout)

    def notify(self):
        cond = self._ensure_cond()
        with cond:
            cond.notify()

    def notifyAll(self):  # noqa: N802 (Java-compatible name)
        cond = self._ensure_cond()
        with cond:
            cond.notify_all()

    def clone(self):
        # Shallow copy by default
        return copy.copy(self)

    def finalize(self):  # Deprecated in Java; no-op here
        pass


class Scanner(Object):
    def __init__(self, source=None):
        super().__init__()
        if source is None:
            self._stream = sys.stdin
            self._close = False
        elif isinstance(source, str):
            self._stream = open(source, 'r', encoding='utf-8')
            self._close = True
        elif hasattr(source, 'read'):
            self._stream = source
            self._close = False
        else:
            # Fallback: treat as string
            self._stream = open(str(source), 'r', encoding='utf-8')
            self._close = True

        self._delim = re.compile(r"\s+")
        self._buffer: list[str] = []
        self._eof = False

    def useDelimiter(self, pattern: str):
        self._delim = re.compile(pattern)
        return self

    def _fill(self):
        while not self._buffer and not self._eof:
            line = self._stream.readline()
            if line == '':
                self._eof = True
                break
            # Strip newline; split by delimiter, filter empties
            parts = [p for p in self._delim.split(line.strip()) if p != '']
            self._buffer.extend(parts)

    def hasNext(self) -> bool:
        self._fill()
        return bool(self._buffer)

    def next(self) -> str:
        self._fill()
        if not self._buffer:
            raise LookupError('NoSuchElementException')
        return self._buffer.pop(0)

    def nextLine(self) -> str:
        # Return the next raw line; if buffer had tokens from a previous line, clear them
        self._buffer.clear()
        line = self._stream.readline()
        if line == '':
            raise LookupError('NoSuchElementException')
        return line.rstrip('\n')

    def nextInt(self) -> int:
        tok = self.next()
        try:
            return int(tok)
        except Exception:
            raise ValueError(f'InputMismatchException: {tok!r} is not an int')

    def nextDouble(self) -> float:
        tok = self.next()
        try:
            return float(tok)
        except Exception:
            raise ValueError(f'InputMismatchException: {tok!r} is not a float')

    def nextLong(self) -> int:
        tok = self.next()
        try:
            return int(tok)
        except Exception:
            raise ValueError(f'InputMismatchException: {tok!r} is not a long')

    def nextBoolean(self) -> bool:
        tok = self.next().lower()
        if tok in ("true", "t", "1", "yes"):
            return True
        if tok in ("false", "f", "0", "no"):
            return False
        raise ValueError(f'InputMismatchException: {tok!r} is not a boolean')

    def close(self):
        if self._close and self._stream:
            try:
                self._stream.close()
            finally:
                self._stream = None


class File(Object):
    def __init__(self, path: str):
        super().__init__()
        self._path = os.fspath(path)

    # Query methods
    def exists(self) -> bool:
        return os.path.exists(self._path)

    def isDirectory(self) -> bool:
        return os.path.isdir(self._path)

    def isFile(self) -> bool:
        return os.path.isfile(self._path)

    def length(self) -> int:
        try:
            return os.path.getsize(self._path)
        except OSError:
            return 0

    def lastModified(self) -> int:
        try:
            return int(os.path.getmtime(self._path) * 1000)
        except OSError:
            return 0

    # Path info
    def getName(self) -> str:
        return os.path.basename(self._path)

    def getPath(self) -> str:
        return self._path

    def getAbsolutePath(self) -> str:
        return os.path.abspath(self._path)

    # Directory ops
    def mkdir(self) -> bool:
        try:
            os.mkdir(self._path)
            return True
        except Exception:
            return False

    def mkdirs(self) -> bool:
        try:
            os.makedirs(self._path, exist_ok=True)
            return True
        except Exception:
            return False

    def list(self):
        try:
            return os.listdir(self._path)
        except Exception:
            return None

    def delete(self) -> bool:
        try:
            if self.isDirectory():
                os.rmdir(self._path)
            else:
                os.remove(self._path)
            return True
        except Exception:
            return False

    # String form
    def toString(self) -> str:
        return self.getPath()


# ------------------------------------------------------------
# Simple graphics: StdDraw-style wrapper using tkinter
# ------------------------------------------------------------

class _GraphicsCtx:
    def __init__(self):
        self.root = None
        self.canvas = None
        self.width = 0
        self.height = 0
        self.pen = "black"
        self.bg = "white"

    def ensure(self, width: int | None = None, height: int | None = None, title: str | None = None):
        if _tk is None:
            raise RuntimeError("Graphics unavailable: tkinter not installed")
        if self.root is None:
            self.root = _tk.Tk()
            self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        if width and height:
            self.width, self.height = int(width), int(height)
        if self.canvas is None or (width and height):
            if self.canvas is not None:
                self.canvas.destroy()
            self.canvas = _tk.Canvas(self.root, width=self.width, height=self.height, bg=self.bg, highlightthickness=0)
            self.canvas.pack()
        if title:
            try:
                self.root.title(title)
            except Exception:
                pass
        self.root.update_idletasks()
        self.root.update()

_gfx = _GraphicsCtx()


def _parse_color(*args):
    if not args:
        return "black"
    if len(args) == 1:
        c = args[0]
        if isinstance(c, tuple) or isinstance(c, list):
            r, g, b = c
            return f"#{int(r)&255:02x}{int(g)&255:02x}{int(b)&255:02x}"
        if isinstance(c, str):
            return c
        # Single int packed? Not supported; default
        return "black"
    if len(args) >= 3:
        r, g, b = args[:3]
        return f"#{int(r)&255:02x}{int(g)&255:02x}{int(b)&255:02x}"
    return "black"


class Color:
    BLACK = "black"
    WHITE = "white"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    CYAN = "cyan"
    MAGENTA = "magenta"
    GRAY = "gray"


class StdDraw(Object):
    @staticmethod
    def open(width: int, height: int, title: str | None = None):
        _gfx.ensure(width, height, title)

    @staticmethod
    def clear(*color):
        _gfx.ensure()
        _gfx.bg = _parse_color(*color) if color else _gfx.bg
        _gfx.canvas.configure(bg=_gfx.bg)
        _gfx.canvas.delete("all")
        _gfx.root.update_idletasks()
        _gfx.root.update()

    @staticmethod
    def setPenColor(*color):
        _gfx.ensure()
        _gfx.pen = _parse_color(*color)

    @staticmethod
    def line(x0: float, y0: float, x1: float, y1: float):
        _gfx.ensure()
        _gfx.canvas.create_line(float(x0), float(y0), float(x1), float(y1), fill=_gfx.pen)

    @staticmethod
    def circle(x: float, y: float, r: float):
        _gfx.ensure()
        x, y, r = float(x), float(y), float(r)
        _gfx.canvas.create_oval(x - r, y - r, x + r, y + r, outline=_gfx.pen)

    @staticmethod
    def filledCircle(x: float, y: float, r: float):
        _gfx.ensure()
        x, y, r = float(x), float(y), float(r)
        _gfx.canvas.create_oval(x - r, y - r, x + r, y + r, outline=_gfx.pen, fill=_gfx.pen)

    @staticmethod
    def rectangle(x: float, y: float, w: float, h: float):
        _gfx.ensure()
        x, y, w, h = float(x), float(y), float(w), float(h)
        _gfx.canvas.create_rectangle(x, y, x + w, y + h, outline=_gfx.pen)

    @staticmethod
    def filledRectangle(x: float, y: float, w: float, h: float):
        _gfx.ensure()
        x, y, w, h = float(x), float(y), float(w), float(h)
        _gfx.canvas.create_rectangle(x, y, x + w, y + h, outline=_gfx.pen, fill=_gfx.pen)

    @staticmethod
    def text(x: float, y: float, s: str):
        _gfx.ensure()
        _gfx.canvas.create_text(float(x), float(y), text=str(s), fill=_gfx.pen, anchor="center")

    @staticmethod
    def show():
        _gfx.ensure()
        _gfx.root.update_idletasks()
        _gfx.root.update()

    @staticmethod
    def pause(ms: int = 0):
        _gfx.ensure()
        if ms and ms > 0:
            _gfx.root.after(int(ms))
        _gfx.root.update_idletasks()
        _gfx.root.update()

    @staticmethod
    def close():
        if _gfx.root is not None:
            try:
                _gfx.root.destroy()
            finally:
                _gfx.root = None
                _gfx.canvas = None
