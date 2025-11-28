from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class MethodDoc:
    name: str
    ret: Optional[str]  # None for constructors
    params_src: str
    access: str
    is_static: bool
    is_abstract: bool
    javadoc: Optional[str] = None
    tags: dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ClassDoc:
    name: str
    kind: str  # 'class' or 'interface'
    package: Optional[str]
    extends: Optional[str] = None
    implements: List[str] = field(default_factory=list)
    javadoc: Optional[str] = None
    methods: List[MethodDoc] = field(default_factory=list)
    fields: List["FieldDoc"] = field(default_factory=list)


@dataclass
class FieldDoc:
    name: str
    typ: str
    access: str
    is_static: bool
    is_final: bool
    javadoc: Optional[str] = None


def _gather_sources(base: Path) -> list[tuple[str, str]]:
    root = base if base.is_dir() else base.parent
    files = [
        p for p in root.rglob("*") if p.is_file() and p.suffix in (".java", ".nk", ".nk.java")
    ]
    files.sort(key=lambda p: str(p.relative_to(root)))
    out: list[tuple[str, str]] = []
    for p in files:
        rel = str(p.relative_to(root))
        out.append((rel, p.read_text(encoding="utf-8")))
    return out


def _extract_package(src: str) -> Optional[str]:
    m = re.search(r"^\s*package\s+([^;]+);", src, flags=re.M)
    return m.group(1).strip() if m else None


def _find_javadoc_before(src: str, pos: int) -> Optional[str]:
    # Find the nearest /** ... */ block that ends before pos
    upto = src[:pos]
    m = list(re.finditer(r"/\*\*(.*?)\*/", upto, flags=re.S))
    if not m:
        return None
    return m[-1].group(1)


def _parse_javadoc(block: str) -> tuple[str, dict[str, List[str]]]:
    text = block.strip()
    # Strip leading * prefixes
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith('*'):
            ln = ln[1:].lstrip()
        lines.append(ln)
    desc_lines: List[str] = []
    tags: dict[str, List[str]] = {}
    current_tag: Optional[str] = None
    for ln in lines:
        if ln.startswith('@'):
            parts = ln.split(None, 1)
            tag = parts[0][1:]
            rest = parts[1] if len(parts) > 1 else ''
            tags.setdefault(tag, []).append(rest)
            current_tag = tag
        else:
            if current_tag is None:
                desc_lines.append(ln)
            else:
                # continuation of previous tag
                if tags[current_tag]:
                    tags[current_tag][-1] += ('\n' + ln) if ln else ''
    return ("\n".join(desc_lines).strip(), tags)


def _extract_classes(src: str) -> list[ClassDoc]:
    docs: List[ClassDoc] = []
    pkg = _extract_package(src)
    # Class or interface with optional generics, extends/implements
    for m in re.finditer(r"(class|interface)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]*>)?\s*(?:extends\s+([^\{\n]+?))?\s*(?:implements\s+([^\{\n]+?))?\s*\{", src):
        kind = m.group(1)
        name = m.group(2)
        extends = m.group(3).strip() if m.group(3) else None
        impls = [s.strip() for s in (m.group(4) or '').split(',') if s and s.strip()]
        jd_raw = _find_javadoc_before(src, m.start())
        jd_desc = None
        if jd_raw:
            jd_desc, _ = _parse_javadoc(jd_raw)
        cd = ClassDoc(name=name, kind=kind, package=pkg, extends=extends, implements=impls, javadoc=jd_desc)
        # Extract members within the class body (approximate)
        body_start = m.end()
        # naive body end: count braces
        depth = 1
        i = body_start
        while i < len(src) and depth > 0:
            if src[i] == '{':
                depth += 1
            elif src[i] == '}':
                depth -= 1
            i += 1
        body = src[body_start:i-1]
        # Fields
        for fm in re.finditer(r"(?m)^(\s*)(public|protected|private)?\s*(static\s+)?(final\s+)?([A-Za-z_][A-Za-z0-9_<>,\.\[\]\s]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=[^;]*)?;\s*$", body):
            access = (fm.group(2) or 'public').strip()
            is_static = bool(fm.group(3))
            is_final = bool(fm.group(4))
            typ = fm.group(5).strip()
            fname = fm.group(6)
            abs_pos = body_start + fm.start()
            jd_raw = _find_javadoc_before(src, abs_pos)
            fdoc = FieldDoc(name=fname, typ=typ, access=access, is_static=is_static, is_final=is_final, javadoc=(_parse_javadoc(jd_raw)[0] if jd_raw else None))
            cd.fields.append(fdoc)
        # Constructors
        ctor_pattern = re.compile(r"(?m)^(\s*)(public|protected|private)?\s*" + re.escape(name) + r"\s*\(([^)]*)\)\s*(\{|;)\s*$")
        for mm in ctor_pattern.finditer(body):
            access = (mm.group(2) or 'public').strip()
            params_src = mm.group(3)
            abs_pos = body_start + mm.start()
            jd_raw = _find_javadoc_before(src, abs_pos)
            jdesc, tags = (_parse_javadoc(jd_raw) if jd_raw else (None, {}))
            md = MethodDoc(name=name, ret=None, params_src=params_src, access=access, is_static=False, is_abstract=(mm.group(4) == ';'), javadoc=jdesc, tags=tags)
            cd.methods.append(md)
        # Methods (including abstract/interface with ;)
        for mm in re.finditer(r"(?m)^(\s*)(public|private|protected)?\s*(static\s+)?(abstract\s+)?([A-Za-z_][A-Za-z0-9_<>,\.\[\]\s]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(\{|;)\s*$", body):
            access = (mm.group(2) or 'public').strip()
            is_static = bool(mm.group(3))
            is_abstract = bool(mm.group(4) or mm.group(8) == ';')
            ret = mm.group(5).strip()
            mname = mm.group(6)
            if mname == name:
                continue
            params_src = mm.group(7)
            abs_pos = body_start + mm.start()
            jd_raw = _find_javadoc_before(src, abs_pos)
            jdesc, tags = (_parse_javadoc(jd_raw) if jd_raw else (None, {}))
            md = MethodDoc(name=mname, ret=ret, params_src=params_src, access=access, is_static=is_static, is_abstract=is_abstract, javadoc=jdesc, tags=tags)
            cd.methods.append(md)
        docs.append(cd)
    return docs


def _html_escape(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _class_filename(cd: ClassDoc) -> str:
    pkg = cd.package or 'default'
    return f"{pkg}.{cd.name}.html"


def _write_index(outdir: Path, classes: List[ClassDoc]):
    outdir.mkdir(parents=True, exist_ok=True)
    # group by package
    pkgs: dict[str, list[ClassDoc]] = {}
    for c in classes:
        key = c.package or '(default)'
        pkgs.setdefault(key, []).append(c)
    # package list
    plist = []
    for pkg in sorted(pkgs.keys()):
        plist.append(f"<li><a href='package-{pkg.replace('.', '_')}.html'>{pkg}</a></li>")
    # all classes
    items = []
    for pkg, clist in sorted(pkgs.items(), key=lambda x: x[0]):
        for c in sorted(clist, key=lambda x: x.name):
            items.append(f"<li><a href=\"{_class_filename(c)}\">{c.name}</a> <span class=\"kind\">({c.kind})</span> <span class='pkg'>{pkg}</span></li>")
    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>NeOak Docs</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:0;}}
header{{background:#0b5394;color:#fff;padding:12px 16px;}}
main{{padding:16px;}}
ul{{line-height:1.7;}}
.kind{{color:#666;font-size:12px;}}
a{{color:#0b5394;text-decoration:none;}}
a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<header><h1 style='margin:0'>NeOak API</h1></header>
<main>
<h2>Packages</h2>
<ul>
{''.join(plist)}
</ul>

<h2>All Classes & Interfaces</h2>
<ul>
{''.join(items)}
</ul>
</main>
</body></html>
"""
    (outdir / "index.html").write_text(html, encoding='utf-8')

    # write package summary pages
    for pkg, clist in pkgs.items():
        rows = []
        for c in sorted(clist, key=lambda x: x.name):
            rows.append(f"<tr><td>{c.kind}</td><td><a href='{_class_filename(c)}'>{c.name}</a></td><td>{_html_escape(c.javadoc or '')}</td></tr>")
        phtml = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>Package {pkg} - NeOak API</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:0;}}
header{{background:#0b5394;color:#fff;padding:12px 16px;}}
main{{padding:16px;max-width:980px;margin:0 auto;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border-bottom:1px solid #e5e5e5;padding:8px 6px;text-align:left;vertical-align:top;}}
th{{background:#f7f7f7;}}
a{{color:#0b5394;text-decoration:none;}}
a:hover{{text-decoration:underline;}}
</style>
</head>
<body>
<header><nav><a href='index.html'>&larr; Index</a></nav><h1 style='margin:0'>Package { _html_escape(pkg) }</h1></header>
<main>
<table>
<tr><th>Kind</th><th>Name</th><th>Description</th></tr>
{''.join(rows)}
</table>
</main>
</body></html>
"""
        (outdir / f"package-{pkg.replace('.', '_')}.html").write_text(phtml, encoding='utf-8')


def _write_class(outdir: Path, cd: ClassDoc):
    # Split methods/constructors and prepare field list
    ctors = [m for m in cd.methods if m.ret is None]
    meths = [m for m in cd.methods if m.ret is not None]
    meths.sort(key=lambda m: (m.name, m.params_src))
    ctors.sort(key=lambda m: m.params_src)
    fields = sorted(cd.fields, key=lambda f: f.name)

    # Summaries
    field_rows = []
    for f in fields:
        mods = ' '.join([f.access] + (["static"] if f.is_static else []) + (["final"] if f.is_final else []))
        field_rows.append(f"<tr><td class='acc'>{mods}</td><td class='sig'>{_html_escape(f.typ)} {_html_escape(f.name)}</td><td class='sum'>{_html_escape(f.javadoc or '')}</td></tr>")

    ctor_rows = []
    for c in ctors:
        mods = c.access
        ctor_rows.append(f"<tr><td class='acc'>{mods}</td><td class='sig'>{_html_escape(cd.name)}({_html_escape(c.params_src)})</td><td class='sum'>{_html_escape(c.javadoc or '')}</td></tr>")

    meth_rows = []
    for m in meths:
        mods = ' '.join([m.access] + (["static"] if m.is_static else []) + (["abstract"] if m.is_abstract else []))
        sig = _html_escape(f"{m.ret} {m.name}({m.params_src})")
        meth_rows.append(f"<tr><td class='acc'>{mods}</td><td class='sig'>{sig}</td><td class='sum'>{_html_escape(m.javadoc or '')}</td></tr>")

    # Details
    field_details = []
    for f in fields:
        field_details.append(f"<h3 id='field-{_html_escape(f.name)}'>{_html_escape(f.name)}</h3>")
        field_details.append(f"<pre class='decl'>{_html_escape(f.typ)} {_html_escape(f.name)}</pre>")
        if f.javadoc:
            field_details.append(f"<p>{_html_escape(f.javadoc)}</p>")

    ctor_details = []
    for c in ctors:
        ctor_details.append(f"<h3 id='ctor-{_html_escape(c.params_src)}'>{_html_escape(cd.name)}({_html_escape(c.params_src)})</h3>")
        ctor_details.append(f"<pre class='decl'>{_html_escape(cd.name)}({_html_escape(c.params_src)})</pre>")
        if c.javadoc:
            ctor_details.append(f"<p>{_html_escape(c.javadoc)}</p>")
        if c.tags:
            ctor_details.append("<dl>")
            for tag, vals in c.tags.items():
                for v in vals:
                    ctor_details.append(f"<dt>@{_html_escape(tag)}</dt><dd>{_html_escape(v)}</dd>")
            ctor_details.append("</dl>")

    meth_details = []
    for m in meths:
        meth_details.append(f"<h3 id='method-{_html_escape(m.name)}'>{_html_escape(m.name)}</h3>")
        meth_details.append(f"<pre class='decl'>{_html_escape(m.ret or '')} {_html_escape(m.name)}({_html_escape(m.params_src)})</pre>")
        if m.javadoc:
            meth_details.append(f"<p>{_html_escape(m.javadoc)}</p>")
        if m.tags:
            meth_details.append("<dl>")
            for tag, vals in m.tags.items():
                for v in vals:
                    meth_details.append(f"<dt>@{_html_escape(tag)}</dt><dd>{_html_escape(v)}</dd>")
            meth_details.append("</dl>")

    pkg = _html_escape(cd.package or '(default)')
    jdoc = _html_escape(cd.javadoc or '')
    extends = _html_escape(cd.extends) if cd.extends else ''
    impls = ', '.join(_html_escape(x) for x in cd.implements) if cd.implements else ''
    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>{_html_escape(cd.name)} - NeOak API</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:0;}}
header{{background:#0b5394;color:#fff;padding:12px 16px;}}
main{{padding:16px;max-width:980px;margin:0 auto;}}
.meta{{color:#333;margin:4px 0 12px;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border-bottom:1px solid #e5e5e5;padding:8px 6px;text-align:left;vertical-align:top;}}
th{{background:#f7f7f7;}}
pre.decl{{background:#f7f7f7;padding:8px;border-radius:4px;}}
a{{color:#0b5394;text-decoration:none;}}
a:hover{{text-decoration:underline;}}
nav a{{margin-right:12px;}}
</style>
</head>
<body>
<header><nav><a href='index.html'>&larr; Index</a> <a href='package-{_html_escape((cd.package or '(default)').replace('.', '_'))}.html'>{pkg}</a></nav><h1 style='margin:0'>{_html_escape(cd.kind.title())} { _html_escape(cd.name) }</h1></header>
<main>
<div class='meta'>Package: {pkg}</div>
<div class='meta'>Extends: {extends}</div>
<div class='meta'>Implements: {impls}</div>
<p>{jdoc}</p>

<h2>Field Summary</h2>
<table>
<tr><th>Modifier and Type</th><th>Field</th><th>Description</th></tr>
{''.join(field_rows) or '<tr><td colspan=3><em>None</em></td></tr>'}
</table>

<h2>Constructor Summary</h2>
<table>
<tr><th>Constructor</th><th>Description</th></tr>
{''.join(ctor_rows) or '<tr><td colspan=2><em>None</em></td></tr>'}
</table>

<h2>Method Summary</h2>
<table>
<tr><th>Modifier/Type</th><th>Method</th><th>Description</th></tr>
{''.join(meth_rows) or '<tr><td colspan=3><em>None</em></td></tr>'}
</table>

<h2>Field Detail</h2>
{''.join(field_details) or '<p><em>None</em></p>'}

<h2>Constructor Detail</h2>
{''.join(ctor_details) or '<p><em>None</em></p>'}

<h2>Method Detail</h2>
{''.join(meth_details) or '<p><em>None</em></p>'}

</main>
</body></html>
"""
    (outdir / _class_filename(cd)).write_text(html, encoding='utf-8')


def generate_docs(path: str, outdir: str) -> None:
    base = Path(path)
    entries = _gather_sources(base)
    classes: List[ClassDoc] = []
    for rel, src in entries:
        classes.extend(_extract_classes(src))
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    _write_index(out, classes)
    for cd in classes:
        _write_class(out, cd)
