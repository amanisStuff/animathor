"""Model: wave distortion styles, evaluation and sampling."""

import math

from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models.geometry as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))

import models.strokes as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))



WAVE_SHAPES = ["sine", "triangle", "square", "sawtooth", "circular", "half_circle", "formula", "custom", "sine_bezier", "noise"]

WAVE_SHAPE_LABELS = [("sine", "Sine"), ("triangle", "Tri"), ("square", "Sq"), ("sawtooth", "Saw"),
                     ("circular", "Circ"), ("half_circle", "Half"), ("formula", "Formula"),
                     ("custom", "Custom"), ("sine_bezier", "Sine Béz"), ("noise", "Noise")]

WAVE_SHAPE_LABEL_DICT = dict(WAVE_SHAPE_LABELS)

DISTORTION_STYLE_TYPES = {"wave", "displacement", "repeat", "thickness"}

DISPLACEMENT_PROFILES = ["flat", "custom"]
DISPLACEMENT_PROFILE_LABELS = [("flat", "Flat"), ("custom", "Custom")]

REPEAT_STYLE_LABEL = "Repeat"
THICKNESS_STYLE_LABEL = "Thickness"


def default_wave_params():
    return {
        "type": "wave",
        "enabled": False,
        "shape": "sine",
        "amplitude": 8.0,
        "frequency": 0.25,
        "phase": 0.0,
        "noise": 0.0,
        "seed": 0,
        "noise_scale": 2.0,
        "reverse": False,
        "clamp": "none",
        "formula": "sin(x)",
        "custom_points": [],
    }


def default_displacement_params():
    """A point-based displacement style, non-destructive.
    Samples a procedural noise field per point along the path and displaces
    anchor locations in X/Y and the rotation/length of symmetric (non-corner,
    internal) Bezier handles. Base geometry remains unchanged."""
    return {
        "type": "displacement",
        "enabled": False,
        # anchor/location offset strength (canvas units at noise_scale=1)
        "location": 10.0,
        # handle rotation influence (degrees)
        "handle_rotate": 0.0,
        # handle length influence (scale factor contribution)
        "handle_length": 0.0,
        # frequency/scale of the noise field along the path
        "noise_scale": 1.0,
        "seed": 0,
        # axis/application toggles
        "affect_x": True,
        "affect_y": True,
        "affect_rotate": True,
        "affect_length": True,
    }


def default_repeat_params():
    """A repeat-curve style: repeats a drawn curve along the path (like wave distortion)."""
    return {
        "type": "repeat",
        "enabled": False,
        "amplitude": 8.0,
        "frequency": 0.25,
        "phase": 0.0,
        "reverse": False,
        "clamp": "none",
        # Normalized curve points in [0,1]x[-1,1], drawn in order; can overlap itself.
        "repeat_points": [],
    }


def default_thickness_params():
    """A thickness style: bottom follows original curve, top follows a drawn profile (no repetition)."""
    return {
        "type": "thickness",
        "enabled": False,
        "amplitude": 8.0,
        "reverse": False,
        "clamp": "none",
        # Normalized profile points in [0,1]x[-1,1], drawn in order.
        "thickness_points": [],
    }


def _merge_wave_style(raw):
    d = default_wave_params()
    if isinstance(raw, dict):
        d.update({k: raw.get(k, d[k]) for k in d.keys() if k != "type"})
    d["type"] = "wave"
    return d


def _merge_displacement_style(raw):
    d = default_displacement_params()
    if isinstance(raw, dict):
        # new spatial params
        for k in ("enabled", "location", "handle_rotate", "handle_length", "noise_scale", "seed",
                  "affect_x", "affect_y", "affect_rotate", "affect_length"):
            if k in raw:
                d[k] = raw.get(k)
        # migrate legacy curve-profile displacement (amount/profile/custom_points)
        if "location" not in raw and "amount" in raw:
            try:
                d["location"] = float(raw.get("amount", d["location"]) or 0.0)
            except Exception:
                pass
    d["type"] = "displacement"
    return d


def _merge_repeat_style(raw):
    d = default_repeat_params()
    if isinstance(raw, dict):
        for k in d.keys():
            if k == "type":
                continue
            if k in raw:
                d[k] = raw.get(k)
    d["type"] = "repeat"
    # normalize repeat_points
    pts = d.get("repeat_points")
    if isinstance(pts, list):
        clean = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    clean.append([float(p[0]), float(p[1])])
                except Exception:
                    pass
        d["repeat_points"] = clean
    else:
        d["repeat_points"] = []
    return d


def _merge_thickness_style(raw):
    d = default_thickness_params()
    if isinstance(raw, dict):
        for k in d.keys():
            if k == "type":
                continue
            if k in raw:
                d[k] = raw.get(k)
    d["type"] = "thickness"
    pts = d.get("thickness_points")
    if isinstance(pts, list):
        clean = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    clean.append([float(p[0]), float(p[1])])
                except Exception:
                    pass
        d["thickness_points"] = clean
    else:
        d["thickness_points"] = []
    return d


def _merge_distortion_style(raw):
    if not isinstance(raw, dict):
        return default_wave_params()
    t = raw.get("type")
    if t == "displacement":
        return _merge_displacement_style(raw)
    if t == "repeat":
        return _merge_repeat_style(raw)
    if t == "thickness":
        return _merge_thickness_style(raw)
    # treat missing/unknown as wave for backward compatibility
    return _merge_wave_style(raw)


def _is_distortion_style(raw):
    return isinstance(raw, dict) and raw.get("type") in DISTORTION_STYLE_TYPES


def _component_styles(component):
    if not isinstance(component, dict):
        return []
    styles = component.get("styles")
    if isinstance(styles, list):
        return list(styles)
    w = component.get("wave")
    if isinstance(w, dict):
        d = default_wave_params()
        d.update({k: w.get(k, d[k]) for k in d.keys() if k != "type"})
        d["type"] = "wave"
        return [d]
    return []


def _distortion_style_indices(component):
    return [i for i, s0 in enumerate(_component_styles(component)) if _is_distortion_style(s0)]


def _sync_wave_legacy(component, styles=None):
    """Keep legacy component['wave'] mirroring the first wave style, if any."""
    if not isinstance(component, dict):
        return
    if styles is None:
        styles = _component_styles(component)
    first_wave = None
    for s0 in styles:
        if isinstance(s0, dict) and s0.get("type") == "wave":
            first_wave = s0
            break
    if first_wave is not None:
        component["wave"] = {k: first_wave[k] for k in first_wave.keys() if k != "type"}
    else:
        component.pop("wave", None)


def _wave_style_raw_list(component):
    """Raw wave style dicts stored on a component, in stack order."""
    out = []
    for s0 in _component_styles(component):
        if isinstance(s0, dict) and s0.get("type") == "wave":
            out.append(s0)
    if not out and isinstance(component, dict) and isinstance(component.get("wave"), dict):
        out.append(component["wave"])
    return out


def _get_wave_styles(component):
    """All wave styles on a component (defaults merged), in stack order."""
    out = []
    for s0 in _wave_style_raw_list(component):
        out.append(_merge_wave_style(s0))
    return out


def _get_wave_style(component, index=0):
    styles = _get_wave_styles(component)
    if 0 <= index < len(styles):
        return styles[index]
    return default_wave_params()


def _set_wave_style(component, wave_style, index=0):
    if not isinstance(component, dict):
        return
    d = _merge_wave_style(wave_style if isinstance(wave_style, dict) else {})
    styles = [dict(s0) for s0 in _component_styles(component)]
    wave_indices = [i for i, s0 in enumerate(styles) if isinstance(s0, dict) and s0.get("type") == "wave"]
    if 0 <= index < len(wave_indices):
        styles[wave_indices[index]] = d
    else:
        styles.append(d)
    component["styles"] = styles
    _sync_wave_legacy(component, styles)


def _remove_wave_style(component, index=0):
    if not isinstance(component, dict):
        return
    styles = [dict(s0) for s0 in _component_styles(component)]
    wave_indices = [i for i, s0 in enumerate(styles) if isinstance(s0, dict) and s0.get("type") == "wave"]
    if wave_indices:
        if 0 <= index < len(wave_indices):
            del styles[wave_indices[index]]
        else:
            del styles[wave_indices[-1]]
    component["styles"] = styles
    _sync_wave_legacy(component, styles)


def _get_distortion_styles(component):
    """All distortion styles (wave/displacement) on a component, merged, in stack order."""
    out = []
    for s0 in _component_styles(component):
        if _is_distortion_style(s0):
            out.append(_merge_distortion_style(s0))
    return out


def _get_distortion_style(component, index=0):
    styles = _get_distortion_styles(component)
    if 0 <= index < len(styles):
        return styles[index]
    return default_wave_params()


def _set_distortion_style(component, style, index=0):
    if not isinstance(component, dict):
        return
    merged = _merge_distortion_style(style if isinstance(style, dict) else {})
    styles = [dict(s0) for s0 in _component_styles(component)]
    idxs = [i for i, s0 in enumerate(styles) if _is_distortion_style(s0)]
    if 0 <= index < len(idxs):
        styles[idxs[index]] = merged
    else:
        styles.append(merged)
    component["styles"] = styles
    _sync_wave_legacy(component, styles)


def _remove_distortion_style(component, index=0):
    if not isinstance(component, dict):
        return
    styles = [dict(s0) for s0 in _component_styles(component)]
    idxs = [i for i, s0 in enumerate(styles) if _is_distortion_style(s0)]
    if idxs:
        if 0 <= index < len(idxs):
            del styles[idxs[index]]
        else:
            del styles[idxs[-1]]
    component["styles"] = styles
    _sync_wave_legacy(component, styles)


def _wave_params(component):
    return _get_wave_style(component)


def _wave_style_active(wv):
    """True when a single wave style actually contributes a visible offset."""
    try:
        return bool(wv.get("enabled")) and (
            abs(float(wv.get("amplitude", 0) or 0)) > 1e-6
            or abs(float(wv.get("noise", 0) or 0)) > 1e-6
        )
    except Exception:
        return False


def _displacement_style_active(dv):
    """True when a spatial displacement style actually contributes an effect."""
    try:
        if not bool(dv.get("enabled")):
            return False
        ax = bool(dv.get("affect_x", True))
        ay = bool(dv.get("affect_y", True))
        ar = bool(dv.get("affect_rotate", True))
        al = bool(dv.get("affect_length", True))
        loc = abs(float(dv.get("location", 0) or 0))
        rot = abs(float(dv.get("handle_rotate", 0) or 0))
        hlen = abs(float(dv.get("handle_length", 0) or 0))
        has_loc = (loc > 1e-6) and (ax or ay)
        has_rot = (rot > 1e-6) and ar
        has_len = (hlen > 1e-6) and al
        return has_loc or has_rot or has_len
    except Exception:
        return False


def _repeat_style_active(rv):
    """True when a repeat-curve style actually contributes a visible offset."""
    try:
        if not bool(rv.get("enabled")):
            return False
        pts = rv.get("repeat_points")
        if not isinstance(pts, list) or len(pts) < 2:
            return False
        return abs(float(rv.get("amplitude", 0) or 0)) > 1e-6
    except Exception:
        return False


def _thickness_style_active(tv):
    """True when a thickness style actually contributes a shape."""
    try:
        if not bool(tv.get("enabled")):
            return False
        pts = tv.get("thickness_points")
        if not isinstance(pts, list) or len(pts) < 2:
            return False
        return abs(float(tv.get("amplitude", 0) or 0)) > 1e-6
    except Exception:
        return False


def _distortion_style_active(sv):
    if not isinstance(sv, dict):
        return False
    t = sv.get("type", "wave")
    if t == "displacement":
        return _displacement_style_active(sv)
    if t == "repeat":
        return _repeat_style_active(sv)
    if t == "thickness":
        return _thickness_style_active(sv)
    return _wave_style_active(sv)


def _component_wave_enabled(component):
    return any(_distortion_style_active(sv) for sv in _get_distortion_styles(component))


def _pseudo_noise01(i, seed=0):
    # deterministic hash-based noise in [0,1)
    x = (int(i) * 374761393 + int(seed) * 668265263 + 1442695041) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 1274126177 & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFFFF) / 4294967295.0

def _smooth_noise1d(x, seed=0, scale=2.0):
    try:
        scale = max(0.1, float(scale))
    except Exception:
        scale = 2.0
    p = float(x) * scale
    i0 = int(math.floor(p))
    i1 = i0 + 1
    f = p - i0
    # smoothstep
    t = f * f * (3.0 - 2.0 * f)
    n0 = _pseudo_noise01(i0, seed) * 2.0 - 1.0
    n1 = _pseudo_noise01(i1, seed) * 2.0 - 1.0
    return n0 + (n1 - n0) * t

def _latex_to_python_expr(expr):
    """Best-effort conversion of LaTeX-like math formulas to Python expressions."""
    import re
    if expr is None:
        return "sin(x)"
    s = str(expr).strip()
    if not s:
        return "sin(x)"
    # strip f(x)=
    s = re.sub(r'^\s*[A-Za-z]\s*\\left\s*\(.*?\\right\s*\)\s*=\s*', '', s)
    s = re.sub(r'^\s*[A-Za-z]\s*\(.*?\)\s*=\s*', '', s)
    s = re.sub(r'^\s*y\s*=\s*', '', s)
    s = s.replace(r'\left', '').replace(r'\right', '')
    s = s.replace(r'\cdot', '*').replace(r'\times', '*')
    s = s.replace(r'\pi', 'pi')
    s = re.sub(r'\^\{([^{}]*)\}', r'**(\1)', s)
    s = s.replace('^', '**')
    s = re.sub(r'\\operatorname\s*\{([^}]+)\}', r'\1', s)
    # functions - longer/more specific first
    for k,v in [(r'\arcsin','asin'),(r'\arccos','acos'),(r'\arctan','atan'),
                (r'\sin','sin'),(r'\cos','cos'),(r'\tan','tan'),
                (r'\sqrt','sqrt'),(r'\ln','log'),(r'\log','log10'),(r'\exp','exp'),(r'\abs','abs')]:
        s = s.replace(k,v)
    s = re.sub(r'\\([A-Za-z]+)', r'\1', s)
    s = s.replace('\\', '')

    def read_group(text, j):
        while j < len(text) and text[j].isspace(): j += 1
        if j < len(text) and text[j] == '{':
            depth=0; k=j
            while k<len(text):
                if text[k]=='{': depth+=1
                elif text[k]=='}':
                    depth-=1
                    if depth==0: return text[j+1:k], k+1
                k+=1
            return text[j+1:], len(text)
        elif j<len(text): return text[j], j+1
        return '', j

    for _ in range(20):
        i=0; out=[]; changed=False
        while i<len(s):
            if s.startswith('frac',i) and (i==0 or not (s[i-1].isalnum() or s[i-1]=='_')):
                i+=4; a,i=read_group(s,i); b,i=read_group(s,i)
                out.append('((' + a + ')/(' + b + '))'); changed=True
            else:
                out.append(s[i]); i+=1
        ns=''.join(out)
        if not changed: break
        s=ns

    funcs=['sqrt','sin','cos','tan','asin','acos','atan','abs','log','log10','exp','sign','floor','ceil','min','max']
    for fn in funcs:
        for _ in range(12):
            i=0; out=[]; changed=False
            while i<len(s):
                if s.startswith(fn+'{',i) and (i==0 or not (s[i-1].isalnum() or s[i-1]=='_')):
                    j=i+len(fn); a,j=read_group(s,j)
                    out.append(fn+'('+a+')'); i=j; changed=True
                else:
                    out.append(s[i]); i+=1
            ns=''.join(out)
            if not changed: break
            s=ns

    for _ in range(12):
        m=re.search(r'\|([^|]+)\|', s)
        if not m: break
        s=s[:m.start()]+'abs('+m.group(1)+')'+s[m.end():]
    s=s.replace('|','').replace('{','(').replace('}',')')
    func_pat=r'(?:'+'|'.join(sorted(funcs,key=len,reverse=True))+r')'
    s=re.sub(r'(\d)([A-Za-z_\(])', r'\1*\2', s)
    s=re.sub(r'(\))([A-Za-z0-9_\(])', r'\1*\2', s)
    s=re.sub(r'(\bpi\b)([A-Za-z0-9_\(])', r'\1*\2', s)
    s=re.sub(r'([A-Za-z0-9_\)])(\bpi\b)', r'\1*\2', s)
    # insert * before function calls, but avoid splitting identifiers like asin -> a*sin
    def _mult_before_func(m):
        pre = m.group(1)
        fn = m.group(2)
        # if pre ends with letter and pre+fn forms a known function name, skip
        if pre and pre[-1].isalpha():
            combo = pre[-1] + fn
            if combo in funcs:
                return m.group(0)
        return pre + '*' + fn
    s=re.sub(r'([A-Za-z0-9_\)])(' + func_pat + r')\b', _mult_before_func, s)
    s=re.sub(r'\b(\d)\s*([A-Za-z])\b', r'\1*\2', s)
    s=s.replace('pi x','pi*x').replace('npi','n*pi')
    s=re.sub(r'^[A-Za-z]\s*\([^)]*\)\s*=\s*', '', s)
    return s.strip() or "sin(x)"

def _generate_sine_deriv_template(amp, freq):
    """Generate wave key/control points for a sine shape using derivative analysis.

    For a sine wave with angular frequency (per template period) = period, the
    wave value is v(t) = amp * sin(period * t) over normalized phase t in [0, 1].
    The derivative is dv/dt = amp * period * cos(period * t).
    Key positions where the derivative is zero (extrema) or at 45-degree tangent
    angles become the control points; y values come from the sine function.

    Returns a sorted list of (t, y) key points forming one smooth template period.
    """
    freq = max(0.05, float(freq))
    period = 2.0 * math.pi * freq  # angular frequency per template period
    # derivative zeros: period * t = pi/2 + k*pi  ->  t = (pi/2 + k*pi) / period
    key_ts = [0.0]
    k = 0
    while True:
        p_ang = math.pi / 2.0 + k * math.pi
        if p_ang > period - 1e-9:
            break
        t_val = p_ang / period
        if t_val < 1.0 - 1e-9 and t_val > 0.0:
            key_ts.append(t_val)
        k += 1
    key_ts.append(1.0)
    # Build unique sorted key points with y = amp * sin(period * t)
    seen = []
    for t_val in sorted(key_ts):
        if any(abs(t_val - existing) < 1e-6 for existing in seen):
            continue
        seen.append(t_val)
    points = []
    for t_val in seen:
        y_val = amp * math.sin(period * t_val)
        points.append((float(t_val), float(y_val)))
    # ensure endpoints exist
    if points[0][0] > 0:
        points.insert(0, (0.0, 0.0))
    if points[-1][0] < 1.0:
        points.append((1.0, float(amp * math.sin(period))))
    return points

def _formula_env_for(w):
    """Build the sandboxed evaluation environment for a formula wave style."""
    allowed_base = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed_base.update({"pi": math.pi, "tau": math.tau, "e": math.e,
                         "abs": abs, "min": min, "max": max, "pow": pow, "round": round,
                         "sign": lambda v: (1.0 if v > 0 else (-1.0 if v < 0 else 0.0)),
                         "r": max(1.0, float(w.get("amplitude", 8.0) or 8.0)),
                         "n": 0.0,
                         "a": float(w.get("amplitude", 8.0) or 8.0),
                         "f": float(w.get("frequency", 0.25) or 0.25),
                         "phi": float(w.get("phase", 0.0) or 0.0)})
    formula = str(w.get("formula", "sin(x)") or "sin(x)")
    try:
        expr = _latex_to_python_expr(formula)
    except Exception:
        expr = "sin(x)"
    return (expr, allowed_base)

def _apply_wave_clamp(v, mode):
    """Clamp a wave contribution to one side: 'positive' (>=0), 'negative' (<=0), or none."""
    if mode == "positive":
        return max(0.0, v)
    if mode == "negative":
        return min(0.0, v)
    return v

def _prepare_wave_evaluator(w, geom=None):
    """Precompute everything needed to evaluate one wave style along a curve.

    `geom` is {"diag": bbox diagonal, "length": curve length} in canvas units
    (defaults to 1.0/1.0 for previews and icons). Frequency semantics:
    0.01..1.0 means the cycle length equals freq * bbox diagonal (1.0 = one
    cycle spans the diagonal); values above 1.0 keep the legacy meaning of
    "N cycles across the curve" so old saved files still render the same.
    Amplitude is relative to the shape: amp/100 * diagonal/2 canvas units."""
    shape = str(w.get("shape", "sine") or "sine").lower()
    ev = {
        "shape": shape,
        "amp": float(w.get("amplitude", 0.0) or 0.0),
        "freq": float(w.get("frequency", 0.0) or 0.0),
        "phase": float(w.get("phase", 0.0) or 0.0),
        "noise": float(w.get("noise", 0.0) or 0.0),
        "seed": int(w.get("seed", 0) or 0),
        "noise_scale": float(w.get("noise_scale", 2.0) or 2.0),
        "formula_env": None,
        "custom_points": None,
        "cycles": 0.0,
        "amp_px": 0.0,
        "noise_px": 0.0,
        "reverse": False,
        "clamp": "none",
    }
    ev["reverse"] = bool(w.get("reverse"))
    clamp_mode = str(w.get("clamp", "none") or "none").lower()
    if clamp_mode not in ("none", "positive", "negative"):
        clamp_mode = "none"
    ev["clamp"] = clamp_mode
    diag = 1.0
    length = 1.0
    if isinstance(geom, dict):
        try:
            diag = max(1e-6, float(geom.get("diag", 1.0) or 1.0))
        except Exception:
            diag = 1.0
        try:
            length = max(1e-6, float(geom.get("length", 1.0) or 1.0))
        except Exception:
            length = 1.0
    freq = ev["freq"]
    if freq <= 0.0:
        ev["cycles"] = 0.0
    elif freq > 1.0:
        # legacy saved files: frequency was "cycles across the curve"
        ev["cycles"] = freq
    else:
        ev["cycles"] = length / (freq * diag)
    # amplitude (and legacy per-wave noise amount) scale with the shape size
    ev["amp_px"] = ev["amp"] / 100.0 * diag * 0.5
    ev["noise_px"] = ev["noise"] / 100.0 * diag * 0.5
    if shape == "formula":
        ev["formula_env"] = _formula_env_for(w)
    if shape == "sine_bezier":
        # derivative-generated template; values stay in [-1,1] (amp scales later)
        periods = freq if freq > 1.0 else 1.0
        ev["custom_points"] = _generate_sine_deriv_template(1.0, periods)
        ev["shape"] = "custom"
    else:
        ev["custom_points"] = w.get("custom_points", None)
    return ev


def _prepare_repeat_evaluator(w, geom=None):
    """Precompute evaluator for a repeat-curve style (parametric drawn pattern)."""
    ev = {
        "shape": "repeat",
        "amp": float(w.get("amplitude", 0.0) or 0.0),
        "freq": float(w.get("frequency", 0.0) or 0.0),
        "phase": float(w.get("phase", 0.0) or 0.0),
        "noise": 0.0,
        "seed": 0,
        "noise_scale": 1.0,
        "formula_env": None,
        "custom_points": None,
        "repeat_points": None,
        "repeat_arclen": None,
        "repeat_total": 0.0,
        "cycles": 0.0,
        "amp_px": 0.0,
        "noise_px": 0.0,
        "reverse": bool(w.get("reverse", False)),
        "clamp": "none",
    }
    clamp_mode = str(w.get("clamp", "none") or "none").lower()
    if clamp_mode not in ("none", "positive", "negative"):
        clamp_mode = "none"
    ev["clamp"] = clamp_mode
    diag = 1.0
    length = 1.0
    if isinstance(geom, dict):
        try:
            diag = max(1e-6, float(geom.get("diag", 1.0) or 1.0))
        except Exception:
            diag = 1.0
        try:
            length = max(1e-6, float(geom.get("length", 1.0) or 1.0))
        except Exception:
            length = 1.0
    freq = ev["freq"]
    if freq <= 0.0:
        ev["cycles"] = 0.0
    elif freq > 1.0:
        ev["cycles"] = freq
    else:
        ev["cycles"] = length / (freq * diag)
    ev["amp_px"] = ev["amp"] / 100.0 * diag * 0.5
    pts = w.get("repeat_points")
    clean = []
    if isinstance(pts, list):
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    clean.append((float(p[0]), float(p[1])))
                except Exception:
                    pass
    ev["repeat_points"] = clean
    # arc-length parameterization in drawn order (allows self-overlapping shapes)
    ar = [0.0]
    total = 0.0
    for i in range(1, len(clean)):
        dx = clean[i][0] - clean[i - 1][0]
        dy = clean[i][1] - clean[i - 1][1]
        total += math.hypot(dx, dy)
        ar.append(total)
    ev["repeat_arclen"] = ar
    ev["repeat_total"] = total
    return ev











CUSTOM_WAVE_SAMPLES = 128

























































