"""Generate src/dark.css from index.css + polish.css.

Every rule that sets a color gets a twin under html[data-theme="dark"] with the
color remapped: light neutrals become dark surfaces, dark text becomes light,
pale tints become deep tints, saturated accents stay. Translucent colors
(shadows, scrims, glass over media) are left alone, and components that sit on
photos/video (reels, stories, media controls) are skipped entirely.

Run after changing either stylesheet:  python3 scripts/make_dark_css.py
"""

import colorsys
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
SOURCES = ["index.css", "polish.css"]
OUT = SRC / "dark.css"
PREFIX = 'html[data-theme="dark"]'
COLOR_PROPS = {
    "color", "background", "background-color", "background-image", "border", "border-color",
    "border-top", "border-bottom", "border-left", "border-right", "border-top-color",
    "border-bottom-color", "outline", "outline-color", "fill", "stroke", "caret-color", "scrollbar-color",
}
# Components drawn on top of photos or video keep their light-on-dark look.
SKIP = re.compile(r"reel|story-viewer|story-(?:progress|nav|image|caption|reply|own|viewers|author)|sticker|poll-|inline-video|"
                  r"media-(?:arrow|dots|counter)|like-burst|tile-|post-modal-close|lesson-thumb|path-cover i|shared-post video")
HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
RGB = re.compile(r"rgba?\(([^)]*)\)")


def to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(v * 255))) for v in (r, g, b)))


def remap(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.12 or l > 0.97 or l < 0.03:  # neutral: invert the lightness scale
        stops = [(1.0, 0.0), (0.98, 0.07), (0.95, 0.11), (0.93, 0.15), (0.86, 0.21), (0.78, 0.3),
                 (0.66, 0.55), (0.56, 0.66), (0.45, 0.66), (0.3, 0.86), (0.15, 0.96), (0.0, 1.0)]
        for (l1, d1), (l2, d2) in zip(stops, stops[1:]):
            if l2 <= l <= l1:
                t = (l - l2) / (l1 - l2) if l1 != l2 else 0
                nl = d2 + (d1 - d2) * t
                return to_hex(nl, nl, nl)
    if l > 0.85:  # pale tint -> deep tint of the same hue
        return to_hex(*colorsys.hls_to_rgb(h, 0.17, min(s, 0.45)))
    if l < 0.35:  # dark colored text -> light version
        return to_hex(*colorsys.hls_to_rgb(h, 0.78, min(1.0, s)))
    return None  # saturated mid-tone accent: keep


def swap_colors(value):
    changed = False

    def hex_sub(match):
        nonlocal changed
        digits = match.group(1)
        if len(digits) in (4, 8):
            return match.group(0)  # has alpha: leave
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        r, g, b = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
        new = remap(r, g, b)
        if new is None:
            return match.group(0)
        changed = True
        return new

    def rgb_sub(match):
        nonlocal changed
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) == 4 and float(parts[3]) < 1:
            return match.group(0)  # translucent: leave
        try:
            r, g, b = (float(p) / 255 for p in parts[:3])
        except ValueError:
            return match.group(0)
        new = remap(r, g, b)
        if new is None:
            return match.group(0)
        changed = True
        return new

    value = HEX.sub(hex_sub, value)
    value = RGB.sub(rgb_sub, value)
    for word, dark in (("white", "#000000"), ("black", "#ffffff")):
        if re.search(rf"\b{word}\b", value):
            value = re.sub(rf"\b{word}\b", dark, value)
            changed = True
    return value if changed else None


def has_accent_background(body):
    """True when the rule paints a saturated background (buttons, badges, bubbles)."""

    for declaration in body.split(";"):
        if ":" not in declaration:
            continue
        prop, value = declaration.split(":", 1)
        if prop.strip().lower() not in {"background", "background-color"}:
            continue
        for digits in HEX.findall(value):
            if len(digits) == 3:
                digits = "".join(c * 2 for c in digits)
            if len(digits) != 6:
                continue
            r, g, b = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            if s >= 0.12 and 0.2 < l < 0.85:
                return True
    return False


def rules(css):
    """Yield (media_or_None, selector, body) for plain rules, one level of @media."""

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i = 0
    while i < len(css):
        brace = css.find("{", i)
        if brace == -1:
            return
        head = css[i:brace].strip()
        if head.startswith("@media"):
            depth, j = 1, brace + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
            for _, selector, body in rules(css[brace + 1 : j - 1]):
                yield head, selector, body
            i = j
        elif head.startswith("@"):
            depth, j = 1, brace + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
            i = j  # skip @keyframes / @font-face / @import blocks
        else:
            end = css.find("}", brace)
            yield None, head, css[brace + 1 : end]
            i = end + 1


def prefix_selector(selector):
    parts = []
    for part in selector.split(","):
        part = part.strip()
        if SKIP.search(part):
            continue
        if part in (":root", "html", "body"):
            parts.append(PREFIX if part != "body" else f"{PREFIX} body")
        else:
            parts.append(f"{PREFIX} {part}")
    return ", ".join(parts)


def main():
    out = ["/* Generated by scripts/make_dark_css.py. Do not edit by hand. */",
           f"{PREFIX} {{ color-scheme: dark; }}",
           f"{PREFIX} body {{ background: #000; color: #f5f5f5; }}"]
    for name in SOURCES:
        for media, selector, body in rules((SRC / name).read_text()):
            if selector.startswith("@") or ":root" in selector and "--" in body and "color:" not in body:
                pass
            declarations = []
            on_accent = has_accent_background(body)
            for declaration in body.split(";"):
                if ":" not in declaration:
                    continue
                prop, value = declaration.split(":", 1)
                prop = prop.strip().lower()
                if prop.startswith("--sk-"):
                    new = swap_colors(value)
                elif prop == "color" and on_accent:
                    new = None  # white text on a blue button stays white
                elif prop in COLOR_PROPS:
                    new = swap_colors(value)
                else:
                    new = None
                if new is not None:
                    declarations.append(f"{prop}:{new.strip()}")
            if not declarations:
                continue
            if "data-theme" in selector:
                continue  # hand-written dark rules already in polish.css
            target = prefix_selector(selector)
            if not target:
                continue
            rule = f"{target}{{{';'.join(declarations)}}}"
            out.append(f"{media}{{{rule}}}" if media else rule)
    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT.relative_to(SRC.parent)} ({len(out) - 3} rules)")


if __name__ == "__main__":
    main()
