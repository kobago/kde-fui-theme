#!/usr/bin/env python3
"""FUI theme generator for KDE Plasma 6.

One palette (tokens) -> every artefact:
  dist/color-schemes/FUI<Name>.colors            KDE colour scheme (Qt / Breeze / GTK bridge)
  dist/plasma/desktoptheme/fui-<name>/           Plasma desktop theme (panel, popups, tooltips, ...)
  dist/aurorae/themes/FUI-<Name>/                Aurorae window decoration (square, glow border)
  dist/wallpapers/FUI-<Name>/                    Wallpaper package (grid + scanlines)
  dist/plasma/look-and-feel/org.kobago.fui.<name>/  Global theme tying everything together
  dist/konsole/FUI-<Name>.colorscheme            Konsole colour scheme
  dist/ghostty/fui-<name>                        Ghostty theme

Only the standard library is required. PyQt6 is used when present to build the
kdeglobals font strings; otherwise a known-good template is used.
Rendering PNGs (wallpaper, previews) needs `rsvg-convert`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
AUTHOR = "kobago"
VERSION = "1.0.0"

# --------------------------------------------------------------------------- tokens
# Values from the FUI skill `tokens.md` (CYAN / AMBER / GREEN). One app, one palette.
PALETTES = {
    "cyan": dict(
        Name="Cyan",
        accent="#00E5FF", accent_dim="#00788C",
        warn="#FFAA28", danger="#FF465A", ok="#50FFA0",
        text="#AAE6F0", text_dim="#5A8C9B",
        bg_deep="#060C12", bg_panel="#0A1620",
        term_blue="#00788C", term_magenta="#8C7AB4", term_cyan="#00E5FF",
    ),
    "amber": dict(
        Name="Amber",
        accent="#FFB020", accent_dim="#8C6010",
        warn="#00E5FF", danger="#FF465A", ok="#50FFA0",
        text="#F0DCB4", text_dim="#96825A",
        bg_deep="#120C04", bg_panel="#1E1608",
        term_blue="#6A8CA8", term_magenta="#B08C9C", term_cyan="#00E5FF",
    ),
    "green": dict(
        Name="Green",
        accent="#46FF8C", accent_dim="#1E8246",
        warn="#FFAA28", danger="#FF465A", ok="#00E5FF",
        text="#B4F0C8", text_dim="#5A966E",
        bg_deep="#041008", bg_panel="#081C0E",
        term_blue="#3C8C8C", term_magenta="#8CA0B4", term_cyan="#00E5FF",
    ),
}

BG_ALPHA = 0.92        # bg_deep for panel / popups
PANEL_ALPHA = 0.78     # bg_panel for widgets
GLOW = ((3.25, 0.10), (5.75, 0.05), (8.25, 0.033), (10.75, 0.025))  # extent px, alpha

# Fonts (pt). One place for the type scale.
# "FUI Mono" is Share Tech Mono with its vertical metrics matched to Noto Sans CJK JP (see make_fui_mono),
# so lines that mix Latin and Japanese keep the same baseline as Latin-only lines.
UI_MONO = "FUI Mono"
USE_FUI_MONO = False            # False = leave the general/fixed/menu/toolbar fonts at the system default (Breeze: Noto Sans / Hack).
                                # The user preferred the stock Latin font; only the window title uses Orbitron.
FONT_GENERAL = (UI_MONO, 11)
FONT_FIXED = (UI_MONO, 11)
FONT_SMALL = (UI_MONO, 9.5)
FONT_TITLE = ("Orbitron", 10)   # window titles: uppercase, +12 % tracking, semibold
MONO_ADVANCE_EM = 0.60          # FUI Mono cell width. Share Tech Mono is 0.54em (tight); Hack / DejaVu Mono are 0.60em.
CJK_FALLBACK_TTC = "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"
CJK_FALLBACK_FAMILY = "Noto Sans CJK JP"


# --------------------------------------------------------------------------- colour helpers
def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def hexs(c) -> str:
    return "#%02x%02x%02x" % tuple(c)


def mix(a, b, t: float):
    """a*(1-t) + b*t"""
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def over(fg, alpha: float, bg):
    """fg composited with `alpha` over bg (opaque result)."""
    return mix(bg, fg, alpha)


def kde(c) -> str:
    return "%d,%d,%d" % tuple(c)


class Pal:
    """Palette tokens as RGB tuples plus derived opaque colours."""

    def __init__(self, key: str, d: dict):
        self.key = key
        self.Name = d["Name"]
        for k, v in d.items():
            if isinstance(v, str) and v.startswith("#"):
                setattr(self, k, rgb(v))
        self.white = (255, 255, 255)
        # derived opaque values for the KDE colour scheme
        self.win_bg = self.bg_panel
        self.win_alt = mix(self.bg_panel, self.accent_dim, 0.10)
        self.view_bg = self.bg_deep
        self.view_alt = mix(self.bg_deep, self.bg_panel, 0.6)
        self.button_bg = over(self.accent_dim, 0.28, self.bg_panel)
        self.button_alt = over(self.accent_dim, 0.45, self.bg_panel)
        self.sel_bg = over(self.accent, 0.35, self.bg_deep)
        self.sel_alt = over(self.accent, 0.20, self.bg_deep)

    def h(self, name: str) -> str:
        return hexs(getattr(self, name))

    # ids / names
    @property
    def scheme_id(self):      # FUICyan
        return f"FUI{self.Name}"

    @property
    def scheme_name(self):    # FUI Cyan
        return f"FUI {self.Name}"

    @property
    def plasma_id(self):      # fui-cyan
        return f"fui-{self.key}"

    @property
    def aurorae_id(self):     # FUI-Cyan
        return f"FUI-{self.Name}"

    @property
    def wallpaper_id(self):
        return f"FUI-{self.Name}"

    @property
    def lnf_id(self):
        return f"org.kobago.fui.{self.key}"


# --------------------------------------------------------------------------- SVG helpers
def el_rect(x, y, w, h, color, alpha, id=None):
    idattr = f' id="{id}"' if id else ""
    return (f'<rect{idattr} x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'style="fill:{color};fill-opacity:{alpha:.3f};stroke:none"/>')


def el_group(id, x, y, inner):
    return f'<g id="{id}" transform="translate({x:g},{y:g})">{inner}</g>'


def svg_doc(w, h, body, pal: Pal | None = None):
    style = ""
    if pal:
        style = ("<style type=\"text/css\" id=\"current-color-scheme\">"
                 f".ColorScheme-Text{{color:{pal.h('text')};}}"
                 f".ColorScheme-Background{{color:{pal.h('bg_deep')};}}"
                 f".ColorScheme-Highlight{{color:{pal.h('accent')};}}"
                 f".ColorScheme-ButtonBackground{{color:{hexs(pal.button_bg)};}}"
                 f".ColorScheme-ButtonFocus{{color:{pal.h('accent')};}}"
                 f".ColorScheme-ButtonHover{{color:{pal.h('accent')};}}"
                 f".ColorScheme-Frame{{color:{pal.h('accent_dim')};}}"
                 "</style>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}">\n'
            f'<defs>{style}</defs>\n{body}\n</svg>\n')


PIECES = ("topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright")


class Sheet:
    """Collects FrameSvg element groups and lays them out on a grid (no overlaps)."""

    def __init__(self, pal: Pal):
        self.pal = pal
        self.out: list[str] = []
        self.y = 0
        self.w = 0

    def _advance(self, w, h):
        self.y += h + 8
        self.w = max(self.w, w)

    def nine(self, prefix, cell, fill=None, line=None, line_w=1,
             line_sides=("top", "bottom", "left", "right"), center=32, margin=None):
        """9-slice frame. cell = border thickness (int) or (top, bottom, left, right)."""
        p = prefix + "-" if prefix else ""
        t, b, l, r = (cell,) * 4 if isinstance(cell, (int, float)) else cell
        geo = {
            "topleft": (0, 0, l, t), "top": (l, 0, center, t), "topright": (l + center, 0, r, t),
            "left": (0, t, l, center), "center": (l, t, center, center), "right": (l + center, t, r, center),
            "bottomleft": (0, t + center, l, b), "bottom": (l, t + center, center, b),
            "bottomright": (l + center, t + center, r, b),
        }
        for name, (x, y, w, h) in geo.items():
            if w <= 0 or h <= 0:
                continue
            inner = el_rect(0, 0, w, h, *(fill or ("#000000", 0.0)))
            if line:
                lc, la = line
                if name.startswith("top") and "top" in line_sides:
                    inner += el_rect(0, 0, w, line_w, lc, la)
                if name.startswith("bottom") and "bottom" in line_sides:
                    inner += el_rect(0, h - line_w, w, line_w, lc, la)
                if name.endswith("left") and "left" in line_sides:
                    inner += el_rect(0, 0, line_w, h, lc, la)
                if name.endswith("right") and "right" in line_sides:
                    inner += el_rect(w - line_w, 0, line_w, h, lc, la)
            self.out.append(el_group(p + name, x, self.y + y, inner))
        total_h = t + center + b
        total_w = l + center + r
        if margin is not None:
            ms = (margin,) * 4 if isinstance(margin, (int, float)) else margin
            for i, side in enumerate(("top", "bottom", "left", "right")):
                m = ms[i]
                w = m if side in ("left", "right") else 4
                h = m if side in ("top", "bottom") else 4
                self.out.append(el_rect(total_w + 8 + i * 12, self.y, w, h, "#ff00ff", 1,
                                        id=f"{p}hint-{side}-margin"))
            total_w += 8 + 4 * 12
        self._advance(total_w, total_h)

    def glow(self, prefix, color, g=11, center=32, layers=GLOW):
        """Frame of light outside an edge, 4 stepped layers, no blur. Used as the 'shadow' prefix."""
        p = prefix + "-"
        geo = {
            "topleft": (0, 0), "top": (g, 0), "topright": (g + center, 0),
            "left": (0, g), "center": (g, g), "right": (g + center, g),
            "bottomleft": (0, g + center), "bottom": (g, g + center), "bottomright": (g + center, g + center),
        }
        for name, (x, y) in geo.items():
            w = center if name in ("top", "bottom", "center") else g
            h = center if name in ("left", "right", "center") else g
            inner = el_rect(0, 0, w, h, "#000000", 0.0)
            for ext, a in reversed(layers):
                e = min(ext, g)
                if name == "top":
                    inner += el_rect(0, g - e, w, e, color, a)
                elif name == "bottom":
                    inner += el_rect(0, 0, w, e, color, a)
                elif name == "left":
                    inner += el_rect(g - e, 0, e, h, color, a)
                elif name == "right":
                    inner += el_rect(0, 0, e, h, color, a)
                elif name == "topleft":
                    inner += el_rect(g - e, g - e, e, e, color, a)
                elif name == "topright":
                    inner += el_rect(0, g - e, e, e, color, a)
                elif name == "bottomleft":
                    inner += el_rect(g - e, 0, e, e, color, a)
                elif name == "bottomright":
                    inner += el_rect(0, 0, e, e, color, a)
            self.out.append(el_group(p + name, x, self.y + y, inner))
        self._advance(2 * g + center, 2 * g + center)

    def raw(self, id, w, h, inner):
        self.out.append(el_group(id, 0, self.y, inner))
        self._advance(w, h)

    def doc(self):
        return svg_doc(max(self.w, 1), max(self.y, 1), "\n".join(self.out), self.pal)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- KDE colour scheme
def colors_file(p: Pal) -> str:
    def group(bg, alt, fg=None, fg_inactive=None):
        fg = fg or p.text
        fg_inactive = fg_inactive or p.text_dim
        return "\n".join([
            f"BackgroundAlternate={kde(alt)}",
            f"BackgroundNormal={kde(bg)}",
            f"DecorationFocus={kde(p.accent)}",
            f"DecorationHover={kde(p.accent)}",
            f"ForegroundActive={kde(p.accent)}",
            f"ForegroundInactive={kde(fg_inactive)}",
            f"ForegroundLink={kde(p.accent)}",
            f"ForegroundNegative={kde(p.danger)}",
            f"ForegroundNeutral={kde(p.warn)}",
            f"ForegroundNormal={kde(fg)}",
            f"ForegroundPositive={kde(p.ok)}",
            f"ForegroundVisited={kde(p.accent_dim)}",
        ])

    return f"""# {p.scheme_name} -- generated by build.py (kde-fui-theme). Do not edit by hand.
[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0

[Colors:Button]
{group(p.button_bg, p.button_alt)}

[Colors:Complementary]
{group(p.bg_deep, p.bg_panel)}

[Colors:Header]
{group(p.bg_deep, p.bg_panel)}

[Colors:Header][Inactive]
{group(p.bg_deep, p.bg_panel, fg=p.text_dim)}

[Colors:Selection]
{group(p.sel_bg, p.sel_alt)}

[Colors:Tooltip]
{group(p.bg_deep, p.bg_panel)}

[Colors:View]
{group(p.view_bg, p.view_alt)}

[Colors:Window]
{group(p.win_bg, p.win_alt)}

[General]
ColorScheme={p.scheme_id}
Name={p.scheme_name}
shadeSortColumn=true

[KDE]
contrast=4

[WM]
activeBackground={kde(p.bg_deep)}
activeBlend={kde(p.bg_deep)}
activeForeground={kde(p.accent)}
inactiveBackground={kde(p.bg_deep)}
inactiveBlend={kde(p.bg_deep)}
inactiveForeground={kde(p.text_dim)}
"""


# --------------------------------------------------------------------------- Plasma desktop theme
def surface_svg(p: Pal, alpha, margin, bg="bg_deep", glow=True):
    """Panel / dialog / tooltip surface: flat fill, 1px accent_dim border, square, glow outside."""
    s = Sheet(p)
    s.nine("", 4, fill=(p.h(bg), alpha), line=(p.h("accent_dim"), 0.8), margin=margin)
    s.nine("mask", 4, fill=("#000000", 1.0))
    if glow:
        s.glow("shadow", p.h("accent"))
    return s.doc()


def viewitem_svg(p: Pal):
    s = Sheet(p)
    a = p.h("accent")
    s.nine("normal", 1)
    s.nine("hover", 1, fill=(a, 0.08))
    s.nine("selected", 1, fill=(a, 0.35), line=(a, 1.0))
    s.nine("selected+hover", 1, fill=(a, 0.45), line=(a, 1.0))
    return s.doc()


def tasks_svg(p: Pal):
    s = Sheet(p)
    a, w, d = p.h("accent"), p.h("warn"), p.h("accent_dim")
    side_of = {"": "bottom", "north": "top", "west": "left", "east": "right", "south": "bottom"}
    for loc, side in side_of.items():
        pre = (loc + "-") if loc else ""
        s.nine(pre + "normal", 2, margin=2)
        s.nine(pre + "hover", 2, fill=(a, 0.08), line=(a, 0.5), line_w=2, line_sides=(side,))
        s.nine(pre + "focus", 2, fill=(a, 0.16), line=(a, 1.0), line_w=2, line_sides=(side,))
        s.nine(pre + "attention", 2, fill=(w, 0.16), line=(w, 1.0), line_w=2, line_sides=(side,))
        s.nine(pre + "minimized", 2, line=(d, 0.8), line_w=2, line_sides=(side,))
        s.nine(pre + "progress", 2, fill=(a, 0.10))
    return s.doc()


def plasmoidheading_svg(p: Pal):
    s = Sheet(p)
    s.nine("header", 1, fill=(p.h("bg_deep"), 0.5), line=(p.h("accent_dim"), 0.8), line_sides=("bottom",), margin=6)
    s.nine("footer", 1, fill=(p.h("bg_deep"), 0.5), line=(p.h("accent_dim"), 0.8), line_sides=("top",))
    return s.doc()


def frame_svg(p: Pal):
    s = Sheet(p)
    d = p.h("accent_dim")
    s.nine("plain", 2, line=(d, 0.5), margin=4)
    s.nine("sunken", 2, fill=(p.h("bg_deep"), 0.5), line=(d, 0.5), margin=4)
    s.nine("raised", 2, fill=(p.h("bg_panel"), 0.4), line=(d, 0.5), margin=4)
    return s.doc()


def lineedit_svg(p: Pal):
    s = Sheet(p)
    a, d = p.h("accent"), p.h("accent_dim")
    s.nine("base", 2, fill=(d, 0.28), line=(a, 0.25), margin=4)
    s.nine("hover", 2, fill=(d, 0.28), line=(a, 0.60), margin=4)
    s.nine("focus", 2, fill=(d, 0.28), line=(a, 1.00), margin=4)
    s.nine("focusframe", 2, line=(a, 0.60), margin=4)
    s.raw("hint-focus-over-base", 4, 4, el_rect(0, 0, 4, 4, "#ff00ff", 1))
    return s.doc()


def button_svg(p: Pal):
    s = Sheet(p)
    a, d = p.h("accent"), p.h("accent_dim")
    s.nine("normal", 3, fill=(d, 0.28), line=(a, 0.25), margin=6)
    s.nine("hover", 3, fill=(d, 0.28), line=(a, 0.60), margin=6)
    s.nine("focus", 3, line=(a, 1.00), margin=6)
    s.nine("pressed", 3, fill=(a, 0.35), line=(a, 1.00), margin=6)
    s.nine("toolbutton-hover", 3, fill=(a, 0.12), line=(a, 0.30), margin=4)
    s.nine("toolbutton-focus", 3, line=(a, 1.00), margin=4)
    s.nine("toolbutton-pressed", 3, fill=(a, 0.25), line=(a, 0.60), margin=4)
    s.nine("shadow", 3, margin=0)
    s.nine("mask-normal", 3, fill=("#000000", 1.0))
    return s.doc()


def tabbar_svg(p: Pal):
    s = Sheet(p)
    a = p.h("accent")
    for loc, side in (("north", "bottom"), ("south", "top"), ("west", "right"), ("east", "left")):
        s.nine(f"{loc}-active-tab", 2, fill=(a, 0.13), line=(a, 1.0), line_w=2, line_sides=(side,), margin=4)
    return s.doc()


def line_svg(p: Pal):
    s = Sheet(p)
    d = p.h("accent_dim")
    s.raw("vertical-line", 1, 16, el_rect(0, 0, 1, 16, d, 0.6))
    s.raw("horizontal-line", 16, 1, el_rect(0, 0, 16, 1, d, 0.6))
    return s.doc()


def build_desktoptheme(p: Pal, out: Path):
    meta = {
        "KPackageStructure": "Plasma/Theme",
        "KPlugin": {
            "Authors": [{"Name": AUTHOR}],
            "Category": "Plasma Theme",
            "Description": f"FUI ({p.Name}) - dark ground, one glowing accent, thin lines, square corners",
            "EnabledByDefault": True,
            "Id": p.plasma_id,
            "License": "GPL-2.0-or-later",
            "Name": p.scheme_name,
            "Version": VERSION,
        },
    }
    write(out / "metadata.json", json.dumps(meta, indent=4, ensure_ascii=False) + "\n")
    write(out / "colors", colors_file(p))
    write(out / "plasmarc", f"""[Wallpaper]
defaultWallpaperTheme={p.wallpaper_id}
defaultFileSuffix=.png
defaultWidth=3840
defaultHeight=2160

[AdaptiveTransparency]
enabled=true

[ContrastEffect]
enabled=false

[BlurBehindEffect]
enabled=false
""")
    # surfaces: default / opaque / translucent / solid
    # Popups sit on the desktop ground, so even the "translucent" variant keeps alpha 0.92:
    # without blur (style rule) a 0.78 ground lets page text show through notifications.
    variants = {"": BG_ALPHA, "opaque": 1.0, "translucent": BG_ALPHA, "solid": 1.0}
    for sub, alpha in variants.items():
        base = out / sub if sub else out
        write(base / "widgets/panel-background.svg", surface_svg(p, alpha, 4))
        write(base / "dialogs/background.svg", surface_svg(p, alpha, 6))
        write(base / "widgets/tooltip.svg", surface_svg(p, alpha, 6))
        if sub != "opaque":
            write(base / "widgets/background.svg", surface_svg(p, alpha, 8))
    write(out / "widgets/translucentbackground.svg", surface_svg(p, PANEL_ALPHA, 8, bg="bg_panel"))
    write(out / "widgets/viewitem.svg", viewitem_svg(p))
    write(out / "widgets/tasks.svg", tasks_svg(p))
    write(out / "widgets/plasmoidheading.svg", plasmoidheading_svg(p))
    write(out / "widgets/frame.svg", frame_svg(p))
    write(out / "widgets/lineedit.svg", lineedit_svg(p))
    write(out / "widgets/button.svg", button_svg(p))
    write(out / "widgets/tabbar.svg", tabbar_svg(p))
    write(out / "widgets/line.svg", line_svg(p))


# --------------------------------------------------------------------------- Aurorae decoration
PAD = 0       # region outside the frame (becomes the KWin shadow). 0 = no glow, no shadow: the frame is the 1px line only.
              # (A 10px glow was tried; the user preferred no halo around windows.)
LINE = 1      # frame line
TITLE_EDGE = 6
TITLE_H = 24
BTN_W, BTN_H = 28, 24
TOP = TITLE_EDGE + TITLE_H + TITLE_EDGE   # 36 = border top


def deco_frame(s: Sheet, prefix, line, inner_line, glow_layers, bg_alpha=BG_ALPHA, center=32):
    """Window shell: [glow PAD][line 1][title bar bg][accent_dim underline] / sides = glow + line."""
    p = s.pal
    P, L = PAD, LINE
    side = P + L
    top = P + TOP
    bg = p.h("bg_deep")
    lc, la = line
    ic, ia = inner_line

    def bands(name, w, h):
        inner = ""
        for ext, a in (reversed(glow_layers) if P > 0 else ()):
            e = min(ext, P)
            g = p.h("accent")
            if name == "top":
                inner += el_rect(0, P - e, w, e, g, a)
            elif name == "bottom":
                inner += el_rect(0, L, w, e, g, a)
            elif name == "left":
                inner += el_rect(P - e, 0, e, h, g, a)
            elif name == "right":
                inner += el_rect(L, 0, e, h, g, a)
            elif name == "topleft":
                inner += el_rect(P - e, P - e, e, e, g, a)          # corner
                inner += el_rect(P - e, P, e, h - P, g, a)          # left band
                inner += el_rect(P, P - e, w - P, e, g, a)          # top band
            elif name == "topright":
                inner += el_rect(L, P - e, e, e, g, a)
                inner += el_rect(L, P, e, h - P, g, a)
                inner += el_rect(0, P - e, L, e, g, a)
            elif name == "bottomleft":
                inner += el_rect(P - e, L, e, e, g, a)
                inner += el_rect(P - e, 0, e, L, g, a)
                inner += el_rect(P, L, w - P, e, g, a)
            elif name == "bottomright":
                inner += el_rect(L, L, e, e, g, a)
                inner += el_rect(L, 0, e, L, g, a)
                inner += el_rect(0, L, L, e, g, a)
        return inner

    geo = {
        "topleft": (0, 0, side, top), "top": (side, 0, center, top), "topright": (side + center, 0, side, top),
        "left": (0, top, side, center), "center": (side, top, center, center), "right": (side + center, top, side, center),
        "bottomleft": (0, top + center, side, side), "bottom": (side, top + center, center, side),
        "bottomright": (side + center, top + center, side, side),
    }
    for name, (x, y, w, h) in geo.items():
        inner = el_rect(0, 0, w, h, "#000000", 0.0) + bands(name, w, h)
        # Everything inside the line is ground colour. KWin's border size setting (Normal = 4px)
        # can make the frame wider than the 1px line; FrameSvg fills that extra width from the
        # centre cell, so the centre must be opaque ground or the gap shows the window behind.
        # The side/bottom cells are [padding][line] only: never paint ground there, it is the shadow area.
        if name == "center":
            inner += el_rect(0, 0, w, h, bg, bg_alpha)
        if name == "top":
            inner += el_rect(0, P, w, L, lc, la)
            inner += el_rect(0, P + L, w, TOP - L - L, bg, bg_alpha)
            inner += el_rect(0, P + TOP - L, w, L, ic, ia)
        elif name == "topleft":
            inner += el_rect(P, P, w - P, L, lc, la)
            inner += el_rect(P, P, L, h - P, lc, la)
        elif name == "topright":
            inner += el_rect(0, P, L, L, lc, la)
            inner += el_rect(0, P, L, h - P, lc, la)
        elif name == "left":
            inner += el_rect(P, 0, L, h, lc, la)
        elif name == "right":
            inner += el_rect(0, 0, L, h, lc, la)
        elif name == "bottom":
            inner += el_rect(0, 0, w, L, lc, la)
        elif name == "bottomleft":
            inner += el_rect(P, 0, L, L, lc, la)
        elif name == "bottomright":
            inner += el_rect(0, 0, L, L, lc, la)
        s.out.append(el_group(f"{prefix}-{name}", x, s.y + y, inner))
    s._advance(2 * side + center, top + center + side)


def decoration_svg(p: Pal):
    s = Sheet(p)
    a, d = p.h("accent"), p.h("accent_dim")
    deco_frame(s, "decoration", line=(a, 1.0), inner_line=(d, 1.0), glow_layers=GLOW)
    deco_frame(s, "decoration-inactive", line=(d, 0.8), inner_line=(d, 0.5), glow_layers=())
    bg = p.h("bg_deep")
    s.raw("decoration-maximized-center", 32, TOP,
          el_rect(0, 0, 32, TOP, bg, BG_ALPHA) + el_rect(0, TOP - 1, 32, 1, d, 1.0))
    s.raw("decoration-maximized-inactive-center", 32, TOP,
          el_rect(0, 0, 32, TOP, bg, BG_ALPHA) + el_rect(0, TOP - 1, 32, 1, d, 0.5))
    return s.doc()


# Button glyphs: 1.5px lines, no fills, inside a 10px box centred in 28x24.
GLYPHS = {
    "close": 'M9,7 L19,17 M19,7 L9,17',
    "maximize": 'M9.5,7.5 H18.5 V16.5 H9.5 Z',
    "restore": 'M9.5,9.5 H16.5 V16.5 H9.5 Z M11.5,9.5 V7.5 H18.5 V14.5 H16.5',
    "minimize": 'M9,12.5 H19',
    "keepabove": 'M9,15 L14,10 L19,15',
    "keepbelow": 'M9,9 L14,14 L19,9',
    "shade": 'M9,7.5 H19 M9,16 L14,11 L19,16',
    "alldesktops": 'M9.5,7.5 H13 V11 H9.5 Z M15,7.5 H18.5 V11 H15 Z M9.5,13 H13 V16.5 H9.5 Z M15,13 H18.5 V16.5 H15 Z',
    "help": 'M10.5,9.5 A3.5,3.5 0 1 1 14,13 V14.5 M14,16.5 V17.5',
    "appmenu": 'M9,8 H19 M9,12 H19 M9,16 H19',
}


def button_file(p: Pal, name: str) -> str:
    glyph = GLYPHS[name]
    fg = p.h("danger") if name == "close" else p.h("accent")
    dim = p.h("text_dim")
    states = {
        "active": (None, fg, 1.0),
        "hover": ((fg, 0.22), fg, 1.0),
        "pressed": ((fg, 0.40), fg, 1.0),
        "deactivated": (None, fg, 0.30),
        "inactive": (None, dim, 1.0),
        "hover-inactive": ((fg, 0.22), fg, 1.0),
        "pressed-inactive": ((fg, 0.40), fg, 1.0),
        "deactivated-inactive": (None, dim, 0.30),
    }
    out = []
    y = 0
    for st, (bg, color, alpha) in states.items():
        inner = el_rect(0, 0, BTN_W, BTN_H, "#000000", 0.0)
        if bg:
            inner += el_rect(0, 0, BTN_W, BTN_H, bg[0], bg[1])
        inner += (f'<path d="{glyph}" style="fill:none;stroke:{color};stroke-opacity:{alpha};'
                  'stroke-width:1.5;stroke-linecap:butt;stroke-linejoin:miter"/>')
        out.append(el_group(f"{st}-center", 0, y, inner))
        y += BTN_H + 4
    return svg_doc(BTN_W, y, "\n".join(out))


def build_aurorae(p: Pal, out: Path):
    write(out / "metadata.desktop", f"""[Desktop Entry]
Name={p.scheme_name}
Comment=FUI window decoration ({p.Name}): square, 1px accent frame, 4-layer glow, no shadow
X-KDE-PluginInfo-Author={AUTHOR}
X-KDE-PluginInfo-Name={p.aurorae_id}
X-KDE-PluginInfo-Version={VERSION}
X-KDE-PluginInfo-License=GPL-2.0-or-later
""")
    write(out / f"{p.aurorae_id}rc", f"""[General]
TitleAlignment=Left
TitleVerticalAlignment=Center
Animation=120
ActiveTextColor={kde(p.accent)}
InactiveTextColor={kde(p.text_dim)}
UseTextShadow=0
ButtonsLeft=
ButtonsRight=IAX
Shadow=true

[Layout]
BorderLeft={LINE}
BorderRight={LINE}
BorderBottom={LINE}
TitleEdgeTop={TITLE_EDGE}
TitleEdgeBottom={TITLE_EDGE}
TitleEdgeLeft=14
TitleEdgeRight=8
TitleEdgeTopMaximized={TITLE_EDGE}
TitleEdgeBottomMaximized={TITLE_EDGE}
TitleEdgeLeftMaximized=14
TitleEdgeRightMaximized=8
TitleBorderLeft=6
TitleBorderRight=6
TitleHeight={TITLE_H}
ButtonWidth={BTN_W}
ButtonHeight={BTN_H}
ButtonSpacing=6
ButtonMarginTop=0
ExplicitButtonSpacer=8
PaddingTop={PAD}
PaddingBottom={PAD}
PaddingLeft={PAD}
PaddingRight={PAD}
""")
    write(out / "decoration.svg", decoration_svg(p))
    for name in GLYPHS:
        write(out / f"{name}.svg", button_file(p, name))


# --------------------------------------------------------------------------- wallpaper
def wallpaper_svg(p: Pal, w=3840, h=2160):
    d = p.h("accent_dim")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <pattern id="minor" width="48" height="48" patternUnits="userSpaceOnUse">
    <path d="M48,0 H0 V48" style="fill:none;stroke:{d};stroke-width:1;stroke-opacity:0.10"/>
  </pattern>
  <pattern id="major" width="240" height="240" patternUnits="userSpaceOnUse">
    <path d="M240,0 H0 V240" style="fill:none;stroke:{d};stroke-width:1;stroke-opacity:0.22"/>
  </pattern>
  <pattern id="scan" width="1" height="3" patternUnits="userSpaceOnUse">
    <rect y="2" width="1" height="1" style="fill:#000000;fill-opacity:0.10"/>
  </pattern>
</defs>
<rect width="{w}" height="{h}" style="fill:{p.h('bg_deep')}"/>
<rect width="{w}" height="{h}" style="fill:url(#minor)"/>
<rect width="{w}" height="{h}" style="fill:url(#major)"/>
<rect width="{w}" height="{h}" style="fill:url(#scan)"/>
</svg>
"""


def rsvg(svg: Path, png: Path, width: int | None = None, height: int | None = None):
    if not shutil.which("rsvg-convert"):
        print(f"  ! rsvg-convert not found, skipping {png.name}")
        return
    cmd = ["rsvg-convert", "-o", str(png)]
    if width:
        cmd += ["-w", str(width)]
    if height:
        cmd += ["-h", str(height)]
    cmd.append(str(svg))
    subprocess.run(cmd, check=True)


def build_wallpaper(p: Pal, out: Path):
    meta = {
        "KPlugin": {
            "Authors": [{"Name": AUTHOR}],
            "Id": p.wallpaper_id,
            "License": "CC0-1.0",
            "Name": f"FUI {p.Name} Grid",
        },
    }
    write(out / "metadata.json", json.dumps(meta, indent=4) + "\n")
    svg = out / "contents/source.svg"
    write(svg, wallpaper_svg(p))
    img = out / "contents/images"
    img.mkdir(parents=True, exist_ok=True)
    rsvg(svg, img / "3840x2160.png")
    rsvg(svg, img / "2560x1440.png", 2560, 1440)
    rsvg(svg, out / "contents/screenshot.png", 400, 225)


# --------------------------------------------------------------------------- fonts (kdeglobals strings)
def qfont_string(family: str, size: float, weight=400, upper=False, tracking_pct=0, style_name="") -> str:
    try:
        from PyQt6.QtGui import QFont  # type: ignore
        f = QFont(family)
        f.setPointSizeF(size)
        f.setWeight(QFont.Weight(weight))
        if upper:
            f.setCapitalization(QFont.Capitalization.AllUppercase)
        if tracking_pct:
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100 + tracking_pct)
        if style_name:
            f.setStyleName(style_name)
        return f.toString()
    except Exception:
        cap = 1 if upper else 0
        ls = (100 + tracking_pct) if tracking_pct else 0
        return f"{family},{size:g},-1,5,{weight},0,0,0,0,0,{cap},0,{ls},0,0,1,{style_name},0,0"


def font_settings() -> dict:
    """kdeglobals font keys. An empty value means 'system default' (apply.sh restores the backup or deletes the key)."""
    ui = {
        "font": qfont_string(*FONT_GENERAL),
        "fixed": qfont_string(*FONT_FIXED),
        "smallestReadableFont": qfont_string(*FONT_SMALL),
        "toolBarFont": qfont_string(*FONT_GENERAL),
        "menuFont": qfont_string(*FONT_GENERAL),
    } if USE_FUI_MONO else {k: "" for k in ("font", "fixed", "smallestReadableFont", "toolBarFont", "menuFont")}
    ui["activeFont"] = qfont_string(*FONT_TITLE, weight=600, upper=True, tracking_pct=12, style_name="SemiBold")
    return ui


# --------------------------------------------------------------------------- look-and-feel
def preview_svg(p: Pal, w=1280, h=720):
    a, d, t, td = p.h("accent"), p.h("accent_dim"), p.h("text"), p.h("text_dim")
    bg = p.h("bg_deep")
    glow = "".join(
        f'<rect x="{240 - e:g}" y="{120 - e:g}" width="{800 + 2 * e:g}" height="{440 + 2 * e:g}" '
        f'style="fill:none;stroke:{a};stroke-opacity:{al};stroke-width:{2 * e:g}"/>'
        for e, al in reversed(GLOW))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <pattern id="minor" width="48" height="48" patternUnits="userSpaceOnUse">
    <path d="M48,0 H0 V48" style="fill:none;stroke:{d};stroke-width:1;stroke-opacity:0.10"/></pattern>
  <pattern id="major" width="240" height="240" patternUnits="userSpaceOnUse">
    <path d="M240,0 H0 V240" style="fill:none;stroke:{d};stroke-width:1;stroke-opacity:0.22"/></pattern>
  <pattern id="scan" width="1" height="3" patternUnits="userSpaceOnUse">
    <rect y="2" width="1" height="1" style="fill:#000000;fill-opacity:0.10"/></pattern>
</defs>
<rect width="{w}" height="{h}" style="fill:{bg}"/>
<rect width="{w}" height="{h}" style="fill:url(#minor)"/>
<rect width="{w}" height="{h}" style="fill:url(#major)"/>
<!-- window -->
{glow}
<rect x="240" y="120" width="800" height="440" style="fill:{bg};fill-opacity:{BG_ALPHA};stroke:{a};stroke-width:1.4"/>
<line x1="240.5" y1="156.5" x2="1039.5" y2="156.5" style="stroke:{d};stroke-width:1"/>
<text x="254" y="144" style="font-family:Orbitron,sans-serif;font-weight:600;font-size:14px;letter-spacing:0.12em;fill:{a}">SYSTEM // CONSOLE</text>
<path d="M990,132 H1000 M1010,132.5 H1019 V141.5 H1010 Z M1024,132 L1034,142 M1034,132 L1024,142" style="fill:none;stroke:{a};stroke-width:1.5"/>
<path d="M1024,132 L1034,142 M1034,132 L1024,142" style="fill:none;stroke:{p.h('danger')};stroke-width:1.5"/>
<rect x="254" y="172" width="180" height="24" style="fill:{a};fill-opacity:0.13;stroke:{a};stroke-width:1"/>
<rect x="254" y="172" width="3" height="24" style="fill:{a}"/>
<text x="272" y="189" style="font-family:Orbitron,sans-serif;font-size:11px;letter-spacing:0.12em;fill:{a}">TELEMETRY</text>
<rect x="254" y="204" width="180" height="24" style="fill:{bg};fill-opacity:0.5;stroke:{a};stroke-opacity:0.22;stroke-width:1"/>
<rect x="254" y="204" width="3" height="24" style="fill:{d};fill-opacity:0.4"/>
<text x="272" y="221" style="font-family:Orbitron,sans-serif;font-size:11px;letter-spacing:0.12em;fill:{t};fill-opacity:0.8">MODULES</text>
<rect x="450" y="172" width="574" height="300" style="fill:{p.h('bg_panel')};fill-opacity:{PANEL_ALPHA};stroke:{d};stroke-opacity:0.8;stroke-width:1"/>
<rect x="464" y="164" width="96" height="16" style="fill:{bg};stroke:{d};stroke-width:1"/>
<text x="473" y="176" style="font-family:'Share Tech Mono',monospace;font-size:11px;fill:{a}">LINK STATUS</text>
<g style="font-family:'Share Tech Mono',monospace;font-size:13px;fill:{td}">
<text x="466" y="206">[T+00:12:34.5]</text><text x="590" y="206" style="fill:{t}">MODEL SYNC VERIFIED</text>
<text x="466" y="228">[T+00:12:31.2]</text><text x="590" y="228" style="fill:{p.h('ok')}">LINK SECURE :: 4 CONTACTS</text>
<text x="466" y="250">[T+00:12:20.9]</text><text x="590" y="250" style="fill:{p.h('warn')}">DRIFT 0.8 mm :: THRESHOLD 0.5</text>
</g>
{"".join(f'<rect x="{466 + i * 9}" y="290" width="7" height="12" style="fill:{a};fill-opacity:{0.25 + 0.75 * i / 17:.2f}"/>' if i / 17 <= 0.72 else f'<rect x="{466 + i * 9}" y="290" width="7" height="12" style="fill:{d};fill-opacity:0.15"/>' for i in range(18))}
<text x="640" y="301" style="font-family:'Share Tech Mono',monospace;font-size:13px;fill:{t}"> 72.0 %</text>
<text x="700" y="301" style="font-family:'Share Tech Mono',monospace;font-size:11px;fill:{td}">POWER</text>
<!-- panel -->
<rect x="0" y="676" width="{w}" height="44" style="fill:{bg};fill-opacity:{BG_ALPHA}"/>
<line x1="0" y1="676.5" x2="{w}" y2="676.5" style="stroke:{d};stroke-width:1"/>
<rect x="120" y="684" width="120" height="28" style="fill:{a};fill-opacity:0.16"/>
<rect x="120" y="710" width="120" height="2" style="fill:{a}"/>
<rect x="250" y="684" width="120" height="28" style="fill:none"/>
<rect x="250" y="710" width="120" height="2" style="fill:{d};fill-opacity:0.8"/>
<text x="{w - 24}" y="703" text-anchor="end" style="font-family:'Share Tech Mono',monospace;font-size:14px;fill:{t}">12:34</text>
</svg>
"""


def build_lnf(p: Pal, out: Path):
    meta = {
        "KPackageStructure": "Plasma/LookAndFeel",
        "KPlugin": {
            "Authors": [{"Name": AUTHOR}],
            "Category": "",
            "Description": f"FUI {p.Name}: colours, Plasma theme, Aurorae decoration, fonts, wallpaper",
            "Id": p.lnf_id,
            "License": "GPL-2.0-or-later",
            "Name": p.scheme_name,
            "Version": VERSION,
        },
    }
    write(out / "metadata.json", json.dumps(meta, indent=4) + "\n")
    f = font_settings()
    ui_fonts = "".join(f"{k}={v}\n" for k, v in f.items() if k != "activeFont" and v)
    write(out / "contents/defaults", f"""[kdeglobals][KDE]
widgetStyle=Breeze

[kdeglobals][General]
ColorScheme={p.scheme_id}
{ui_fonts}
[kdeglobals][WM]
activeFont={f['activeFont']}

[kdeglobals][Icons]
Theme=breeze-dark

[plasmarc][Theme]
name={p.plasma_id}

[Wallpaper]
Image={p.wallpaper_id}

[kcminputrc][Mouse]
cursorTheme=breeze_cursors

[kwinrc][org.kde.kdecoration2]
library=org.kde.kwin.aurorae
theme=__aurorae__svg__{p.aurorae_id}
""")
    # KCM look-and-feel: thumbnail = previews/preview.png, full preview = previews/fullscreenpreview.jpg (JPEG, by name).
    svg = out / "contents/previews/preview.svg"
    write(svg, preview_svg(p))
    rsvg(svg, out / "contents/previews/preview.png")
    full_png = out / "contents/previews/fullscreenpreview.png"
    rsvg(svg, full_png, 1920, 1080)
    svg.unlink()
    try:
        from PIL import Image  # type: ignore
        Image.open(full_png).convert("RGB").save(out / "contents/previews/fullscreenpreview.jpg", quality=90)
        full_png.unlink()
    except Exception as e:
        print(f"  ! could not write fullscreenpreview.jpg ({e}); the KCM will show the default preview")


# --------------------------------------------------------------------------- terminals
def term_palette(p: Pal):
    lite = lambda c: mix(c, p.white, 0.3)  # noqa: E731
    base = [p.bg_panel, p.danger, p.ok, p.warn, p.term_blue, p.term_magenta, p.term_cyan, p.text]
    bright = [p.text_dim] + [lite(c) for c in base[1:]]
    return base + bright


def konsole_file(p: Pal) -> str:
    cols = term_palette(p)
    lines = [f"[Background]\nColor={kde(p.bg_deep)}\n",
             f"[BackgroundFaint]\nColor={kde(p.bg_deep)}\n",
             f"[BackgroundIntense]\nColor={kde(p.bg_panel)}\n",
             f"[Foreground]\nColor={kde(p.text)}\n",
             f"[ForegroundFaint]\nColor={kde(p.text_dim)}\n",
             f"[ForegroundIntense]\nColor={kde(mix(p.text, p.white, 0.3))}\n"]
    for i in range(8):
        lines.append(f"[Color{i}]\nColor={kde(cols[i])}\n")
        lines.append(f"[Color{i}Intense]\nColor={kde(cols[8 + i])}\n")
        lines.append(f"[Color{i}Faint]\nColor={kde(mix(cols[i], p.bg_deep, 0.4))}\n")
    lines.append(f"[General]\nAnchor=0.5,0.5\nBlur=false\nColorRandomization=false\n"
                 f"Description={p.scheme_name}\nFillStyle=Tile\nOpacity={BG_ALPHA}\nWallpaper=\nWallpaperOpacity=1\n")
    return "\n".join(lines)


def ghostty_file(p: Pal) -> str:
    cols = term_palette(p)
    out = [f"# {p.scheme_name} -- generated by kde-fui-theme"]
    out += [f"palette = {i}={hexs(c)}" for i, c in enumerate(cols)]
    out += [
        f"background = {p.h('bg_deep')}",
        f"foreground = {p.h('text')}",
        f"cursor-color = {p.h('accent')}",
        f"cursor-text = {p.h('bg_deep')}",
        f"selection-background = {hexs(p.sel_bg)}",
        f"selection-foreground = {p.h('text')}",
    ]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- derived UI font
def cjk_metrics_em() -> tuple[float, float]:
    """(ascent, descent) of the CJK fallback in em, read from the installed TTC. Defaults to Noto CJK's hhea values."""
    try:
        from fontTools.ttLib import TTCollection  # type: ignore
        for f in TTCollection(CJK_FALLBACK_TTC).fonts:
            if f["name"].getDebugName(1) == CJK_FALLBACK_FAMILY:
                upm = f["head"].unitsPerEm
                return f["hhea"].ascent / upm, -f["hhea"].descent / upm
    except Exception:
        pass
    return 1.160, 0.288


def make_fui_mono(src: Path, dst: Path):
    """Share Tech Mono -> FUI Mono: same glyphs, hhea/OS2 vertical metrics set to the CJK fallback's.

    Qt sizes a text line by the tallest font in it, so a Latin font with a small ascent sits several px
    lower whenever a Japanese glyph shares the line (Dolphin's date column, mixed menus). Matching the
    metrics removes the jump. Renamed because the OFL reserves the name 'Share'.
    """
    from fontTools.ttLib import TTFont  # type: ignore
    asc_em, desc_em = cjk_metrics_em()
    f = TTFont(src)
    upm = f["head"].unitsPerEm
    asc, desc = round(asc_em * upm), round(desc_em * upm)
    f["hhea"].ascent, f["hhea"].descent, f["hhea"].lineGap = asc, -desc, 0
    os2 = f["OS/2"]
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = asc, -desc, 0
    os2.usWinAscent, os2.usWinDescent = asc, desc
    os2.fsSelection |= 1 << 7          # USE_TYPO_METRICS
    # Tracking: widen every cell to MONO_ADVANCE_EM and centre the glyph in it. Done in the font so GTK,
    # Chrome and Plasma QML get the same spacing (QFont letterSpacing only reaches Qt widgets).
    glyf, hmtx = f["glyf"], f["hmtx"]
    order = f.getGlyphOrder()
    base_adv = hmtx[f.getBestCmap()[ord("a")]][0]
    delta = round(MONO_ADVANCE_EM * upm) - base_adv
    shift = delta // 2
    if delta > 0:
        for gname in order:                      # simple glyphs first, composites inherit the shift
            g = glyf[gname]
            if not g.isComposite() and g.numberOfContours > 0:
                g.coordinates.translate((shift, 0))
                g.recalcBounds(glyf)
        for gname in order:
            g = glyf[gname]
            if g.isComposite():
                g.recalcBounds(glyf)
            adv, lsb = hmtx[gname]
            hmtx[gname] = (adv + delta if adv > 0 else adv, lsb + shift if adv > 0 else lsb)
        os2.xAvgCharWidth = round(MONO_ADVANCE_EM * upm)
    family, full, ps = "FUI Mono", "FUI Mono", "FUIMono-Regular"
    name = f["name"]
    for rec in name.names:
        nid = rec.nameID
        if nid in (1, 16):
            rec.string = family
        elif nid == 3:
            rec.string = f"{full};kde-fui-theme;metrics matched to {CJK_FALLBACK_FAMILY}"
        elif nid == 4:
            rec.string = full
        elif nid == 6:
            rec.string = ps
        elif nid == 0:
            rec.string = rec.toUnicode() + " Modified by kobago (kde-fui-theme): vertical metrics only."
    dst.parent.mkdir(parents=True, exist_ok=True)
    f.save(dst)
    print(f"  FUI Mono: ascent {asc}/{upm} descent {desc}/{upm} (from {CJK_FALLBACK_FAMILY}), "
          f"advance {base_adv} -> {base_adv + max(delta, 0)}/{upm}")


# --------------------------------------------------------------------------- main
def build(p: Pal):
    print(f"== {p.scheme_name}")
    write(DIST / "color-schemes" / f"{p.scheme_id}.colors", colors_file(p))
    build_desktoptheme(p, DIST / "plasma/desktoptheme" / p.plasma_id)
    build_aurorae(p, DIST / "aurorae/themes" / p.aurorae_id)
    build_wallpaper(p, DIST / "wallpapers" / p.wallpaper_id)
    build_lnf(p, DIST / "plasma/look-and-feel" / p.lnf_id)
    write(DIST / "konsole" / f"{p.scheme_id}.colorscheme", konsole_file(p))
    write(DIST / "ghostty" / p.plasma_id, ghostty_file(p))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    make_fui_mono(ROOT / "fonts/ShareTechMono-Regular.ttf", DIST / "fonts/FUIMono-Regular.ttf")
    shutil.copy(ROOT / "fonts/OFL-ShareTechMono.txt", DIST / "fonts/OFL-FUIMono.txt")
    for key, d in PALETTES.items():
        build(Pal(key, d))
    write(DIST / "fonts.ini", "\n".join(f"{k}={v}" for k, v in font_settings().items()) + "\n")
    print(f"done -> {DIST}")


if __name__ == "__main__":
    main()
