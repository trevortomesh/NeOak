import re
from typing import Tuple, List, Dict, Optional


def _strip_comments(code: str) -> str:
    # Remove // line comments and /* */ block comments
    code = re.sub(r"//.*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    # Remove package and import statements (ignored for now)
    code = re.sub(r"^\s*package\s+[^;]+;\s*", "", code, flags=re.M)
    code = re.sub(r"^\s*import\s+[^;]+;\s*", "", code, flags=re.M)
    return code


def _replace_literals_and_ops(expr: str) -> str:
    # Replace tokens outside of string literals
    out = []
    i = 0
    n = len(expr)
    in_str = False
    str_ch = ''
    while i < n:
        ch = expr[i]
        if in_str:
            out.append(ch)
            if ch == str_ch and (i == 0 or expr[i - 1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        # Logical and/or
        if expr.startswith('&&', i):
            out.append(' and ')
            i += 2
            continue
        if expr.startswith('||', i):
            out.append(' or ')
            i += 2
            continue
        # Not (but not !=)
        if ch == '!' and (i + 1 >= n or expr[i + 1] != '='):
            out.append('not ')
            i += 1
            continue
        # true/false/null as whole words
        m = re.match(r"\b(true|false|null)\b", expr[i:])
        if m:
            tok = m.group(1)
            rep = {'true': 'True', 'false': 'False', 'null': 'None'}[tok]
            out.append(rep)
            i += len(tok)
            continue
        # <expr>.length -> len(<expr>) for simple dotted names
        m = re.match(r"([A-Za-z_][A-Za-z0-9_\.\[\]]*)\.length\b", expr[i:])
        if m:
            tgt = m.group(1)
            out.append(f"len({tgt})")
            i += m.end()
            continue
        # Math.max/min mapping
        if expr.startswith('Math.max', i):
            out.append('max')
            i += len('Math.max')
            continue
        if expr.startswith('Math.min', i):
            out.append('min')
            i += len('Math.min')
            continue
        # obj.toString() -> str(obj) for simple dotted/identifier
        m = re.match(r"([A-Za-z_][A-Za-z0-9_\.]*)\.toString\(\)", expr[i:])
        if m:
            target = m.group(1)
            out.append(f"str({target})")
            i += m.end()
            continue
        # new <type>[size] -> initialized list (primitive)
        m = re.match(r"new\s+(int|double|boolean|String)\s*\[(.*?)\]", expr[i:])
        if m:
            t = m.group(1)
            sz = m.group(2)
            sz_py = _replace_literals_and_ops(sz)
            defaults = {
                'int': '0',
                'double': '0.0',
                'boolean': 'False',
                'String': "''",
            }
            out.append(f"([{defaults[t]}] * ({sz_py}))")
            i += m.end()
            continue
        # new <type>[] { a, b } -> [a, b] (primitive)
        m = re.match(r"new\s+(int|double|boolean|String)\s*\[\]\s*\{(.*?)\}", expr[i:])
        if m:
            elems = m.group(2)
            # Split by commas at top level
            parts = _split_top_level_commas(elems)
            parts = [
                _replace_literals_and_ops(p.strip()) for p in parts if p.strip() != ''
            ]
            out.append("[" + ", ".join(parts) + "]")
            i += m.end()
            continue
        # new ClassName(args) -> ClassName(args)
        m = re.match(r"new\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", expr[i:])
        if m:
            cls = m.group(1)
            out.append(cls + '(')
            i += m.end()
            continue
        # Preserve class-qualified calls; no rewrite here to avoid shadowing issues
        out.append(ch)
        i += 1
    return ''.join(out)


def _map_exception_name(name: str) -> str:
    # Map common Java exception class names (optionally qualified) to Python equivalents
    base = name.split('.')[-1]
    mapping = {
        # Core runtime + argument/state
        'RuntimeException': 'RuntimeError',
        'IllegalArgumentException': 'ValueError',
        'IllegalStateException': 'RuntimeError',
        'UnsupportedOperationException': 'NotImplementedError',

        # Nulls/casts/lookup
        'NullPointerException': 'TypeError',
        'ClassCastException': 'TypeError',
        'NoSuchElementException': 'LookupError',
        'NoSuchMethodException': 'AttributeError',
        'NoSuchFieldException': 'AttributeError',

        # Indexing / bounds
        'IndexOutOfBoundsException': 'IndexError',
        'ArrayIndexOutOfBoundsException': 'IndexError',
        'StringIndexOutOfBoundsException': 'IndexError',

        # IO / Files / Networking
        'IOException': 'OSError',
        'FileNotFoundException': 'FileNotFoundError',
        'EOFException': 'EOFError',
        'SocketException': 'OSError',
        'UnknownHostException': 'OSError',
        'BindException': 'PermissionError',
        'SSLException': 'OSError',
        'ZipException': 'OSError',

        # Import/classpath
        'ClassNotFoundException': 'ImportError',
        'NoClassDefFoundError': 'ImportError',

        # Parsing / formats / URL
        'NumberFormatException': 'ValueError',
        'ParseException': 'ValueError',
        'DateTimeParseException': 'ValueError',
        'PatternSyntaxException': 'ValueError',
        'MalformedURLException': 'ValueError',
        'URISyntaxException': 'ValueError',
        'DataFormatException': 'ValueError',

        # SQL / concurrency / timeouts
        'SQLException': 'RuntimeError',
        'TimeoutException': 'TimeoutError',
        'InterruptedException': 'KeyboardInterrupt',
        'ConcurrentModificationException': 'RuntimeError',

        # Arithmetic
        'ArithmeticException': 'ArithmeticError',

        # Security / access
        'SecurityException': 'PermissionError',
        'AccessControlException': 'PermissionError',

        # Errors
        'AssertionError': 'AssertionError',
        'OutOfMemoryError': 'MemoryError',
        'StackOverflowError': 'RecursionError',

        # Fallbacks
        'Exception': 'Exception',
        'Error': 'Exception',
    }
    return mapping.get(base, base)


def _split_top_level_plus(expr: str) -> list[str]:
    parts = []
    buf = []
    depth = 0
    in_str = False
    str_ch = ''
    i = 0
    while i < len(expr):
        ch = expr[i]
        if in_str:
            buf.append(ch)
            if ch == str_ch and expr[i - 1] != '\\':
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            buf.append(ch)
            i += 1
            continue
        if ch == '(':
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == '+' and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append(''.join(buf).strip())
    return parts


def _translate_statement(line: str) -> str:
    l = line.strip()
    if not l:
        return ""

    # Remove trailing semicolon if present
    if l.endswith(";"):
        l = l[:-1]

    # System.out.println
    m = re.match(r"System\.out\.println\((.*)\)$", l)
    if m:
        inner = m.group(1).strip()
        expr = _maybe_rewrite_string_concat(inner)
        return f"print({expr})"

    # System.out.print (no newline)
    m = re.match(r"System\.out\.print\((.*)\)$", l)
    if m:
        inner = m.group(1).strip()
        expr = _maybe_rewrite_string_concat(inner)
        return f"print({expr}, end='')"

    # Variable declarations with optional initializer
    m = re.match(
        r"(?:final\s+)?(int|double|boolean|String|[A-Z][A-Za-z0-9_<>]*)(\[\])?\s+(\w+)\s*(?:=\s*(.*))?$",
        l,
    )
    if m:
        name = m.group(3)
        init = m.group(4)
        if init is None:
            return f"{name} = None"
        init_py = _maybe_rewrite_string_concat(init)
        return f"{name} = {init_py}"

    # ++ / -- as statements
    m = re.match(r"(\w+)\s*\+\+\s*$", l)
    if m:
        return f"{m.group(1)} += 1"
    m = re.match(r"(\w+)\s*--\s*$", l)
    if m:
        return f"{m.group(1)} -= 1"

    # return statement
    m = re.match(r"return\s+(.*)$", l)
    if m:
        return f"return {_maybe_rewrite_string_concat(m.group(1))}"

    # throw statements
    m = re.match(r"throw\s+new\s+([A-Za-z_][A-Za-z0-9_\.]*?)\s*\((.*)\)\s*$", l)
    if m:
        cls = _map_exception_name(m.group(1))
        args = _replace_literals_and_ops(m.group(2))
        return f"raise {cls}({args})"
    m = re.match(r"throw\s+([A-Za-z_][A-Za-z0-9_\.]*?)\s*;?$", l)
    if m:
        return f"raise {_map_exception_name(m.group(1))}"

    # function call, assignment, or general expression
    return _maybe_rewrite_string_concat(l)


def _translate_for_header(header: str) -> Tuple[str, int]:
    # Try to convert canonical for-loops into Python for-range.
    # Returns tuple (python_header_line, indent_delta_after_header)
    h = header.strip()
    # for (int i = 0; i < n; i++)
    m = re.match(
        r"for\s*\(\s*(?:int|double|boolean|String)?\s*(\w+)\s*=\s*([^;]+);\s*\1\s*([<>]=?|==|!=)\s*([^;]+);\s*\1\+\+\s*\)\s*\{?\s*$",
        h,
    )
    if m:
        var, start, op, end = m.groups()
        start_py = _replace_literals_and_ops(start)
        end_py = _replace_literals_and_ops(end)
        if op == "<":
            return (f"for {var} in range({start_py}, {end_py}):", 1)
        if op == "<=":
            return (f"for {var} in range({start_py}, ({end_py}) + 1):", 1)
        # Fallback to while-based lowering
    # Decrement pattern
    m = re.match(
        r"for\s*\(\s*(?:int|double|boolean|String)?\s*(\w+)\s*=\s*([^;]+);\s*\1\s*([<>]=?)\s*([^;]+);\s*\1--\s*\)\s*\{?\s*$",
        h,
    )
    if m:
        var, start, op, end = m.groups()
        start_py = _replace_literals_and_ops(start)
        end_py = _replace_literals_and_ops(end)
        if op == ">":
            return (f"for {var} in range({start_py}, {end_py}, -1):", 1)
        if op == ">=":
            return (f"for {var} in range({start_py}, ({end_py}) - 1, -1):", 1)
    # Generic fallback: emit init before, while header, and we'll need to insert increment later
    return ("", 0)


def _replace_this_tokens(s: str) -> str:
    # Replace 'this' tokens and 'this.' with 'self' variants outside strings
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == str_ch and (i == 0 or s[i - 1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        # this.
        if s.startswith('this.', i):
            out.append('self.')
            i += len('this.')
            continue
        # this as a standalone token
        m = re.match(r"\bthis\b", s[i:])
        if m:
            out.append('self')
            i += len('this')
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _replace_super_tokens(s: str) -> str:
    # Rewrite Java super(...) and super.method(...) into Python super().__init__(...) / super().method(...)
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == str_ch and (i == 0 or s[i - 1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        if s.startswith('super.', i):
            out.append('super().')
            i += len('super.')
            continue
        if s.startswith('super(', i):
            out.append('super().__init__(')
            i += len('super(')
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _replace_field_tokens(s: str, field_names: set[str], locals_set: set[str]) -> str:
    # Qualify bare field identifiers with self.<name> outside strings.
    # Skip if already qualified (preceded by '.'), or if token is a known local/param.
    if not field_names:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == str_ch and (i == 0 or s[i-1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        if (ch.isalpha() or ch == '_'):
            j = i+1
            while j < n and (s[j].isalnum() or s[j] == '_'):
                j += 1
            tok = s[i:j]
            prev = s[i-1] if i > 0 else ''
            if tok in field_names and tok not in locals_set and prev != '.':
                out.append('self.' + tok)
            else:
                out.append(tok)
            i = j
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _qualify_static_calls(s: str, class_name: str, static_names: set[str]) -> str:
    # Qualify calls to unqualified static methods of the current class to avoid name shadowing in Python.
    if not static_names:
        return s
    out = []
    i = 0
    n = len(s)
    in_str = False
    str_ch = ''
    while i < n:
        ch = s[i]
        if in_str:
            out.append(ch)
            if ch == str_ch and (i == 0 or s[i-1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue
        # detect identifier followed by '(' not preceded by '.' or alnum/underscore
        if ch.isalpha() or ch == '_':
            j = i+1
            while j < n and (s[j].isalnum() or s[j] == '_'):
                j += 1
            name = s[i:j]
            k = j
            while k < n and s[k].isspace():
                k += 1
            prev = s[i-1] if i > 0 else ''
            if name in static_names and k < n and s[k] == '(' and prev not in ('.',) and not (prev.isalnum() or prev == '_'):
                out.append(f"{class_name}.{name}")
                i = j
                continue
            out.append(name)
            i = j
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _translate_block(body: str, instance: bool = False, field_names: set[str] | None = None, param_names: list[str] | None = None, class_name: str | None = None, static_names: set[str] | None = None, source_file: str | None = None, source_start_line: int | None = None) -> str:
    # Convert a Java-like block (no method/class signatures) into Python
    lines = [ln for ln in body.splitlines()]
    out: list[str] = []
    indent = 0
    pending_for_init = None
    pending_for_update = None
    field_names = field_names or set()
    locals_set: set[str] = set(param_names or [])

    def emit(line: str):
        if line is None:
            return
        # Add source mapping marker if available
        if source_file and source_start_line is not None and line.strip() != "":
            out.append(("    " * indent) + f"# NEOAK_SRC: {source_file}:{source_start_line + i}")
        out.append(("    " * indent) + line)

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if instance:
            # Map 'this' and 'super' in instance contexts
            raw = _replace_this_tokens(raw)
            raw = _replace_super_tokens(raw)
            raw = _replace_field_tokens(raw, field_names, locals_set)
        # Qualify unqualified static method calls in both static and instance contexts
        if class_name and static_names:
            raw = _qualify_static_calls(raw, class_name, static_names)
        line = raw.strip()

        # Skip empty lines
        if line == "":
            out.append("")
            i += 1
            continue

        # Handle else/else if closing previous block
        m = re.match(r"}\s*else\s+if\s*\((.*)\)\s*{\s*$", line)
        if m:
            indent = max(0, indent - 1)
            cond = _replace_literals_and_ops(m.group(1))
            emit(f"elif {cond}:")
            indent += 1
            i += 1
            continue

        m = re.match(r"}\s*else\s*{\s*$", line)
        if m:
            indent = max(0, indent - 1)
            emit("else:")
            indent += 1
            i += 1
            continue

        # Close blocks for bare '}'
        if line == "}":
            indent = max(0, indent - 1)
            i += 1
            continue

        # Expand inline blocks with both { and } on the same line
        if '{' in line and '}' in line and line.index('{') < line.rindex('}'):
            before = line[: line.index('{') + 1].strip()
            inner = line[line.index('{') + 1 : line.rindex('}')].strip()
            after = line[line.rindex('}') + 1 :].strip()
            # Insert back into lines: header, inner statements (one per line), closing brace, then after
            insert = []
            insert.append(before)
            for stmt in _split_top_level_semicolons(inner):
                if stmt.strip():
                    insert.append(stmt.strip() + ';')
            insert.append('}')
            if after:
                insert.append(after)
            # Replace current line with expanded lines
            lines[i : i + 1] = insert
            # Continue without increment so we process the new header
            continue

        # if / while headers
        m = re.match(r"if\s*\((.*)\)\s*{\s*$", line)
        if m:
            cond_src = m.group(1)
            if instance:
                cond_src = _replace_field_tokens(cond_src, field_names, locals_set)
            cond = _replace_literals_and_ops(cond_src)
            emit(f"if {cond}:")
            indent += 1
            i += 1
            continue

        m = re.match(r"while\s*\((.*)\)\s*{\s*$", line)
        if m:
            cond_src = m.group(1)
            if instance:
                cond_src = _replace_field_tokens(cond_src, field_names, locals_set)
            cond = _replace_literals_and_ops(cond_src)
            emit(f"while {cond}:")
            indent += 1
            i += 1
            continue

        # switch header: capture until matching brace
        m = re.match(r"switch\s*\((.*)\)\s*{\s*$", line)
        if m:
            switch_expr = _replace_literals_and_ops(m.group(1).strip())
            # collect lines for switch block
            brace = 1
            j = i + 1
            block_lines = []
            while j < len(lines) and brace > 0:
                ln = lines[j]
                block_lines.append(ln)
                brace += ln.count('{')
                brace -= ln.count('}')
                j += 1
            # remove the last line(s) that close the switch
            # Adjust to exclude the final closing '}'
            while block_lines and block_lines[-1].strip() == '}':
                block_lines.pop()
            # Parse cases
            cases = []  # list of (values:list[str] or None for default, body_lines:list[str])
            cur_vals = None
            cur_body = []
            def flush():
                nonlocal cur_vals, cur_body
                if cur_vals is not None or cur_body:
                    cases.append((cur_vals, cur_body))
                cur_vals = None
                cur_body = []
            k = 0
            while k < len(block_lines):
                l2 = block_lines[k].strip()
                mcase = re.match(r"case\s+([^:]+):\s*$", l2)
                mdef = re.match(r"default\s*:\s*$", l2)
                if mcase:
                    flush()
                    val = mcase.group(1).strip()
                    cur_vals = [val]
                elif mdef:
                    flush()
                    cur_vals = []  # empty list marks default
                else:
                    # Stop current case on 'break;'
                    if l2 == 'break;' or l2 == 'break':
                        flush()
                    else:
                        cur_body.append(block_lines[k])
                k += 1
            flush()
            # Merge fallthrough cases: fold empty-case bodies into the next non-empty body
            merged = []
            pending_vals = []
            for vals, body_lines in cases:
                if vals is None:
                    continue
                if vals != [] and len([ln for ln in body_lines if ln.strip() and ln.strip() != 'break;' and ln.strip() != 'break']) == 0:
                    pending_vals.extend(vals)
                    continue
                # attach pending fallthrough values
                if vals != []:
                    vals = pending_vals + vals
                    pending_vals = []
                merged.append((vals, body_lines))
            cases = merged

            # Emit switch as if/elif/else
            emit(f"__sw = {switch_expr}")
            first = True
            for vals, body_lines in cases:
                if vals is None:
                    continue
                if vals == []:
                    # default
                    emit("else:")
                else:
                    conds = [f"__sw == {_replace_literals_and_ops(v)}" for v in vals]
                    kw = "if" if first else "elif"
                    emit(f"{kw} " + " or ".join(conds) + ":")
                    first = False
                indent += 1
                # translate body
                inner = _translate_block("\n".join(body_lines), instance=instance)
                for inner_ln in inner.splitlines():
                    emit(inner_ln)
                indent -= 1
            # If there was no default and no cases, emit pass
            if not cases:
                emit("pass")
            i = j
            continue

        # try { ... } catch (...) { ... } finally { ... }
        if re.match(r"try\s*{\s*$", line):
            # Capture try block
            brace = 1
            j = i + 1
            try_lines = []
            while j < len(lines) and brace > 0:
                ln = lines[j]
                if re.match(r"}\s*catch\s*\(.*\)\s*{\s*$", ln.strip()) or re.match(r"}\s*finally\s*{\s*$", ln.strip()):
                    break
                try_lines.append(ln)
                brace += ln.count('{')
                brace -= ln.count('}')
                j += 1
            # Collect catches and finally
            catches = []  # list of (types:list[str], name:str, body_lines:list[str])
            finally_lines = None
            # Now iterate over zero or more catch blocks
            while j < len(lines):
                s = lines[j].strip()
                mc = re.match(r"}\s*catch\s*\(\s*([^\)]+)\s+(\w+)\s*\)\s*{\s*$", s)
                mf = re.match(r"}\s*finally\s*{\s*$", s)
                if mc:
                    typespec = mc.group(1).strip()
                    name = mc.group(2).strip()
                    types = [t.strip() for t in typespec.split('|')]
                    # collect catch body
                    j += 1
                    brace2 = 1
                    body2 = []
                    while j < len(lines) and brace2 > 0:
                        ln2 = lines[j]
                        body2.append(ln2)
                        brace2 += ln2.count('{')
                        brace2 -= ln2.count('}')
                        j += 1
                    # remove trailing closing brace
                    while body2 and body2[-1].strip() == '}':
                        body2.pop()
                    catches.append((types, name, body2))
                    continue
                elif mf:
                    # collect finally body
                    j += 1
                    brace3 = 1
                    fbody = []
                    while j < len(lines) and brace3 > 0:
                        ln3 = lines[j]
                        fbody.append(ln3)
                        brace3 += ln3.count('{')
                        brace3 -= ln3.count('}')
                        j += 1
                    while fbody and fbody[-1].strip() == '}':
                        fbody.pop()
                    finally_lines = fbody
                    break
                else:
                    # End of try-catch-finally
                    break
            # Emit Python try/except/finally
            emit("try:")
            indent += 1
            inner = _translate_block("\n".join(try_lines), instance=instance)
            for inner_ln in inner.splitlines():
                emit(inner_ln)
            indent -= 1
            for types, name, body2 in catches:
                mapped = [_map_exception_name(t) for t in types] if types else ["Exception"]
                types_py = ", ".join(mapped) if len(mapped) > 1 else (mapped[0])
                emit(f"except ({types_py}) as {name}:") if len(mapped) > 1 else emit(f"except {types_py} as {name}:")
                indent += 1
                inner2 = _translate_block("\n".join(body2), instance=instance)
                for inner_ln in inner2.splitlines():
                    emit(inner_ln)
                indent -= 1
            if finally_lines is not None:
                emit("finally:")
                indent += 1
                innerf = _translate_block("\n".join(finally_lines), instance=instance)
                for inner_ln in innerf.splitlines():
                    emit(inner_ln)
                indent -= 1
            i = j
            continue

        # for-each header: for (Type name : expr) {
        m = re.match(r"for\s*\(\s*(?:final\s+)?[A-Za-z_][A-Za-z0-9_<>\[\]]*\s+(\w+)\s*:\s*(.*)\)\s*\{\s*$", line)
        if m:
            var = m.group(1)
            iter_src = m.group(2).strip()
            if instance:
                iter_src = _replace_field_tokens(iter_src, field_names, locals_set)
            iterable = _replace_literals_and_ops(iter_src)
            emit(f"for {var} in {iterable}:")
            indent += 1
            i += 1
            continue

        # for header
        if line.startswith("for "):
            # Try canonical range conversion
            h_line, delta = _translate_for_header(line)
            if h_line:
                emit(h_line)
                indent += delta
                i += 1
                continue
            # Fallback: attempt simple while-lowering for pattern: for (init; cond; update) {
            m_for = re.match(r"for\s*\(([^;]+);([^;]+);([^\)]+)\)\s*{\s*$", line)
            if m_for:
                init_src = m_for.group(1).strip()
                cond_src = m_for.group(2).strip()
                upd_src = m_for.group(3).strip()
                if instance:
                    init_src = _replace_field_tokens(init_src, field_names, locals_set)
                    cond_src = _replace_field_tokens(cond_src, field_names, locals_set)
                    upd_src = _replace_field_tokens(upd_src, field_names, locals_set)
                pending_for_init = _translate_statement(init_src + ";")
                while_cond = _replace_literals_and_ops(cond_src)
                pending_for_update = _translate_statement(upd_src + ";")
                if pending_for_init:
                    emit(pending_for_init)
                emit(f"while {while_cond}:")
                indent += 1
                i += 1
                continue

        # Block open with trailing '{' (e.g., naked block)
        if line.endswith("{"):
            head = line[:-1].strip()
            if head:
                # Treat as a new scope; in Python we emulate with just a block using 'if True:'
                emit("if True:")
            else:
                emit("if True:")
            indent += 1
            i += 1
            continue

        # Line possibly closes a for-block: detect pattern of '}' then emit update
        if line == "}" and pending_for_update:
            indent = max(0, indent - 1)
            emit(pending_for_update)
            pending_for_update = None
            i += 1
            continue

        # Regular statement(s); may contain multiple semicolon-separated parts
        stmts = _split_top_level_semicolons(line)
        for s in stmts:
            s = s.strip()
            if not s:
                continue
            if not s.endswith(';'):
                s = s + ';'
            # Track method-scope locals from declarations
            decl_m = re.match(r"(?:final\s+)?(int|double|boolean|String|[A-Z][A-Za-z0-9_<>]*)(\[\])?\s+(\w+)\s*(?:=\s*(.*))?;\s*$", s)
            if decl_m:
                locals_set.add(decl_m.group(3))
            py_stmt = _translate_statement(s)
            if py_stmt:
                emit(py_stmt)
        i += 1

    return "\n".join(out) + "\n"


class ClassSpec:
    def __init__(self, name: str):
        self.name = name
        self.base: Optional[str] = None
        self.fields: List[Tuple[str, str, Optional[str]]] = []  # (type, name, init)
        # (ret, name, params, body, src_path, start_line)
        self.static_methods: List[Tuple[str, str, str, str, str, int]] = []
        # (ret, name, params, body, src_path, start_line)
        self.instance_methods: List[Tuple[str, str, str, str, str, int]] = []
        # list of (params, body, src_path, start_line)
        self.ctors: List[Tuple[str, str, str, int]] = []


def _find_matching_brace(s: str, start_index: int) -> int:
    # start_index should point to the '{' character
    if start_index < 0 or start_index >= len(s) or s[start_index] != '{':
        return -1
    depth = 1
    i = start_index + 1
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_classes(code: str) -> List[ClassSpec]:
    classes: List[ClassSpec] = []
    i = 0
    n = len(code)
    # Build file markers table for source mapping
    file_marks: List[Tuple[int, str]] = []  # (content_start_idx, path)
    for m in re.finditer(r"^NEOAK_FILE:(.*)$", code, flags=re.M):
        path = m.group(1).strip()
        content_start = m.end()
        if content_start < len(code) and code[content_start] == '\n':
            content_start += 1
        file_marks.append((content_start, path))
    file_marks.sort(key=lambda x: x[0])

    def find_src(pos: int) -> Tuple[str, int]:
        # Returns (path, line_number)
        current_path = "<unknown>"
        start_idx = 0
        for s, p in file_marks:
            if s <= pos:
                current_path = p
                start_idx = s
            else:
                break
        line_no = code[start_idx:pos].count('\n') + 1
        return current_path, line_no
    while i < n:
        m = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{", code[i:])
        if not m:
            break
        cls_name = m.group(1)
        base_name = m.group(2)
        body_start = i + m.end()
        body_end = _find_matching_brace(code, body_start - 1)
        if body_end == -1:
            break
        body = code[body_start:body_end]
        spec = ClassSpec(cls_name)
        spec.base = base_name

        # Extract methods and constructors first to avoid mis-parsing fields
        j = 0
        removed_ranges: List[Tuple[int, int]] = []
        while j < len(body):
            # Constructor and methods
            ctor_pat = re.compile((r"(public|private|protected)?\s*" + re.escape(cls_name) + r"\s*\(([^)]*)\)\s*\{"))
            mc = ctor_pat.search(body[j:])
            mm = re.search(r"(?:(?:public|private|protected)\s+)?(?:static\s+)?(?!public\b|private\b|protected\b)([A-Za-z_][A-Za-z0-9_<>\[\]]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{", body[j:])
            # Choose earliest
            candidates = []
            if mc:
                candidates.append((j + mc.start(), 'ctor', mc))
            if mm:
                candidates.append((j + mm.start(), 'method', mm))
            if not candidates:
                break
            candidates.sort(key=lambda x: x[0])
            k, kind, msel = candidates[0]
            hdr_end = j + msel.end()
            blk_end = _find_matching_brace(body, hdr_end - 1)
            if blk_end == -1:
                break
            chunk = body[hdr_end:blk_end]
            # Absolute index of header end in full code
            abs_hdr_end = body_start + hdr_end
            src_path, start_line = find_src(abs_hdr_end)
            if kind == 'ctor':
                params = msel.group(2).strip()
                spec.ctors.append((params, chunk, src_path, start_line))
            else:
                # Using new pattern groups
                # Static detection is tricky here; we infer static if 'this' is not used? too complex.
                # Instead, detect 'static' by peeking at header text
                header_text = body[k:hdr_end]
                is_static = ' static ' in f' {header_text} '
                rettype = msel.group(1)
                name = msel.group(2)
                params = msel.group(3).strip()
                if is_static:
                    spec.static_methods.append((rettype, name, params, chunk, src_path, start_line))
                else:
                    spec.instance_methods.append((rettype, name, params, chunk, src_path, start_line))
            removed_ranges.append((k, blk_end + 1))
            j = blk_end + 1

        # Collect only top-level text (depth==0) for field parsing
        top_level_chars = []
        depth = 0
        k = 0
        while k < len(body):
            ch = body[k]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)
            else:
                if depth == 0:
                    top_level_chars.append(ch)
            k += 1
        leftover = ''.join(top_level_chars)
        # Scan for field declarations (non-static) at top-level
        for decl in leftover.split(';'):
            d = decl.strip()
            if not d:
                continue
            # skip blocks or lines with braces
            if '{' in d or '}' in d:
                continue
            mfield = re.match(r"(public|private|protected)?\s*(final\s+)?(int|double|boolean|String|[A-Za-z_][A-Za-z0-9_<>]*)(\[\])?\s+(\w+)\s*(?:=\s*(.*))?$", d)
            if mfield and ' static ' not in d:
                typ = mfield.group(3)
                name = mfield.group(5)
                init = mfield.group(6).strip() if mfield.group(6) else None
                spec.fields.append((typ, name, init))

        classes.append(spec)
        i = body_end + 1
    return classes


def _translate_params(param_str: str) -> Tuple[str, list[str]]:
    if not param_str or param_str.strip() == "":
        return "", []
    params = []
    names = []
    for p in param_str.split(","):
        p = p.strip()
        if not p:
            continue
        # Remove array brackets and generics naively
        parts = p.split()
        name = parts[-1]
        # Remove trailing [] if present
        name = re.sub(r"\[\]$", "", name)
        params.append(name)
        names.append(name)
    return ", ".join(params), names


def _parse_params_detailed(param_str: str) -> List[Tuple[str, bool, str]]:
    # Returns list of (type, is_array, name)
    res: List[Tuple[str, bool, str]] = []
    if not param_str or param_str.strip() == "":
        return res
    for p in param_str.split(','):
        p = p.strip()
        if not p:
            continue
        parts = p.split()
        if len(parts) < 2:
            # Fallback
            name = parts[-1]
            res.append(("Object", False, name))
            continue
        typ = parts[-2]
        name = parts[-1]
        is_array = typ.endswith('[]') or name.endswith('[]')
        typ = re.sub(r"\[\]$", "", typ)
        name = re.sub(r"\[\]$", "", name)
        # Strip generic params
        typ = re.sub(r"<.*>", "", typ)
        res.append((typ, is_array, name))
    return res


def transpile(code: str) -> str:
    """
    Transpile a minimal Java-like NeOak source into Python code.
    Supports:
    - Class with static methods
    - static void main(String[] args)
    - if/else if/else, while, for (limited forms)
    - variable declarations, return
    - System.out.println
    """
    code = _strip_comments(code)

    py_lines = [
        "# Generated by NeOak transpiler",
        "from typing import *",
        "def _neoak_strcat(*parts):\n    return ''.join(str(p) for p in parts)\n",
        "def _neoak_plus(*parts):\n    acc = None\n    for p in parts:\n        if acc is None:\n            acc = p\n        else:\n            if isinstance(acc, str) or isinstance(p, str):\n                acc = str(acc) + str(p)\n            else:\n                acc = acc + p\n    return acc\n",
        "def _neoak_is_type(x, t, arr=False):\n"
        "    if arr:\n"
        "        return isinstance(x, list)\n"
        "    if t == 'boolean':\n"
        "        return isinstance(x, bool)\n"
        "    if t == 'String':\n"
        "        return isinstance(x, str)\n"
        "    if t == 'int':\n"
        "        return isinstance(x, int) and not isinstance(x, bool)\n"
        "    if t == 'double':\n"
        "        return (isinstance(x, float) or (isinstance(x, int) and not isinstance(x, bool)))\n"
        "    try:\n"
        "        cls = globals().get(t)\n"
        "        return isinstance(x, cls) if cls else True\n"
        "    except Exception:\n"
        "        return True\n",
    ]

    classes = _extract_classes(code)
    if not classes:
        raise ValueError("No classes found. Define at least one class with a static main method.")

    main_found = False
    main_class_name = None
    main_params = None
    main_body = None

    # Generate Python classes
    for cls in classes:
        base = cls.base if cls.base else "object"
        py_lines.append(f"class {cls.name}({base}):")
        field_set = {name for (_typ, name, _init) in cls.fields}
        # __init__ with overload dispatch
        if cls.ctors:
            py_lines.append("    def __init__(self, *args):")
            # Field defaults first
            for (typ, name, init) in cls.fields:
                if init is not None:
                    init_py = _maybe_rewrite_string_concat(init)
                    py_lines.append(f"        self.{name} = {init_py}")
                else:
                    defaults = {'int': '0', 'double': '0.0', 'boolean': 'False', 'String': "''"}
                    py_lines.append(f"        self.{name} = {defaults.get(typ, 'None')}")
            # Overload branches
            for (params, body, src_path, start_line) in cls.ctors:
                details = _parse_params_detailed(params)
                arity = len(details)
                cond = [f"len(args) == {arity}"]
                type_checks = []
                for idx, (t, is_arr, name) in enumerate(details):
                    type_checks.append(f"_neoak_is_type(args[{idx}], '{t}', {str(is_arr)})")
                if type_checks:
                    cond.append(" and ".join(type_checks))
                py_lines.append(f"        if {' and '.join(cond)}:")
                # param bindings
                for idx, (_, _, name) in enumerate(details):
                    py_lines.append(f"            {name} = args[{idx}]")
                # optional super call
                if cls.base and 'super(' not in body:
                    py_lines.append("            super().__init__()")
                ctor_param_names = [n for (_t, _arr, n) in details]
                py_body = _translate_block(body, instance=True, field_names=field_set, param_names=ctor_param_names, class_name=cls.name, static_names={name for (_ret, name, _params, _body, *_extra) in cls.static_methods}, source_file=src_path, source_start_line=start_line)
                py_lines.append("".join(["            " + ln if ln else ln for ln in py_body.splitlines(True)]))
                py_lines.append("            return")
            py_lines.append("        raise TypeError('No matching constructor for given arguments')")
        else:
            py_lines.append("    def __init__(self):")
            for (typ, name, init) in cls.fields:
                if init is not None:
                    init_py = _maybe_rewrite_string_concat(init)
                    py_lines.append(f"        self.{name} = {init_py}")
                else:
                    defaults = {'int': '0', 'double': '0.0', 'boolean': 'False', 'String': "''"}
                    py_lines.append(f"        self.{name} = {defaults.get(typ, 'None')}")
            if cls.base:
                py_lines.append("        super().__init__()")
            else:
                py_lines.append("        pass")

        # Group methods by name for overloading
        inst_groups: Dict[str, List[Tuple[str, str, str, str, int]]] = {}
        for (ret, name, params, body, src_path, start_line) in cls.instance_methods:
            inst_groups.setdefault(name, []).append((params, body, ret, src_path, start_line))

        for name, overs in inst_groups.items():
            if len(overs) == 1:
                params, body, _, src_path, start_line = overs[0]
                params_py, _names = _translate_params(params)
                py_lines.append(f"    def {name}(self, {params_py}):")
                py_body = _translate_block(body, instance=True, field_names=field_set, param_names=_names, class_name=cls.name, static_names={name for (_ret, name, _params, _body, *_extra) in cls.static_methods}, source_file=src_path, source_start_line=start_line)
                py_lines.append("".join(["        " + ln if ln else ln for ln in py_body.splitlines(True)]))
            else:
                # Create specific variants
                for idx, (params, body, _, src_path, start_line) in enumerate(overs):
                    details = _parse_params_detailed(params)
                    params_py = ", ".join([n for (_, _, n) in details])
                    py_lines.append(f"    def {name}__ov{idx}(self, {params_py}):")
                    param_names = [n for (_t, _arr, n) in details]
                    py_body = _translate_block(body, instance=True, field_names=field_set, param_names=param_names, class_name=cls.name, static_names={name for (_ret, name, _params, _body, *_extra) in cls.static_methods}, source_file=src_path, source_start_line=start_line)
                    py_lines.append("".join(["        " + ln if ln else ln for ln in py_body.splitlines(True)]))
                # Dispatcher
                py_lines.append(f"    def {name}(self, *args):")
                for idx, (params, _body, _ret, _src, _ln) in enumerate(overs):
                    details = _parse_params_detailed(params)
                    arity = len(details)
                    cond = [f"len(args) == {arity}"]
                    type_checks = []
                    for aidx, (t, is_arr, _n) in enumerate(details):
                        type_checks.append(f"_neoak_is_type(args[{aidx}], '{t}', {str(is_arr)})")
                    if type_checks:
                        cond.append(" and ".join(type_checks))
                    py_lines.append(f"        if {' and '.join(cond)}:")
                    call_args = ", ".join([f"args[{i}]" for i in range(arity)])
                    py_lines.append(f"            return self.{name}__ov{idx}({call_args})")
                py_lines.append("        raise TypeError('No matching overload for method')")

        # If class defines toString(), add __str__ alias for Python printing
        if 'toString' in inst_groups:
            # Find zero-arg variant if any
            has_zero = any(len(_parse_params_detailed(p)) == 0 for (p, _b, _r) in inst_groups['toString'])
            if has_zero:
                py_lines.append("    def __str__(self):")
                py_lines.append("        return self.toString()")

        # Static methods grouped by name
        static_groups: Dict[str, List[Tuple[str, str, str, str, int]]] = {}
        for (ret, name, params, body, src_path, start_line) in cls.static_methods:
            static_groups.setdefault(name, []).append((params, body, ret, src_path, start_line))

        for name, overs in static_groups.items():
            if len(overs) == 1:
                params, body, _, src_path, start_line = overs[0]
                params_py, _names = _translate_params(params)
                py_lines.append("    @staticmethod")
                py_lines.append(f"    def {name}({params_py}):")
                py_body = _translate_block(body, class_name=cls.name, static_names={name for (_ret, name, _params, _body, *_extra) in cls.static_methods}, source_file=src_path, source_start_line=start_line)
                py_lines.append("".join(["        " + ln if ln else ln for ln in py_body.splitlines(True)]))
                if name == 'main':
                    main_found = True
                    main_class_name = cls.name
            else:
                # Specific variants
                for idx, (params, body, _, src_path, start_line) in enumerate(overs):
                    details = _parse_params_detailed(params)
                    params_py = ", ".join([n for (_, _, n) in details])
                    py_lines.append("    @staticmethod")
                    py_lines.append(f"    def {name}__ov{idx}({params_py}):")
                    py_body = _translate_block(body, class_name=cls.name, static_names={name for (_ret, name, _params, _body, *_extra) in cls.static_methods}, source_file=src_path, source_start_line=start_line)
                    py_lines.append("".join(["        " + ln if ln else ln for ln in py_body.splitlines(True)]))
                # Dispatcher
                py_lines.append("    @staticmethod")
                py_lines.append(f"    def {name}(*args):")
                for idx, (params, _body, _ret, _src, _ln) in enumerate(overs):
                    details = _parse_params_detailed(params)
                    arity = len(details)
                    cond = [f"len(args) == {arity}"]
                    type_checks = []
                    for aidx, (t, is_arr, _n) in enumerate(details):
                        type_checks.append(f"_neoak_is_type(args[{aidx}], '{t}', {str(is_arr)})")
                    if type_checks:
                        cond.append(" and ".join(type_checks))
                    py_lines.append(f"        if {' and '.join(cond)}:")
                    call_args = ", ".join([f"args[{i}]" for i in range(arity)])
                    py_lines.append(f"            return {cls.name}.{name}__ov{idx}({call_args})")
                py_lines.append("        raise TypeError('No matching overload for static method')")
                if name == 'main':
                    main_found = True
                    main_class_name = cls.name

        py_lines.append("")

    if not main_found:
        raise ValueError("No static main method found. Expected: static void main(String[] args) { ... }")

    # No global static wrappers; prefer ClassName.method to avoid shadowing
    py_lines.append("")

    # Launcher that calls ClassName.main(args)
    py_lines.append("if __name__ == '__main__':")
    py_lines.append("    import sys")
    py_lines.append(f"    {main_class_name}.main(sys.argv[1:])")

    return "\n".join(py_lines) + "\n"


def _split_top_level_commas(s: str) -> list[str]:
    parts = []
    buf = []
    depth = 0
    in_str = False
    str_ch = ''
    for i, ch in enumerate(s):
        if in_str:
            buf.append(ch)
            if ch == str_ch and s[i - 1] != '\\':
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            buf.append(ch)
            continue
        if ch == '(' or ch == '[' or ch == '{':
            depth += 1
            buf.append(ch)
            continue
        if ch == ')' or ch == ']' or ch == '}':
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == ',' and depth == 0:
            parts.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append(''.join(buf))
    return parts


def _maybe_rewrite_string_concat(expr: str) -> str:
    expr = expr.strip()
    # If the expression is an assignment like x = a + b, rewrite RHS only
    m = re.match(r"^(.*?=)(.*)$", expr)
    if m:
        left = m.group(1)
        right = m.group(2)
        return left + _maybe_rewrite_string_concat(right)

    parts = _split_top_level_plus(expr)
    if len(parts) <= 1:
        return _replace_literals_and_ops(expr)
    # Use Java-like plus semantics at runtime: numeric addition unless a string is encountered
    parts = [_replace_literals_and_ops(p.strip()) for p in parts]
    return "_neoak_plus(" + ", ".join(parts) + ")"


def _split_top_level_semicolons(s: str) -> list[str]:
    parts = []
    buf = []
    depth = 0
    in_str = False
    str_ch = ''
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str:
            buf.append(ch)
            if ch == str_ch and (i == 0 or s[i - 1] != '\\'):
                in_str = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            buf.append(ch)
            i += 1
            continue
        if ch in '([{':
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch in ')]}':
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == ';' and depth == 0:
            parts.append(''.join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append(''.join(buf))
    return parts
