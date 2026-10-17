"""Render data.js to tools/preview.svg with a label at every target's anchor, for eye-checking.

Usage:
    .venv/bin/python tools/preview.py [rivers|seas|ranges ...]   # label only these decks (default: all)
    sips -s format png tools/preview.svg --out tools/preview.png   # macOS: rasterise at canvas size
(`qlmanage -t` also works but squares the thumbnail and crops the right of the map.)
"""
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLE = {  # layer: (fill, stroke, stroke-width, label colour)
    'land': ('#EDEDE8', 'none', 0, None),
    'countries': ('none', '#C9C9C2', 0.8, None),
    'lakes': ('#BFD7EA', '#fff', 1, None),
    'seas': ('#9CC3E0', '#fff', 1, '#0B3D6B'),
    'ranges': ('rgba(160,120,80,.45)', '#7A5A3A', 1.2, '#5A3A1A'),
    'rivers': ('none', '#3F7FB5', 3, '#1F4F85'),
}


def main() -> None:
    decks = sys.argv[1:] or ['seas', 'ranges', 'rivers']
    src = (ROOT / 'data.js').read_text(encoding='utf-8')
    eu = json.loads(src[src.index('{'):src.rindex(';')])['eu']
    w, h = eu['w'], eu['h']
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="{w}" height="{h}" fill="#DCEAF5"/>']
    for layer, (fill, stroke, sw, _) in STYLE.items():
        dash = ' stroke-dasharray="4 3"' if layer == 'ranges' else ''
        out += [f'<path d="{f["d"]}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>'
                for f in eu[layer]]
    for layer, (*_, colour) in STYLE.items():
        for f in eu[layer] if colour and layer in decks else []:
            x, y, n = f['cx'], f['cy'], escape(f['name'])
            cw = 6 * len(f['name']) + 15  # ~ the game's .chip.name box at 10px Manrope bold
            out.append(f'<rect x="{x - cw / 2:.1f}" y="{y - 8}" width="{cw}" height="16" rx="8" '
                       f'fill="#fff" fill-opacity=".92" stroke="{colour}" stroke-width="1"/>'
                       f'<text x="{x}" y="{y + 3.5}" font-family="Helvetica" font-size="10" '
                       f'font-weight="bold" text-anchor="middle" fill="{colour}">{n}</text>')
    out.append('</svg>')
    (ROOT / 'tools' / 'preview.svg').write_text('\n'.join(out), encoding='utf-8')


if __name__ == '__main__':
    main()
