import threading
import copy
import sys
import re
import os
import time


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
