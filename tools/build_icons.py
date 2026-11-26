"""Download Lucide icons (ISC License) and rasterize them to PNG assets.

This is a development-time tool. It needs `cairosvg` installed, but the app
itself only needs the generated PNG files in `src/assets/icons/`.

Usage (from the repo root):
    python tools/build_icons.py                # regenerate every icon
    python tools/build_icons.py --only-missing # add icons not on disk yet

Lucide: https://github.com/lucide-icons/lucide  (ISC License, see LICENSE file)
"""

import os
import sys
import urllib.request

# cairosvg imports cairocffi, which needs a system Cairo DLL on Windows.
# This project bundles pycairo, so alias it before importing cairosvg.
import cairo  # pycairo
sys.modules['cairocffi'] = cairo
import cairosvg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'src', 'assets', 'icons')
BASE_URL = 'https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{}.svg'

# Logical name -> Lucide icon slug. Keep this in sync with the names passed to
# draw_icon()/draw_button() in src/views so no button renders an empty icon.
ICONS = {
    'undo': 'undo-2',
    'redo': 'redo-2',
    'pen': 'pencil',
    'select': 'mouse-pointer-2',
    'eraser': 'eraser',
    'cutter': 'scissors',
    'bucket': 'paint-bucket',
    'snap': 'magnet',
    'options': 'sliders-horizontal',
    'shape_free': 'spline',
    'shape_line': 'slash',
    'shape_rect': 'rectangle-horizontal',
    'shape_square': 'square',
    'shape_ellipse': 'ellipse',
    'shape_circle': 'circle',
    'shape_triangle': 'triangle',
    'shape_polygon': 'hexagon',
    'shape_star': 'star',
    'elev_front': 'bring-to-front',
    'elev_forward': 'chevrons-up',
    'elev_backward': 'chevrons-down',
    'elev_back': 'send-to-back',
    'union': 'combine',
    'intersect': 'blend',
    'subtract': 'square-minus',
    'exclude': 'square-x',
    'ref_load': 'image-plus',
    'ref_visible': 'eye',
    'ref_hidden': 'eye-off',
    'ref_clear': 'trash',
    'eyedropper': 'pipette',
    'wave_add': 'plus',
    'wave_remove': 'minus',
    'wave_apply': 'check',
    'wave': 'audio-waveform',
    'boost': 'zap',
    'curve_redraw': 'rotate-ccw',
    'curve_hide': 'eye-off',
    'curve_show': 'eye',
    'save': 'save',
    'open': 'folder-open',
    'import': 'import',
    'export': 'download',
    'copy': 'copy',
    'move': 'move',
    'text': 'type',
    'displacement_add': 'move-diagonal',
    'repeat_add': 'repeat-2',
    'thickness_add': 'ruler',
    'flip_h': None,  # custom SVG below (Lucide has no flip icons)
    'flip_v': None,
    'align_left': 'align-start-horizontal',
    'align_hcenter': 'align-center-horizontal',
    'align_right': 'align-end-horizontal',
    'align_top': 'align-start-vertical',
    'align_vmiddle': 'align-center-vertical',
    'align_bottom': 'align-end-vertical',
}

# Lucide has no flip glyphs, so these are drawn locally in the same style.
CUSTOM_SVG = {
    'flip_h': '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3v18"/>
        <path d="M9 7 3 12l6 5z" fill="currentColor" stroke="none"/>
        <path d="M15 7 21 12l-6 5z" fill="currentColor" stroke="none"/>
    </svg>''',
    'flip_v': '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12h18"/>
        <path d="M7 9 12 3l5 6z" fill="currentColor" stroke="none"/>
        <path d="M7 15 12 21l5-6z" fill="currentColor" stroke="none"/>
    </svg>''',
}

SIZES = (20, 24)


def main():
    only_missing = '--only-missing' in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    for logical, slug in ICONS.items():
        paths = [os.path.join(OUT_DIR, f'{logical}_{size}.png') for size in SIZES]
        if only_missing and all(os.path.exists(path) for path in paths):
            continue
        if logical in CUSTOM_SVG:
            svg = CUSTOM_SVG[logical]
        else:
            try:
                with urllib.request.urlopen(BASE_URL.format(slug), timeout=20) as resp:
                    svg = resp.read().decode('utf-8')
            except Exception as exc:
                print(f'  FAILED {logical} ({slug}): {exc}')
                continue
        # Lucide uses stroke="currentColor"; bake in white so the PNG can be
        # tinted to any colour at runtime with BLEND_RGBA_MULT.
        svg = svg.replace('currentColor', '#ffffff')
        for size, path in zip(SIZES, paths):
            png = cairosvg.svg2png(
                bytestring=svg.encode('utf-8'),
                output_width=size,
                output_height=size,
            )
            with open(path, 'wb') as fh:
                fh.write(png)
        print(f'  built {logical} ({slug or "custom"})')


if __name__ == '__main__':
    main()
