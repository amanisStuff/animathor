"""Download Lucide icons (ISC License) and rasterize them to PNG assets.

This is a development-time tool. It needs `cairosvg` installed, but the app
itself only needs the generated PNG files in `src/assets/icons/`.

Usage (from the repo root):
    python tools/build_icons.py

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

# Logical name -> Lucide icon slug.
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
    'elev_front': 'bring-to-front',
    'elev_forward': 'chevrons-up',
    'elev_backward': 'chevrons-down',
    'elev_back': 'send-to-back',
    'union': 'combine',
    'intersect': 'blend',
    'ref_load': 'image-plus',
    'ref_visible': 'eye',
    'ref_hidden': 'eye-off',
    'ref_clear': 'trash',
    'eyedropper': 'pipette',
    'wave_add': 'plus',
    'wave_remove': 'minus',
    'wave': 'audio-waveform',
    'boost': 'zap',
    'curve_redraw': 'rotate-ccw',
    'curve_hide': 'eye-off',
    'curve_show': 'eye',
    'save': 'save',
    'open': 'folder-open',
    'export': 'download',
    'copy': 'copy',
    'move': 'move',
}

SIZES = (20, 24)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for logical, slug in ICONS.items():
        url = BASE_URL.format(slug)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                svg = resp.read().decode('utf-8')
        except Exception as exc:
            print(f'  FAILED {logical} ({slug}): {exc}')
            continue
        # Lucide uses stroke="currentColor"; bake in white so the PNG can be
        # tinted to any colour at runtime with BLEND_RGBA_MULT.
        svg = svg.replace('currentColor', '#ffffff')
        for size in SIZES:
            png = cairosvg.svg2png(
                bytestring=svg.encode('utf-8'),
                output_width=size,
                output_height=size,
            )
            path = os.path.join(OUT_DIR, f'{logical}_{size}.png')
            with open(path, 'wb') as fh:
                fh.write(png)
        print(f'  built {logical} ({slug})')


if __name__ == '__main__':
    main()
