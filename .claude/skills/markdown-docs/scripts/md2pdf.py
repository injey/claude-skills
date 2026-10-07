#!/usr/bin/env python3
"""markdown-docs: render Markdown documents and slide decks to HTML and PDF, with optional project styling.

    md2pdf.py [build] <file.md | folder> [...] [options]   build (the default command)
        documents (*.md)          -> PDF (A4/Letter, cover, contents, page numbers); --html keeps the HTML
        decks (*.slides.md, or front matter type: slides)
                                  -> HTML deck (16:9, keyboard navigation, notes) + PDF, one slide per page
    md2pdf.py new <folder> --title "Title"                start a topic from the style's starter deck + document
    md2pdf.py init-style [DIR] [--accent HEX] [--font NAME] [--logo FILE]
                                                         scaffold a project style folder (.md2pdf/)
    md2pdf.py doctor                                     check required tools
    md2pdf.py themes                                     list built-in themes

Style layers, later wins:
  1. theme                <skill>/themes/<name>/ or a folder: config.json, components.css (shared),
                          theme.css + template.html (documents), deck.css + deck.html (decks),
                          mermaid.json, starter/
  2. project style        nearest .md2pdf/ folder above the Markdown file: config.json and mermaid.json are
                          merged, theme.css / deck.css are appended, template.html / deck.html / starter/ replace;
                          config "theme" may name a theme folder inside .md2pdf/
  3. front matter         title, subtitle, author, date, status, version, audience, classification;
                          decks: footer, label; style keys: accent, cover, toc, numbered
  4. command-line flags   --accent, --font, --heading-font, --mono-font, --logo, --page, --cover, --css ...

Requires pandoc and Google Chrome / Chromium / Edge (or CHROME_PATH); mmdc only for Mermaid blocks.
Python 3.9+ standard library only.
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
THEMES_DIR = SKILL_DIR / "themes"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "md2pdf"
PROJECT_DIR_NAME = ".md2pdf"

MD_FORMAT = ("markdown+fenced_divs+pipe_tables+raw_html+raw_attribute"
             "+lists_without_preceding_blankline+task_lists+autolink_bare_uris")
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
H1_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)
STATUS_RE = re.compile(r"^Status:\s*\*\*(.+?)\*\*", re.M)
NUMBERED_HEADING_RE = re.compile(r"^#{2,3}\s+(\d+(\.\d+)*[.)]?|[A-Z]\d*[.)]|§)\s", re.M)
MERMAID_RE = re.compile(r"^(```|~~~)mermaid[^\n]*\n(.*?)^\1[ \t]*$", re.M | re.S)
ALERT_RE = re.compile(r"^> ?\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n((?:>.*(?:\n|$))*)", re.M)
MD_LINK_HREF_RE = re.compile(r'(href=")(?![a-z]+:|#)([^"#]+?)\.md((?:#[^"]*)?")')
META_KEYS = ("title", "subtitle", "author", "date", "status", "version", "audience", "classification")
STYLE_KEYS = ("accent", "cover", "toc", "numbered")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        die(f"'{tool}' not found on PATH (run: md2pdf.py doctor)")
    return path


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")
    return {}


# ---------------------------------------------------------------- colours
def _rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        die(f"not a hex colour: {hex_}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, weight_b: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x * (1 - weight_b) + y * weight_b):02X}" for x, y in zip(ra, rb))


def palette(accent: str, ink: str) -> dict:
    return {
        "accent": accent,
        "accent-dark": mix(accent, "#000000", 0.30),
        "accent-ink": mix(accent, "#000000", 0.45),
        "tint": mix(accent, "#FFFFFF", 0.93),
        "tint-2": mix(accent, "#FFFFFF", 0.86),
        "tint-3": mix(accent, "#FFFFFF", 0.65),
        "ink": ink,
        "muted": mix(ink, "#FFFFFF", 0.35),
        "line": mix(ink, "#FFFFFF", 0.87),
    }


# ---------------------------------------------------------------- style resolution
class Style:
    """The merged result of theme + project style + front matter + CLI."""

    def __init__(self, theme_dir: Path, project_dir: Path | None, cli: dict):
        self.theme_dir = theme_dir
        self.project_dir = project_dir
        self.config = read_json(theme_dir / "config.json")
        self.mermaid = read_json(theme_dir / "mermaid.json")
        shared = [p for p in (theme_dir / "components.css",) if p.exists()]  # used by documents and decks
        self.css_files = shared + [theme_dir / "theme.css"]
        self.deck_css_files = shared + [p for p in (theme_dir / "deck.css",) if p.exists()]
        self.template = theme_dir / "template.html"
        self.deck_template = theme_dir / "deck.html"
        self.starter_dir = theme_dir / "starter"
        self.base_dirs = {"logo": theme_dir}
        if project_dir:
            proj = read_json(project_dir / "config.json")
            proj.pop("theme", None)
            if "logo" in proj:
                self.base_dirs["logo"] = project_dir
            self.config = deep_merge(self.config, proj)
            self.mermaid = deep_merge(self.mermaid, read_json(project_dir / "mermaid.json"))
            if (project_dir / "theme.css").exists():
                self.css_files.append(project_dir / "theme.css")
            if (project_dir / "deck.css").exists():
                self.deck_css_files.append(project_dir / "deck.css")
            if (project_dir / "template.html").exists():
                self.template = project_dir / "template.html"
            if (project_dir / "deck.html").exists():
                self.deck_template = project_dir / "deck.html"
            if (project_dir / "starter").is_dir():
                self.starter_dir = project_dir / "starter"
        self.cli = cli

    def logo_uri(self, cfg: dict) -> str:
        logo = cfg.get("logo")
        if not logo:
            return ""
        lp = Path(logo).expanduser()
        lp = lp if lp.is_absolute() else (self.base_dirs["logo"] / lp)
        if not lp.exists():
            die(f"logo not found: {lp}")
        return data_uri(lp)

    def resolved(self, front: dict) -> dict:
        cfg = dict(self.config)
        for key in STYLE_KEYS:
            if key in front:
                cfg[key] = front[key]
        cfg = deep_merge(cfg, {k: v for k, v in self.cli.items() if v is not None and k != "css"})
        return cfg


def find_project_dir(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        cand = d / PROJECT_DIR_NAME
        if cand.is_dir():
            return cand
    return None


def theme_dir_for(name_or_path: str) -> Path:
    p = Path(name_or_path).expanduser()
    if p.is_dir():
        return p.resolve()
    d = THEMES_DIR / name_or_path
    if not d.is_dir():
        die(f"unknown theme '{name_or_path}'. Built-in: {', '.join(list_themes())}")
    return d


def list_themes() -> list[str]:
    return sorted(p.name for p in THEMES_DIR.iterdir() if (p / "theme.css").exists())


# ---------------------------------------------------------------- generated CSS
def css_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def footer_content(template: str, meta: dict) -> str:
    """Turn 'Page {page} of {pages}' into a CSS content value."""
    if not template:
        return "none"
    for key in META_KEYS:
        template = template.replace("{" + key + "}", str(meta.get(key, "") or ""))
    parts = []
    for tok in re.split(r"(\{page\}|\{pages\})", template):
        if tok == "{page}":
            parts.append("counter(page)")
        elif tok == "{pages}":
            parts.append("counter(pages)")
        elif tok:
            parts.append(css_string(tok))
    return " ".join(parts) or "none"


def font_stack(name: str, fallback: str) -> str:
    return f'"{name}", {fallback}' if name else fallback


def generated_css(cfg: dict, meta: dict, kind: str = "doc") -> str:
    pal = palette(cfg.get("accent", "#3B4CCA"), cfg.get("ink", "#1F2430"))
    fonts = cfg.get("fonts", {})
    body = font_stack(fonts.get("body", ""), "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif")
    heading = font_stack(fonts.get("heading", ""), body)
    mono = font_stack(fonts.get("mono", ""), "SFMono-Regular, Menlo, Consolas, monospace")
    tokens = "\n".join(f"  --{k}: {v};" for k, v in pal.items())
    root = (f":root {{\n{tokens}\n  --font-body: {body};\n  --font-heading: {heading};\n"
            f"  --font-mono: {mono};\n}}\n")
    if kind == "deck":  # slides print one per 16:9 page with no margins or page footers
        return root + "@page slide { size: 1280px 720px; margin: 0; }\n"
    page = cfg.get("page", {})
    size = page.get("size", "A4")
    margin = page.get("margin", "18mm 17mm 20mm 17mm")
    footer = cfg.get("footer", {}) or {}
    foot_font = f"8pt {body}"
    boxes = ""
    for side in ("left", "center", "right"):
        if footer.get(side):
            boxes += (f"  @bottom-{side} {{ content: {footer_content(footer[side], meta)}; "
                      f"font: {foot_font}; color: {pal['muted']}; }}\n")
    first = ""
    if boxes and str(cfg.get("cover", "band")) != "none":
        first = "@page :first {\n" + "".join(
            f"  @bottom-{s} {{ content: none; }}\n" for s in ("left", "center", "right")) + "}\n"
    return root + f"@page {{ size: {size}; margin: {margin};\n{boxes}}}\n{first}"


def google_fonts_link(cfg: dict) -> str:
    if not cfg.get("google_fonts", True):
        return ""
    names = []
    for key in ("heading", "body", "mono"):
        n = (cfg.get("fonts", {}) or {}).get(key)
        if n and n not in names:
            names.append(n)
    if not names:
        return ""
    fams = "&".join(f"family={n.replace(' ', '+')}:wght@400;500;600;700" for n in names)
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link href="https://fonts.googleapis.com/css2?{fams}&display=swap" rel="stylesheet">\n')


# ---------------------------------------------------------------- Markdown preprocessing
def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return meta, text[end + 5:]


def derive_meta(front: dict, body: str, src: Path) -> tuple[dict, str]:
    meta = {k: front[k] for k in META_KEYS if front.get(k)}
    if "title" not in meta:
        m = H1_RE.search(body)
        if m:
            meta["title"] = m.group(1).strip()
            body = body[: m.start()] + body[m.end():]
        else:
            meta["title"] = src.stem.replace("-", " ").replace("_", " ").strip().capitalize()
    if "status" not in meta:
        m = STATUS_RE.search(body)
        if m:
            meta["status"] = m.group(1).rstrip(".").strip()
            body = body[: m.start()] + body[m.end():]  # shown on the cover instead
    if "date" not in meta:
        meta["date"] = _dt.date.fromtimestamp(src.stat().st_mtime).isoformat()
    return meta, body


def convert_alerts(md: str) -> str:
    """GitHub alerts (> [!NOTE] ...) -> pandoc fenced divs with a title."""
    def sub(m: re.Match) -> str:
        kind = m.group(1).lower()
        inner = "\n".join(re.sub(r"^> ?", "", ln) for ln in m.group(2).rstrip("\n").splitlines())
        return f'::: {{.{kind}}}\n[{kind.capitalize()}]{{.callout-title}}\n\n{inner}\n:::\n'
    return ALERT_RE.sub(sub, md)


def render_mermaid(code: str, svg_id: str, config: dict) -> str:
    cfg_text = json.dumps(config, sort_keys=True)
    key = hashlib.sha1((code + cfg_text + svg_id).encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{key}.svg"
    if not out.exists():
        src, cfg = CACHE_DIR / f"{key}.mmd", CACHE_DIR / f"{key}.json"
        src.write_text(code)
        cfg.write_text(cfg_text)
        proc = subprocess.run([need("mmdc"), "-i", str(src), "-o", str(out), "-c", str(cfg),
                               "-b", "transparent", "-I", svg_id, "-q"], capture_output=True, text=True)
        src.unlink(missing_ok=True)
        cfg.unlink(missing_ok=True)
        if proc.returncode != 0 or not out.exists():
            die(f"Mermaid render failed ({svg_id}):\n{proc.stderr or proc.stdout}\n---\n{code}")
    return re.sub(r"^<\?xml[^>]*>\s*", "", out.read_text())


def replace_mermaid(md: str, prefix: str, config: dict) -> str:
    n = [0]

    def sub(m: re.Match) -> str:
        n[0] += 1
        caption, height, lines = "", "", []
        for line in m.group(2).splitlines():
            d = re.match(r"^\s*%%\s*(caption|height)\s*:\s*(.+)$", line)
            if d:
                caption, height = (d.group(2).strip(), height) if d.group(1) == "caption" \
                    else (caption, d.group(2).strip().rstrip("px"))
                continue
            lines.append(line)
        code = "\n".join(lines) + "\n"
        if re.match(r"\s*(flowchart|graph)\b", code):  # theme-coloured classes: class X accent / alert
            tv = config.get("themeVariables", {})
            for name, fill in (("accent", tv.get("primaryBorderColor")), ("alert", "#C53030")):
                if fill and re.search(rf"(:::|\bclass\s+[\w,]+\s+){name}\b", code) and f"classDef {name}" not in code:
                    code += f"    classDef {name} fill:{fill},stroke:{fill},color:#fff\n"
        svg = render_mermaid(code, f"mmd-{prefix}-{n[0]}", config)
        style = f' style="--h:{height}px"' if height else ""
        cap = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
        return f'\n```{{=html}}\n<figure class="diagram"{style}>{svg}{cap}</figure>\n```\n'

    return MERMAID_RE.sub(sub, md)


def mermaid_config(style: Style, cfg: dict) -> dict:
    pal = palette(cfg.get("accent", "#3B4CCA"), cfg.get("ink", "#1F2430"))
    derived = {"themeVariables": {
        "primaryColor": pal["tint"], "primaryBorderColor": pal["accent"], "lineColor": pal["accent-dark"],
        "clusterBkg": mix(pal["accent"], "#FFFFFF", 0.96), "clusterBorder": pal["tint-3"],
        "actorBkg": pal["tint"], "actorBorder": pal["accent"], "signalColor": pal["accent-dark"],
        "labelBoxBkgColor": pal["tint"], "labelBoxBorderColor": pal["accent"],
    }}
    return deep_merge(derived, style.mermaid)  # explicit mermaid.json values win


def inline_local_images(page: str, base: Path) -> str:
    def sub(m: re.Match) -> str:
        src = m.group(2)
        if re.match(r"^(https?:|data:|#)", src):
            return m.group(0)
        p = (base / src).resolve()
        return f"{m.group(1)}{data_uri(p)}{m.group(3)}" if p.exists() else m.group(0)
    return re.sub(r'(<img[^>]*?\ssrc=")([^"]+)(")', sub, page)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "doc"


# ---------------------------------------------------------------- render
def truthy(v) -> bool:
    return str(v).strip().lower() not in ("false", "no", "0", "off", "none", "")


def render_html(src: Path, style: Style, out_html: Path, extra_css: list[Path], link_pdf: bool) -> dict:
    front, body = split_front_matter(src.read_text(encoding="utf-8"))
    cfg = style.resolved(front)
    meta, body = derive_meta(front, body, src)
    for key, val in (cfg.get("meta") or {}).items():  # project-wide cover defaults, e.g. author
        if key in META_KEYS and val:
            meta.setdefault(key, val)
    body = convert_alerts(body)
    body = replace_mermaid(body, slug(src.stem), mermaid_config(style, cfg))

    css = "\n".join(p.read_text(encoding="utf-8") for p in style.css_files + extra_css)
    head = google_fonts_link(cfg) + f"<style>\n{generated_css(cfg, meta)}\n{css}\n</style>\n"
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(head)
        head_path = Path(fh.name)

    args = [need("pandoc"), "-f", MD_FORMAT, "-t", "html5", "-s", "--columns=1000",
            "--template", str(style.template), "-H", str(head_path)]
    for key, val in meta.items():
        args += ["-M", f"{key}={val}"]
    cover = str(cfg.get("cover", "band")).lower()
    if cover in ("band", "plain"):
        args += ["-V", f"cover-{cover}=true"]
    logo = style.logo_uri(cfg)
    if logo:
        args += ["-V", f"logo={logo}"]
    if truthy(cfg.get("toc", True)):
        args += ["--toc", f"--toc-depth={int(cfg.get('toc_depth', 2))}"]
    numbered = str(cfg.get("numbered", "auto")).lower()
    if numbered == "auto":
        numbered = "false" if NUMBERED_HEADING_RE.search(body) else "true"
    if truthy(numbered):
        args.append("--number-sections")
    try:
        proc = subprocess.run(args, input=body, capture_output=True, text=True, cwd=str(src.parent))
    finally:
        head_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        die(f"pandoc failed for {src}:\n{proc.stderr}")
    page = proc.stdout
    if link_pdf:
        page = MD_LINK_HREF_RE.sub(r"\1\2.pdf\3", page)
    out_html.write_text(inline_local_images(page, src.parent), encoding="utf-8")
    return cfg


SLIDE_CLASS_RE = re.compile(r"<!--\s*slide:\s*([\w\s-]+?)\s*-->")
SLIDE_BREAK = "<!--SLIDE-BREAK-->"


def is_deck(src: Path, front: dict | None = None) -> bool:
    if src.name.endswith(".slides.md"):
        return True
    if front is None:
        front, _ = split_front_matter(src.read_text(encoding="utf-8"))
    return front.get("type", "").lower() in ("slides", "deck")


def split_slides(body: str) -> tuple[list[str], list[list[str]]]:
    """Split on lines that are exactly '---' (outside code fences); read <!-- slide: classes -->."""
    chunks, buf, fence = [], [], None
    for line in body.splitlines():
        m = re.match(r"^(```|~~~)", line.strip())
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
        if fence is None and re.match(r"^---\s*$", line):
            chunks.append("\n".join(buf))
            buf = []
        else:
            buf.append(line)
    chunks.append("\n".join(buf))
    chunks = [c for c in chunks if c.strip()]
    classes = []
    for i, chunk in enumerate(chunks):
        m = SLIDE_CLASS_RE.search(chunk)
        classes.append(m.group(1).split() if m else [])
        chunks[i] = SLIDE_CLASS_RE.sub("", chunk)
    return chunks, classes


def render_deck(src: Path, style: Style, out_html: Path, extra_css: list[Path]) -> int:
    """Render a 16:9 slide deck; returns the number of slides."""
    front, body = split_front_matter(src.read_text(encoding="utf-8"))
    cfg = style.resolved(front)
    if not style.deck_template.exists() or not style.deck_css_files:
        die(f"theme {style.theme_dir} has no deck.html / deck.css")
    title = front.get("title", src.stem.replace(".slides", ""))
    footer_title = front.get("footer", title)
    label = front.get("label", "")
    body = convert_alerts(body)
    body = replace_mermaid(body, slug(src.stem.replace(".slides", "")), mermaid_config(style, cfg))
    chunks, classes = split_slides(body)
    proc = subprocess.run(
        [need("pandoc"), "-f", MD_FORMAT, "-t", "html5", "--columns=1000"],
        input=f"\n\n{SLIDE_BREAK}\n\n".join(chunks), capture_output=True, text=True, cwd=str(src.parent))
    if proc.returncode != 0:
        die(f"pandoc failed for {src}:\n{proc.stderr}")
    rendered = proc.stdout.split(SLIDE_BREAK)
    if len(rendered) != len(chunks):
        die("slide split mismatch; avoid '<!--SLIDE-BREAK-->' in content")

    logo = style.logo_uri(cfg)
    total = len(rendered)
    sections = []
    for n, (inner, cls) in enumerate(zip(rendered, classes), start=1):
        lead = f'<img class="title-logo" src="{logo}" alt="">' if ("title" in cls and logo) else ""
        logo_img = f'<img src="{logo}" alt="">' if logo else ""
        foot = (f'<div class="footer">{logo_img}<span>{html.escape(footer_title)}</span>'
                f'<span class="label">{html.escape(label)}</span><span class="spacer"></span>'
                f"<span>{n} / {total}</span></div>")
        sections.append(f'<section class="slide {" ".join(cls)}" id="s{n}"><div class="body">'
                        f"{lead}{inner.strip()}</div>{foot}</section>")

    css = "\n".join(p.read_text(encoding="utf-8") for p in style.deck_css_files + extra_css)
    page = (style.deck_template.read_text(encoding="utf-8")
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{HEAD}}", google_fonts_link(cfg))
            .replace("{{CSS}}", generated_css(cfg, {}, "deck") + css)
            .replace("{{SLIDES}}", "\n".join(sections)))
    out_html.write_text(inline_local_images(page, src.parent), encoding="utf-8")
    return total


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def run_chrome(extra: list[str], url: str, out: Path) -> bool:
    """Headless Chrome sometimes writes its output but never exits: watch the file, then stop Chrome."""
    chrome = find_chrome() or die("Chrome/Chromium/Edge not found; install one or set CHROME_PATH")
    out.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
             "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
             f"--user-data-dir={profile}", *extra, url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        last, stable, deadline = -1, 0, time.time() + 180
        while time.time() < deadline:
            size = out.stat().st_size if out.exists() else -1
            if proc.poll() is not None and size <= 0:
                break
            stable = stable + 1 if size > 0 and size == last else 0
            if stable >= 3 or (proc.poll() is not None and size > 0):
                break
            last = size
            time.sleep(0.5)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    return out.exists() and out.stat().st_size > 0


def print_pdf(html_path: Path, pdf: Path) -> None:
    if not run_chrome(["--no-pdf-header-footer", f"--print-to-pdf={pdf}"], html_path.resolve().as_uri(), pdf):
        die(f"PDF export failed for {html_path}")


def slide_shots(html_path: Path, numbers: list[int], out_dir: Path) -> list[Path]:
    """PNG previews of individual slides (1280x720) for layout checks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for n in numbers:
        png = out_dir / f"{html_path.stem}-{n:02d}.png"
        if run_chrome(["--window-size=1280,720", f"--screenshot={png}"], f"{html_path.resolve().as_uri()}#{n}", png):
            made.append(png)
    return made


# ---------------------------------------------------------------- commands
def collect(targets: list[Path], recursive: bool) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        t = t.expanduser().resolve()
        if t.is_file() and t.suffix.lower() in (".md", ".markdown"):
            files.append(t)
        elif t.is_dir():
            it = t.rglob("*.md") if recursive else t.glob("*.md")
            # skip README files and folders starting with "_" or "." (templates, styles, caches)
            files += sorted(p for p in it if p.name.lower() != "readme.md" and "node_modules" not in p.parts
                            and not any(part.startswith(("_", ".")) for part in p.relative_to(t).parts[:-1]))
        else:
            die(f"not a Markdown file or folder: {t}")
    return files


def cmd_build(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="md2pdf.py build",
                                description="Convert Markdown documents and *.slides.md decks to HTML and/or PDF.")
    p.add_argument("targets", nargs="+", type=Path)
    p.add_argument("-o", "--out-dir", type=Path, help="write outputs here (default: next to each source)")
    p.add_argument("--theme", default=None, help="built-in theme name or a theme folder (default: project's, else 'default')")
    p.add_argument("--style", type=Path, help="project style folder to use instead of auto-discovered .md2pdf/")
    p.add_argument("--no-project-style", action="store_true", help="ignore any .md2pdf/ folder")
    p.add_argument("--css", type=Path, action="append", default=[], help="extra CSS file(s), loaded last")
    p.add_argument("--accent", help="accent colour, e.g. '#0F766E'")
    p.add_argument("--ink", help="body text colour")
    p.add_argument("--font", help="body (and heading) font, e.g. 'Source Sans 3'")
    p.add_argument("--heading-font")
    p.add_argument("--mono-font")
    p.add_argument("--no-google-fonts", action="store_true", help="use locally installed fonts only")
    p.add_argument("--logo", help="logo image shown on the cover")
    p.add_argument("--page", help="page size: A4, Letter, Legal, A3, '210mm 297mm'")
    p.add_argument("--cover", choices=["band", "plain", "none"])
    p.add_argument("--no-toc", action="store_true")
    num = p.add_mutually_exclusive_group()
    num.add_argument("--numbered", dest="numbered", action="store_const", const="true")
    num.add_argument("--no-numbered", dest="numbered", action="store_const", const="false")
    p.add_argument("--no-footer", action="store_true")
    p.add_argument("--recursive", action="store_true", help="include sub-folders when a folder is given")
    p.add_argument("--changed", action="store_true", help="skip files whose PDF is newer than the source")
    p.add_argument("--format", choices=["pdf", "html", "both"],
                   help="outputs to write (default: pdf for documents, both for decks)")
    p.add_argument("--html", action="store_true", help="same as --format both")
    p.add_argument("--html-only", action="store_true", help="same as --format html (fast preview)")
    p.add_argument("--shots", default="", help="decks: PNG previews of slides, e.g. 1,5,9 or 'all'")
    p.add_argument("--keep-md-links", action="store_true", help="don't rewrite links to sibling .md files as .pdf")
    a = p.parse_args(argv)

    cli: dict = {}
    if a.accent: cli["accent"] = a.accent
    if a.ink: cli["ink"] = a.ink
    fonts = {}
    if a.font: fonts.update(body=a.font, heading=a.font)
    if a.heading_font: fonts["heading"] = a.heading_font
    if a.mono_font: fonts["mono"] = a.mono_font
    if fonts: cli["fonts"] = fonts
    if a.no_google_fonts: cli["google_fonts"] = False
    if a.logo: cli["logo"] = str(Path(a.logo).expanduser().resolve())
    if a.page: cli["page"] = {"size": a.page}
    if a.cover: cli["cover"] = a.cover
    if a.no_toc: cli["toc"] = False
    if a.numbered: cli["numbered"] = a.numbered
    if a.no_footer: cli["footer"] = {"left": "", "center": "", "right": ""}

    fmt = a.format or ("html" if a.html_only else "both" if a.html else None)
    built = 0
    for src in collect(a.targets, a.recursive):
        style, project = resolve_style(src, a.theme, a.style, a.no_project_style, cli)
        deck = is_deck(src)
        outputs = style.config.get("outputs") or {}  # e.g. {"document": "both", "deck": "both"}
        out_fmt = fmt or outputs.get("deck" if deck else "document") or ("both" if deck else "pdf")
        stem = src.name[: -len(".slides.md")] if src.name.endswith(".slides.md") else src.stem
        out_dir = (a.out_dir.expanduser().resolve() if a.out_dir else src.parent)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf, out_html = out_dir / f"{stem}.pdf", out_dir / f"{stem}.html"
        newest = out_html if out_fmt == "html" else pdf
        if a.changed and newest.exists() and newest.stat().st_mtime >= src.stat().st_mtime:
            print(f"up to date  {newest}")
            continue
        made = []
        with tempfile.TemporaryDirectory() as tmp:
            html_path = out_html if out_fmt in ("html", "both") else Path(tmp) / out_html.name
            extra = [c.resolve() for c in a.css]
            if deck:
                total = render_deck(src, style, html_path, extra)
            else:
                render_html(src, style, html_path, extra, link_pdf=not a.keep_md_links)
            if out_fmt in ("html", "both"):
                made.append(html_path)
            if out_fmt in ("pdf", "both"):
                print_pdf(html_path, pdf)
                made.append(pdf)
            if deck and a.shots:
                nums = list(range(1, total + 1)) if a.shots == "all" else [int(x) for x in a.shots.split(",") if x.strip()]
                made += slide_shots(html_path, nums, CACHE_DIR / "shots")
        via = f"  (style: {project})" if project else ""
        for m in made:
            print(f"built  {m}{via}")
        built += 1
    return 0 if built or a.changed else 1


def resolve_style(src: Path, theme: str | None, style_dir: Path | None, no_project: bool, cli: dict):
    project = None if no_project else (style_dir.expanduser().resolve() if style_dir else find_project_dir(src.parent))
    theme_name = theme or (read_json(project / "config.json").get("theme") if project else None) or "default"
    if project and not theme and (project / theme_name).is_dir():
        theme_name = str(project / theme_name)  # project theme folder, relative to .md2pdf/
    return Style(theme_dir_for(theme_name), project, cli), project


def cmd_new(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="md2pdf.py new",
                                description="Start a topic folder with the style's starter deck and document.")
    p.add_argument("folder", type=Path, help="topic folder to create, e.g. docs/outbound/q4-review")
    p.add_argument("--title", required=True)
    p.add_argument("--theme")
    p.add_argument("--style", type=Path)
    a = p.parse_args(argv)
    dest = a.folder.expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        die(f"{dest} already exists and is not empty")
    style, project = resolve_style(dest / "x.md", a.theme, a.style, False, {})
    starters = sorted(style.starter_dir.glob("*.md")) if style.starter_dir.is_dir() else []
    if not starters:
        die(f"no starter files in {style.starter_dir}")
    dest.mkdir(parents=True, exist_ok=True)
    name, today = dest.name, _dt.date.today().isoformat()
    for st in starters:
        out = dest / (f"{name}.slides.md" if st.name.endswith(".slides.md") else f"{name}-{st.name}")
        out.write_text(st.read_text(encoding="utf-8").replace("{{TITLE}}", a.title).replace("{{DATE}}", today),
                       encoding="utf-8")
        print(f"created {out}")
    return 0


INIT_CSS = """/* Project overrides for markdown-docs documents (decks: deck.css). Loaded after the theme's CSS.
   Colours and fonts are best set in config.json (accent, ink, fonts); use this file for
   anything else. Tokens: --accent --accent-dark --accent-ink --tint --tint-2 --tint-3
   --ink --muted --line --font-heading --font-body --font-mono

   Examples:
   .cover-band { background: var(--accent); }              flat cover instead of gradient
   h2 { text-transform: uppercase; letter-spacing: .03em; }
   thead th { background: var(--accent); color: #fff; }    solid table headers
*/
"""


def cmd_init_style(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="md2pdf.py init-style", description="Create a project style folder.")
    p.add_argument("dir", nargs="?", type=Path, default=Path.cwd(), help="project folder (default: current)")
    p.add_argument("--accent")
    p.add_argument("--ink")
    p.add_argument("--font")
    p.add_argument("--heading-font")
    p.add_argument("--mono-font")
    p.add_argument("--logo", type=Path)
    p.add_argument("--cover", choices=["band", "plain", "none"])
    p.add_argument("--theme", default="default")
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)

    target = a.dir.expanduser().resolve()
    if target.name != PROJECT_DIR_NAME:
        target = target / PROJECT_DIR_NAME
    if target.exists() and any(target.iterdir()) and not a.force:
        die(f"{target} already exists (use --force to overwrite config.json and theme.css)")
    target.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"theme": a.theme}
    if a.accent: _rgb(a.accent); cfg["accent"] = a.accent
    if a.ink: _rgb(a.ink); cfg["ink"] = a.ink
    fonts = {}
    if a.font: fonts.update(body=a.font, heading=a.font)
    if a.heading_font: fonts["heading"] = a.heading_font
    if a.mono_font: fonts["mono"] = a.mono_font
    if fonts: cfg["fonts"] = fonts
    if a.cover: cfg["cover"] = a.cover
    if a.logo:
        logo = a.logo.expanduser().resolve()
        if not logo.exists():
            die(f"logo not found: {logo}")
        shutil.copy(logo, target / f"logo{logo.suffix.lower()}")
        cfg["logo"] = f"logo{logo.suffix.lower()}"
    (target / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    (target / "theme.css").write_text(INIT_CSS, encoding="utf-8")
    print(f"created {target}/config.json and theme.css")
    print("other optional files: template.html (replaces the theme's), mermaid.json (merged)")
    return 0


def cmd_doctor(_: list[str]) -> int:
    ok = True
    for tool, why in (("pandoc", "required"), ("mmdc", "only for Mermaid diagrams")):
        path = shutil.which(tool)
        print(f"{'ok ' if path else '-- '} {tool:<8} {path or 'not found'}  ({why})")
        ok &= bool(path) or tool == "mmdc"
    chrome = find_chrome()
    print(f"{'ok ' if chrome else '-- '} chrome   {chrome or 'not found (set CHROME_PATH)'}  (required for PDF)")
    swift = shutil.which("swift")
    print(f"{'ok ' if swift else '-- '} swift    {swift or 'not found'}  (optional: page previews on macOS)")
    print(f"themes: {', '.join(list_themes())}   cache: {CACHE_DIR}")
    return 0 if ok and chrome else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    commands = {"build": cmd_build, "new": cmd_new, "init-style": cmd_init_style, "doctor": cmd_doctor,
                "themes": lambda _: print("\n".join(list_themes())) or 0}
    if argv[0] in commands:
        return commands[argv[0]](argv[1:])
    return cmd_build(argv)


if __name__ == "__main__":
    raise SystemExit(main())
