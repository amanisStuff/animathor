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


def _prepare_thickness_evaluator(w, geom=None):
    """Precompute evaluator for a thickness style (single profile along full path)."""
    ev = {
        "shape": "thickness",
        "amp": float(w.get("amplitude", 0.0) or 0.0),
        "reverse": bool(w.get("reverse", False)),
        "clamp": "none",
        "thickness_points": None,
        "thickness_arclen": None,
        "thickness_total": 0.0,
        "amp_px": 0.0,
    }
    clamp_mode = str(w.get("clamp", "none") or "none").lower()
    if clamp_mode not in ("none", "positive", "negative"):
        clamp_mode = "none"
    ev["clamp"] = clamp_mode
    diag = 1.0
    if isinstance(geom, dict):
        try:
            diag = max(1e-6, float(geom.get("diag", 1.0) or 1.0))
        except Exception:
            diag = 1.0
    ev["amp_px"] = ev["amp"] / 100.0 * diag * 0.5
    pts = w.get("thickness_points")
    clean = []
    if isinstance(pts, list):
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    clean.append((float(p[0]), float(p[1])))
                except Exception:
                    pass
    ev["thickness_points"] = clean
    ar = [0.0]; total = 0.0
    for i in range(1, len(clean)):
        dx = clean[i][0] - clean[i - 1][0]
        dy = clean[i][1] - clean[i - 1][1]
        total += math.hypot(dx, dy)
        ar.append(total)
    ev["thickness_arclen"] = ar
    ev["thickness_total"] = total
    return ev


def _thickness_profile_at(frac, ev):
    """Sample thickness profile at frac 0..1 along the full path. Returns normal offset (pattern units)."""
    pts = ev.get("thickness_points") or []
    if len(pts) < 2:
        return 0.0
    total = float(ev.get("thickness_total") or 0.0)
    ar = ev.get("thickness_arclen") or []
    f = max(0.0, min(1.0, float(frac)))
    if total <= 1e-9 or len(ar) != len(pts):
        idxf = f * (len(pts) - 1)
        i0 = int(math.floor(idxf)); i1 = min(len(pts) - 1, i0 + 1)
        tt = idxf - i0
        return pts[i0][1] + (pts[i1][1] - pts[i0][1]) * tt
    target = f * total
    j = 0
    while j < len(ar) - 2 and ar[j + 1] < target:
        j += 1
    a0, a1 = ar[j], ar[j + 1]
    seg = a1 - a0
    tt = 0.0 if seg <= 1e-9 else (target - a0) / seg
    tt = max(0.0, min(1.0, tt))
    return pts[j][1] + (pts[j + 1][1] - pts[j][1]) * tt


def _repeat_offset_at(frac, ev):
    """Parametric repeat offset at phase frac in [0,1].
    Returns (tangential, normal) in pattern units; pattern is drawn in order
    and may self-overlap (not a function of x)."""
    pts = ev.get("repeat_points") or []
    if len(pts) < 2:
        return 0.0, 0.0
    total = float(ev.get("repeat_total") or 0.0)
    ar = ev.get("repeat_arclen") or []
    if total <= 1e-9 or len(ar) != len(pts):
        # fallback: index-based
        f = max(0.0, min(1.0, float(frac)))
        idxf = f * (len(pts) - 1)
        i0 = int(math.floor(idxf))
        i1 = min(len(pts) - 1, i0 + 1)
        tt = idxf - i0
        p0, p1 = pts[i0], pts[i1]
        x = p0[0] + (p1[0] - p0[0]) * tt
        y = p0[1] + (p1[1] - p0[1]) * tt
        return x - 0.5, y
    f = float(frac) % 1.0
    if f < 0:
        f += 1.0
    target = f * total
    # linear scan is fine for small pattern point counts
    j = 0
    while j < len(ar) - 2 and ar[j + 1] < target:
        j += 1
    a0, a1 = ar[j], ar[j + 1]
    seg = a1 - a0
    tt = 0.0 if seg <= 1e-9 else (target - a0) / seg
    tt = max(0.0, min(1.0, tt))
    p0, p1 = pts[j], pts[j + 1]
    x = p0[0] + (p1[0] - p0[0]) * tt
    y = p0[1] + (p1[1] - p0[1]) * tt
    return x - 0.5, y


def _repeat_value_at(frac, pts_or_ev):
    """Scalar normal component for preview/icon compatibility."""
    if isinstance(pts_or_ev, dict):
        _t, n = _repeat_offset_at(frac, pts_or_ev)
        return n
    # legacy: pts list
    if not pts_or_ev or len(pts_or_ev) < 2:
        return 0.0
    ev = {"repeat_points": list(pts_or_ev), "repeat_arclen": None, "repeat_total": 0.0}
    # build arc
    ar = [0.0]; total = 0.0
    for i in range(1, len(ev["repeat_points"])):
        dx = ev["repeat_points"][i][0] - ev["repeat_points"][i - 1][0]
        dy = ev["repeat_points"][i][1] - ev["repeat_points"][i - 1][1]
        total += math.hypot(dx, dy); ar.append(total)
    ev["repeat_arclen"] = ar; ev["repeat_total"] = total
    _t, n = _repeat_offset_at(frac, ev)
    return n


def _custom_wave_at(f, cps):
    """Catmull-Rom/Hermite interpolation of custom wave points at phase f in [0,1].
    Tangents come from neighbouring control points (normalised by pi/4 to match
    ideal sine derivatives), so few-point sine templates stay smooth."""
    if not cps or len(cps) < 2:
        return 0.0
    cps = sorted(cps, key=lambda cp: (cp[0], cp[1]))
    npts = len(cps)
    seg_idx = -1
    for j in range(npts - 1):
        if cps[j][0] <= f <= cps[j + 1][0]:
            seg_idx = j
            break
    if seg_idx < 0:
        # f outside the point x-range: clamp to nearest endpoint value
        return cps[0][1] if f < cps[0][0] else cps[-1][1]
    x0, y0 = cps[seg_idx]
    x1, y1 = cps[seg_idx + 1]
    dx = x1 - x0
    if abs(dx) < 1e-9:
        return y0
    t = (f - x0) / dx
    # Catmull-Rom tangents from neighbouring points
    if seg_idx > 0:
        tan_left_x = x0 - cps[seg_idx - 1][0]
        tan_left_y = y0 - cps[seg_idx - 1][1]
    else:
        tan_left_x = dx
        tan_left_y = y1 - y0
    if seg_idx + 2 < npts:
        tan_right_x = cps[seg_idx + 2][0] - x1
        tan_right_y = cps[seg_idx + 2][1] - y1
    else:
        tan_right_x = dx
        tan_right_y = y1 - y0
    # normalised slopes (dy/dx), scaled to ideal sine derivatives
    norm_factor = math.pi / 4.0
    m0 = (tan_left_y / tan_left_x if abs(tan_left_x) > 1e-9 else 0.0) * norm_factor
    m1 = (tan_right_y / tan_right_x if abs(tan_right_x) > 1e-9 else 0.0) * norm_factor
    # cubic Hermite basis
    t2 = t * t
    t3 = t2 * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2
    return h00 * y0 + h10 * m0 * dx + h01 * y1 + h11 * m1 * dx

CUSTOM_WAVE_SAMPLES = 128

def _custom_uniform_samples(cps, n=None):
    """Resample any point set onto the fixed uniform sample grid (t in [0,1])."""
    if n is None:
        n = CUSTOM_WAVE_SAMPLES
    n = max(2, int(n))
    if cps and len(cps) >= 2:
        return [(i / (n - 1.0), _custom_wave_at(i / (n - 1.0), cps)) for i in range(n)]
    return [(i / (n - 1.0), 0.0) for i in range(n)]

def _custom_wave_paint(w, box, pos, drag):
    """Paint a custom waveform/repeat pattern inside the box.

    Wave/custom: uniform-column paint (function of x), fills gaps horizontally.
    Repeat: freeform parametric points in drawn order, allowing loops/overlap.
    `drag` is previous paint state, or None when starting a stroke.
    """
    if not box or box.w <= 0 or box.h <= 0:
        return drag
    t = clamp((pos[0] - box.x) / max(1, box.w - 1), 0.0, 1.0)
    amp = clamp((pos[1] - (box.y + box.h / 2.0)) / max(1, box.h / 2.0), -1.0, 1.0)

    if w.get("type") in ("repeat", "thickness"):
        key = "thickness_points" if w.get("type") == "thickness" else "repeat_points"
        pts = w.get(key)
        if not isinstance(pts, list):
            pts = []
        # append in drawn order; thin by distance to keep list reasonable
        pnew = [float(t), float(amp)]
        if not pts:
            pts.append(pnew)
        else:
            last = pts[-1]
            try:
                dx = pnew[0] - float(last[0])
                dy = pnew[1] - float(last[1])
            except Exception:
                dx, dy = 1.0, 0.0
            if (dx * dx + dy * dy) >= (0.004 * 0.004):
                pts.append(pnew)
        w[key] = pts
        return [t, amp]

    n = CUSTOM_WAVE_SAMPLES
    key = "custom_points"
    pts = w.get(key)
    if not pts or len(pts) != n:
        # convert legacy sparse points (or empty) onto the uniform grid first
        pts = _custom_uniform_samples(pts)
        w[key] = pts
    idx = int(round(t * (n - 1)))
    if drag is None or len(drag) < 2:
        drag = [idx, amp]
    i0, i1 = min(drag[0], idx), max(drag[0], idx)
    for i in range(i0, i1 + 1):
        f = 0.0 if i1 == i0 else (i - i0) / (i1 - i0)
        pts[i] = (i / (n - 1.0), drag[1] + (amp - drag[1]) * f)
    return [idx, amp]

def _custom_smooth_samples(cps, passes=2, window=5):
    """Wrap-around moving average over the fixed sample grid (the wave loops,
    so smoothing wraps across the ends and stays seamless)."""
    pts = _custom_uniform_samples(cps)
    n = len(pts)
    vals = [a for _t, a in pts]
    half = max(1, window // 2)
    for _ in range(max(0, passes)):
        vals = [sum(vals[(i + j) % n] for j in range(-half, half + 1)) / (2 * half + 1)
                for i in range(n)]
    return [(i / (n - 1.0), v) for i, v in enumerate(vals)]


def _smooth_repeat_points(pts, passes=2, window=5):
    """Moving-average smoothing for freeform repeat pattern points (drawn order)."""
    if not isinstance(pts, list) or len(pts) < 3:
        return list(pts) if isinstance(pts, list) else []
    clean = []
    for p in pts:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                clean.append([float(p[0]), float(p[1])])
            except Exception:
                pass
    if len(clean) < 3:
        return clean
    half = max(1, int(window) // 2)
    for _ in range(max(0, int(passes))):
        out = []
        n = len(clean)
        for i in range(n):
            j0 = max(0, i - half)
            j1 = min(n - 1, i + half)
            cnt = j1 - j0 + 1
            sx = sum(clean[j][0] for j in range(j0, j1 + 1)) / cnt
            sy = sum(clean[j][1] for j in range(j0, j1 + 1)) / cnt
            # keep endpoints anchored for stability
            if i == 0 or i == n - 1:
                sx, sy = clean[i][0], clean[i][1]
            out.append([max(0.0, min(1.0, sx)), max(-1.0, min(1.0, sy))])
        clean = out
    return clean


def _segs_to_repeat_points(segs, n=96):
    """Sample curve segs into normalized repeat pattern points (drawn order).
    x is mapped to 0..1 along arc length, y is centered and scaled to [-1,1]."""
    if not segs:
        return []
    # sample polyline
    pts = []
    total = 0.0
    seg_lens = []
    for seg in segs:
        try:
            p0, c1, c2, p3 = seg
        except Exception:
            seg_lens.append(0.0)
            continue
        l = 0.0
        prev = p0
        for i in range(1, 21):
            t = i / 20.0
            p = cubic_bezier_point(p0, c1, c2, p3, t)
            l += math.hypot(p[0] - prev[0], p[1] - prev[1])
            prev = p
        seg_lens.append(l)
        total += l
    if total <= 1e-9:
        return []
    cum = 0.0
    for si, seg in enumerate(segs):
        try:
            p0, c1, c2, p3 = seg
        except Exception:
            continue
        sl = seg_lens[si] if si < len(seg_lens) else 0.0
        steps = max(2, int(round(n * (sl / total))))
        start = cum / total
        end = (cum + sl) / total
        for i in range(0 if si == 0 else 1, steps + 1):
            t = i / steps
            x, y = cubic_bezier_point(p0, c1, c2, p3, t)
            s = start + (end - start) * t
            pts.append((s, x, y))
        cum += sl
    if len(pts) < 2:
        return []
    # Normalize based on the curve's start/end chord.
    # X axis = chord from start to end (0 at start, 1 at end).
    # Y axis = perpendicular distance from that chord, preserving aspect.
    x0, y0 = pts[0][1], pts[0][2]
    x1, y1 = pts[-1][1], pts[-1][2]
    cdx, cdy = x1 - x0, y1 - y0
    chord = math.hypot(cdx, cdy)
    if chord < 1e-9:
        # degenerate: fall back to bbox
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 1e-9); dy = max(maxy - miny, 1e-9)
        cx = (minx + maxx) / 2.0; cy = (miny + maxy) / 2.0
        scale = 1.0 / max(dx, dy)
        out = []
        for _s, x, y in pts:
            nxp = (x - minx) / dx
            nyp = max(-1.0, min(1.0, (y - cy) * scale * 2.0))
            out.append([max(0.0, min(1.0, nxp)), nyp])
        return out
    tx, ty = cdx / chord, cdy / chord  # along chord
    nxv, nyv = -ty, tx                 # perpendicular (left normal)
    out = []
    for _s, x, y in pts:
        dxp, dyp = x - x0, y - y0
        along = (dxp * tx + dyp * ty) / chord      # 0..1 at start/end
        perp = (dxp * nxv + dyp * nyv) / chord     # distance from chord, relative to chord length
        out.append([max(0.0, min(1.0, along)), max(-1.0, min(1.0, perp))])
    return out

def _wave_value_for(ev, s):
    """Evaluate one prepared wave style at normalized arc position s in [0,1].
    With the reverse flag set, the result is inverted: -f(x)."""
    v = _wave_value_raw(ev, s)
    return -v if ev["reverse"] else v

def _wave_value_raw(ev, s):
    """Raw wave shape value in [-1,1] (direction inversion not applied)."""
    freq = ev["freq"]
    if freq == 0:
        return 0.0
    # phase slider is in degrees (0..360) and maps to a full cycle; the number
    # of cycles across the curve comes from the geometry (cycle length is
    # freq * bbox diagonal for the 0.01..1.0 range)
    p = (s * ev["cycles"] * math.tau) + math.radians(ev["phase"])
    shape = ev["shape"]
    if shape == "noise":
        # standalone noise distortion: smooth pseudo-random profile in [-1,1]
        # so amplitude scales it exactly like every other shape. Phase does not
        # apply to noise (grayed out in the panel).
        return _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
    if shape == "formula" and ev["formula_env"] is not None:
        fstr, abase = ev["formula_env"]
        try:
            env = dict(abase)
            frac = (p / math.tau) - math.floor(p / math.tau)
            env.update({"x": p, "p": p, "t": frac, "s": s, "frac": frac})
            return float(eval(fstr, {"__builtins__": {}}, env))
        except Exception:
            return math.sin(p)
    cps = ev["custom_points"]
    if shape == "custom" and cps and len(cps) >= 2:
        frac = max(0.0, min(1.0, (p / math.tau) - math.floor(p / math.tau)))
        return _custom_wave_at(frac, cps)
    if shape == "repeat":
        rpts = ev.get("repeat_points")
        if isinstance(rpts, list) and len(rpts) >= 2:
            frac = (p / math.tau) - math.floor(p / math.tau)
            return _repeat_value_at(frac, ev)
        return 0.0
    # built-in shapes
    tval = p / math.tau
    frac = tval - math.floor(tval)
    if shape == "triangle":
        return 4.0 * abs(frac - 0.5) - 1.0
    if shape == "square":
        return 1.0 if frac < 0.5 else -1.0
    if shape == "sawtooth":
        return 2.0 * frac - 1.0
    if shape == "circular":
        if frac < 0.5:
            q = 4.0 * frac - 1.0
            return math.sqrt(max(0.0, 1.0 - q * q))
        q = 4.0 * (frac - 0.5) - 1.0
        return -math.sqrt(max(0.0, 1.0 - q * q))
    if shape == "half_circle":
        q = 2.0 * frac - 1.0
        return math.sqrt(max(0.0, 1.0 - q * q))
    return math.sin(p)

def _wave_icon_polyline(wave, n=20):
    """One normalized cycle of a wave/repeat/thickness style, for drawing shape thumbnail icons."""
    w = dict(wave) if isinstance(wave, dict) else {}
    w["frequency"] = 1.0
    w["phase"] = 0.0
    w["noise"] = 0.0
    w["clamp"] = "none"
    if w.get("type") == "thickness":
        ev = _prepare_thickness_evaluator(w)
        pts_t = ev.get("thickness_points") or []
        pts = []
        for i in range(n + 1):
            s = i / n
            v = _thickness_profile_at(s, ev) if len(pts_t) >= 2 else 0.0
            pts.append((s, v))
        return pts
    if w.get("type") == "repeat":
        ev = _prepare_repeat_evaluator(w)
    else:
        ev = _prepare_wave_evaluator(w)
    pts = []
    for i in range(n + 1):
        s = i / n
        pts.append((s, _wave_value_for(ev, s)))
    return pts

def _wave_preview_polyline(wave, n=None):
    """Composed wave/repeat/thickness preview, normalized for the live preview box."""
    w = wave if isinstance(wave, dict) else {}
    if w.get("type") == "thickness":
        ev = _prepare_thickness_evaluator(w)
        pts_t = ev.get("thickness_points") or []
        if len(pts_t) < 2:
            return [(0.0, 0.0), (1.0, 0.0)]
        amp = float(ev.get("amp", 0.0) or 0.0)
        n = max(64, min(512, len(pts_t) * 4))
        pts = []
        for i in range(n + 1):
            s = i / n
            v = _thickness_profile_at(s, ev)
            if ev.get("reverse"):
                v = -v
            v = amp * v / 100.0
            v = max(-1.0, min(1.0, v))
            pts.append((s, v))
        return pts
    if w.get("type") == "repeat":
        ev = _prepare_repeat_evaluator(w)
    else:
        ev = _prepare_wave_evaluator(w)
    if n is None:
        cycles = abs(ev.get("cycles", 0.0))
        n = int(min(2400, max(240, cycles * 24)))
        if ev.get("shape") == "noise" or ev.get("noise", 0.0) != 0.0:
            noise_cells = max(1.0, cycles) * 4.0 * max(0.1, ev.get("noise_scale", 2.0))
            n = int(min(2400, max(n, noise_cells * 6)))
        if ev.get("shape") == "repeat":
            rpts = ev.get("repeat_points") or []
            n = int(min(2400, max(n, cycles * max(16, len(rpts) * 2))))
    pts = []
    for i in range(n + 1):
        s = i / n
        total = ev.get("amp", 0.0) * _wave_value_for(ev, s)
        if ev.get("noise", 0.0) != 0.0:
            nz = _smooth_noise1d(s * ev.get("cycles", 0.0) * 4.0, seed=ev.get("seed", 0), scale=ev.get("noise_scale", 2.0))
            total += ev.get("noise", 0.0) * nz
        total = _apply_wave_clamp(total, ev.get("clamp", "none"))
        pts.append((s, total / 100.0))
    return pts


def _smooth_noise2d(x, y, seed=0, scale=1.0):
    """2D value noise in [-1,1], smoothly interpolated (object-space field)."""
    try:
        scale = max(1e-4, float(scale))
    except Exception:
        scale = 1.0
    px = float(x) * scale
    py = float(y) * scale
    ix0 = int(math.floor(px))
    iy0 = int(math.floor(py))
    fx = px - ix0
    fy = py - iy0
    tx = fx * fx * (3.0 - 2.0 * fx)
    ty = fy * fy * (3.0 - 2.0 * fy)

    def _n(ix, iy):
        h = (ix * 374761393 + iy * 668265263) & 0xFFFFFFFF
        return _pseudo_noise01(h, seed) * 2.0 - 1.0

    n00 = _n(ix0, iy0)
    n10 = _n(ix0 + 1, iy0)
    n01 = _n(ix0, iy0 + 1)
    n11 = _n(ix0 + 1, iy0 + 1)
    nx0 = n00 + (n10 - n00) * tx
    nx1 = n01 + (n11 - n01) * tx
    return nx0 + (nx1 - nx0) * ty


def _spatial_displacement_field(d, param, size_ref=100.0, _ly=None):
    """Sample 4D point-based displacement (dx,dy, drot, dlen) along the path.

    `param` is the point's normalized position along the component (0..1).
    The 4th arg is accepted for backward compatibility with old (d,lx,ly,size_ref)
    calls and is ignored.
    """
    # Backward compat: old signature (d, lx, ly, size_ref)
    if _ly is not None and not isinstance(size_ref, (int, float)):
        # unlikely, but be safe
        size_ref = 100.0
    if _ly is not None and isinstance(_ly, (int, float)):
        # old call: (d, lx, ly, size_ref) - _ly is actually ly, size_ref is old size_ref
        # We can't perfectly map spatial->point without index, but use a stable hash.
        old_lx = float(param)
        old_ly = float(_ly)
        old_ref = float(size_ref) if isinstance(size_ref, (int, float)) else 100.0
        param = ((old_lx / max(1e-6, old_ref)) * 0.73 + (old_ly / max(1e-6, old_ref)) * 1.37) % 1.0
        size_ref = old_ref

    loc = float(d.get("location", 0.0) or 0.0)
    hrot = float(d.get("handle_rotate", 0.0) or 0.0)
    hlen = float(d.get("handle_length", 0.0) or 0.0)
    nscale = float(d.get("noise_scale", 1.0) or 1.0)
    seed = int(d.get("seed", 0) or 0)
    ref = max(1e-6, float(size_ref or 100.0))
    t = float(param) * max(0.01, nscale) * 2.0
    nx = _smooth_noise2d(t, 0.17, seed=seed + 11, scale=1.0)
    ny = _smooth_noise2d(t, 0.73, seed=seed + 29, scale=1.0)
    nr = _smooth_noise2d(t, 1.31, seed=seed + 47, scale=1.0)
    nl = _smooth_noise2d(t, 1.91, seed=seed + 71, scale=1.0)
    dx = nx * loc * ref * 0.02
    dy = ny * loc * ref * 0.02
    drot = nr * math.radians(hrot) * 0.5
    dlen = nl * hlen * 0.02
    if not bool(d.get("affect_x", True)):
        dx = 0.0
    if not bool(d.get("affect_y", True)):
        dy = 0.0
    if not bool(d.get("affect_rotate", True)):
        drot = 0.0
    if not bool(d.get("affect_length", True)):
        dlen = 0.0
    return dx, dy, drot, dlen


def _local_point_for_disp(pt, frame):
    """Object/local coords for sampling: relative to OBB frame when available."""
    if not frame:
        return float(pt[0]), float(pt[1])
    cx, cy = float(frame.get("cx", 0.0)), float(frame.get("cy", 0.0))
    ux, uy = frame.get("u", (1.0, 0.0))
    vx, vy = frame.get("v", (0.0, 1.0))
    dx = float(pt[0]) - cx
    dy = float(pt[1]) - cy
    return dx * float(ux) + dy * float(uy), dx * float(vx) + dy * float(vy)


def _displacement_preview_polyline(disp, n=240):
    """Point-based displacement preview: show a noise-driven offset curve."""
    d = _merge_displacement_style(disp if isinstance(disp, dict) else {})
    pts = []
    size_ref = 100.0
    for i in range(n + 1):
        s = i / n
        dx, dy, drot, dlen = _spatial_displacement_field(d, s, size_ref)
        v = (dx + dy * 0.5) / max(1e-6, (abs(float(d.get("location", 0) or 0)) * size_ref * 0.02 * 1.5) or 1.0)
        v = max(-1.0, min(1.0, v))
        pts.append((s, v))
    return pts


def _distortion_style_preview_polyline(style):
    if isinstance(style, dict) and style.get("type") == "displacement":
        return _displacement_preview_polyline(style)
    return _wave_preview_polyline(style if isinstance(style, dict) else {})


def _apply_spatial_displacements_to_segs(stroke, comp_index, base_segs, styles):
    """Apply point-based displacement styles to bezier segs non-destructively."""
    if not base_segs:
        return list(base_segs)
    frame, size_ref = _disp_frame_and_size(stroke, base_segs)

    segs = [list(s) for s in base_segs]
    ranges = _component_ranges(stroke)
    s0 = ranges[comp_index][0] if 0 <= comp_index < len(ranges) else 0
    closed = _is_closed_segs(base_segs)
    all_segs_stroke = segs_of(stroke)
    stroke_closed = _is_closed_segs(all_segs_stroke)
    ncomps = len(ranges) if ranges else len(_stroke_components(stroke))
    pin_start_edge = (comp_index == 0 and not stroke_closed)
    pin_end_edge = (comp_index == max(0, ncomps - 1) and not stroke_closed)
    n = len(segs)
    anchors = []
    for i in range(n):
        if i == 0:
            anchors.append((i, "p0"))
        anchors.append((i, "p3"))

    processed = set()
    for li, aname in anchors:
        gi = s0 + li
        key = (gi, aname)
        if aname == "p0" and li > 0:
            continue
        if aname == "p0" and li == 0 and closed and n > 1:
            continue
        # keep open-curve edge anchors and their attached handles completely fixed
        if (pin_start_edge and li == 0 and aname == "p0") or (pin_end_edge and li == n - 1 and aname == "p3"):
            processed.add(key)
            continue
        if key in processed:
            continue

        aj = 0 if aname == "p0" else 3
        base_pt = tuple(segs[li][aj])
        lx, ly = _local_point_for_disp(base_pt, frame)
        aparam = (li / max(1, n)) if aname == "p0" else ((li + 1) / max(1, n))
        aparam = max(0.0, min(1.0, float(aparam)))
        total_dx = total_dy = total_drot = total_dlen = 0.0
        for sv in styles:
            dx, dy, drot, dlen = _spatial_displacement_field(sv, aparam, size_ref)
            total_dx += dx; total_dy += dy; total_drot += drot; total_dlen += dlen
        # Apply displacement in object-local frame so it rotates with the object.
        if isinstance(frame, dict):
            ux, uy = frame.get("u", (1.0, 0.0))
            vx, vy = frame.get("v", (0.0, 1.0))
            wdx = total_dx * float(ux) + total_dy * float(vx)
            wdy = total_dx * float(uy) + total_dy * float(vy)
            total_dx, total_dy = wdx, wdy
        # Displacement affects handles, not anchor positions.
        new_anchor = base_pt

        if aname == "p0":
            h = segs[li][1]
            segs[li][0] = new_anchor
            segs[li][1] = (h[0] + total_dx, h[1] + total_dy)
            if li > 0:
                h2 = segs[li - 1][2]
                segs[li - 1][3] = new_anchor
                segs[li - 1][2] = (h2[0] + total_dx, h2[1] + total_dy)
            elif closed and n > 1:
                h2 = segs[-1][2]
                segs[-1][3] = new_anchor
                segs[-1][2] = (h2[0] + total_dx, h2[1] + total_dy)
        else:
            h = segs[li][2]
            segs[li][3] = new_anchor
            segs[li][2] = (h[0] + total_dx, h[1] + total_dy)
            if li < n - 1:
                h2 = segs[li + 1][1]
                segs[li + 1][0] = new_anchor
                segs[li + 1][1] = (h2[0] + total_dx, h2[1] + total_dy)
            elif closed and n > 1:
                h2 = segs[0][1]
                segs[0][0] = new_anchor
                segs[0][1] = (h2[0] + total_dx, h2[1] + total_dy)

        try:
            corner = is_corner_anchor(stroke, gi, aname)
        except Exception:
            corner = False
        if not corner:
            slots = _anchor_handle_slots(segs, li, aname, closed)
            if len(slots) >= 2:
                (s1, h1name), (s2, h2name) = slots[0], slots[1]
                j1 = 1 if h1name == "c1" else 2
                j2 = 1 if h2name == "c1" else 2
                hx = segs[s1][j1][0] - new_anchor[0]
                hy = segs[s1][j1][1] - new_anchor[1]
                hl = math.hypot(hx, hy)
                if hl > 1e-6:
                    ang = math.atan2(hy, hx) + total_drot
                    nl = max(0.05, hl * (1.0 + total_dlen))
                    nh = (new_anchor[0] + math.cos(ang) * nl, new_anchor[1] + math.sin(ang) * nl)
                    segs[s1][j1] = nh
                    segs[s2][j2] = _mirror_handle(new_anchor, nh)
        processed.add(key)
        if aname == "p3" and li < n - 1:
            processed.add((s0 + li + 1, "p0"))
        if aname == "p3" and li == n - 1 and closed and n > 1:
            processed.add((s0, "p0"))
        if aname == "p0" and li > 0:
            processed.add((s0 + li - 1, "p3"))
        if aname == "p0" and li == 0 and closed and n > 1:
            processed.add((s0 + n - 1, "p3"))

    return [tuple(s) for s in segs]


def _prepare_displacement_evaluator(d, geom=None):
    # legacy API shim; spatial displacement is applied as geometry transform
    return {"kind": "displacement", "style": _merge_displacement_style(d if isinstance(d, dict) else {})}

def _disp_frame_and_size(stroke, base_segs):
    """Object/local frame and size reference for point-based displacement."""
    try:
        obb = get_stroke_obb(stroke) if isinstance(stroke, dict) else None
    except Exception:
        obb = None
    frame = None
    size_ref = 1.0
    if isinstance(obb, dict):
        cx = float(obb.get("cx", 0.0)); cy = float(obb.get("cy", 0.0))
        hw = float(obb.get("hw", 0.0)); hh = float(obb.get("hh", 0.0))
        ang = float(obb.get("angle", 0.0) or 0.0)
        # If stored OBB is axis-aligned but geometry is rotated (common after
        # ops that recompute AABB), prefer min-area OBB from segs for a stable
        # object frame so displacement doesn't "animate" during rotation.
        if abs(ang) < 1e-6:
            try:
                pts_for_obb = [pt for seg in (base_segs or []) for pt in seg]
                mobb = _min_area_obb(pts_for_obb) if len(pts_for_obb) >= 3 else None
                if isinstance(mobb, dict):
                    mang = float(mobb.get("angle", 0.0) or 0.0)
                    mhw = float(mobb.get("hw", hw)); mhh = float(mobb.get("hh", hh))
                    # Canonicalize min-area OBB to stable axis: keep angle in (-45,45]
                    while mang <= -math.pi / 4.0 - 1e-9:
                        mang += math.pi / 2.0
                        mhw, mhh = mhh, mhw
                    while mang > math.pi / 4.0 + 1e-9:
                        mang -= math.pi / 2.0
                        mhw, mhh = mhh, mhw
                    if abs(mang) > 1e-3:
                        cx = float(mobb.get("cx", cx)); cy = float(mobb.get("cy", cy))
                        hw, hh, ang = mhw, mhh, mang
            except Exception:
                pass
        ca, sa = math.cos(ang), math.sin(ang)
        u, v = (ca, sa), (-sa, ca)
        size_ref = max(1.0, 2.0 * math.hypot(hw, hh))
        frame = {"cx": cx, "cy": cy, "u": u, "v": v}
    if frame is None:
        pts = [pt for seg in (base_segs or []) for pt in seg]
        if pts:
            try:
                mobb = _min_area_obb(pts) if len(pts) >= 3 else None
            except Exception:
                mobb = None
            if isinstance(mobb, dict):
                mang = float(mobb.get("angle", 0.0) or 0.0)
                mhw = float(mobb.get("hw", 0.0)); mhh = float(mobb.get("hh", 0.0))
                while mang <= -math.pi / 4.0 - 1e-9:
                    mang += math.pi / 2.0
                    mhw, mhh = mhh, mhw
                while mang > math.pi / 4.0 + 1e-9:
                    mang -= math.pi / 2.0
                    mhw, mhh = mhh, mhw
                ca, sa = math.cos(mang), math.sin(mang)
                frame = {"cx": float(mobb.get("cx", 0.0)), "cy": float(mobb.get("cy", 0.0)), "u": (ca, sa), "v": (-sa, ca)}
                size_ref = max(1.0, 2.0 * math.hypot(mhw, mhh))
            else:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                cx = (min(xs) + max(xs)) * 0.5; cy = (min(ys) + max(ys)) * 0.5
                size_ref = max(1.0, math.hypot(max(xs) - min(xs), max(ys) - min(ys)))
                frame = {"cx": cx, "cy": cy, "u": (1.0, 0.0), "v": (0.0, 1.0)}
        else:
            frame = {"cx": 0.0, "cy": 0.0, "u": (1.0, 0.0), "v": (0.0, 1.0)}
            size_ref = 1.0
    return frame, size_ref


def _distortion_sample_steps(segs, lengths, total, seg_samples, wave_evaluators):
    SAMPLES_PER_CYCLE = 32
    SAMPLES_PER_NOISE_CELL = 8
    needed = 8
    for ev in wave_evaluators.values():
        needed = max(needed, int(math.ceil(abs(ev.get("cycles", 0.0)) * SAMPLES_PER_CYCLE)) + 8)
        if ev.get("shape") == "noise" or ev.get("noise", 0.0) != 0.0:
            noise_cells = max(1.0, abs(ev.get("cycles", 0.0))) * 4.0 * max(0.1, ev.get("noise_scale", 2.0))
            needed = max(needed, int(math.ceil(noise_cells * SAMPLES_PER_NOISE_CELL)) + 8)
        if ev.get("shape") == "repeat":
            rpts = ev.get("repeat_points") or []
            needed = max(needed, int(math.ceil(abs(ev.get("cycles", 0.0)) * max(16, len(rpts) * 2))) + 8)
    fixed_total = seg_samples * max(1, len(segs))
    needed_total = min(max(fixed_total, needed), 8192)
    steps_list = []
    for _l in lengths:
        frac = (_l / total) if total > 0 else (1.0 / max(1, len(lengths)))
        steps_list.append(max(4, int(round(needed_total * frac))))
    return steps_list


def _sample_base_component(segs, lengths, total, steps_list, seg_samples, disp_frame):
    base_pts, base_s, base_local = [], [], []
    cum = 0.0
    for si, (p0, c1, c2, p3) in enumerate(segs):
        seg_len = lengths[si] if si < len(lengths) else 0.0
        start_s = cum / total
        end_s = (cum + seg_len) / total if total > 0 else start_s
        steps = steps_list[si] if si < len(steps_list) else seg_samples
        for i in range(0 if si == 0 else 1, steps + 1):
            t = i / steps
            x, y = cubic_bezier_point(p0, c1, c2, p3, t)
            s = start_s + (end_s - start_s) * t
            base_pts.append((x, y))
            base_s.append(s)
            base_local.append(_local_point_for_disp((x, y), disp_frame))
        cum += seg_len
    return base_pts, base_s, base_local


def _distortion_normals(out):
    normals = []
    n = len(out)
    for i in range(n):
        if i == 0:
            dx = out[1][0] - out[0][0]; dy = out[1][1] - out[0][1]
        elif i == n - 1:
            dx = out[-1][0] - out[-2][0]; dy = out[-1][1] - out[-2][1]
        else:
            dx = out[i + 1][0] - out[i - 1][0]; dy = out[i + 1][1] - out[i - 1][1]
        ll = math.hypot(dx, dy)
        if ll < 1e-6:
            normals.append(normals[-1] if normals else (0.0, -1.0))
        else:
            normals.append((-dy / ll, dx / ll))
    for i in range(1, len(normals)):
        pxn, pyn = normals[i - 1]; nxn, nyn = normals[i]
        if pxn * nxn + pyn * nyn < 0:
            normals[i] = (-nxn, -nyn)
    return normals


def _rebuild_distortion_param(out, disp_frame):
    new_s = [0.0] * len(out)
    cuml = 0.0
    prev_pt = out[0]
    for k in range(1, len(out)):
        pt = out[k]
        cuml += math.hypot(pt[0] - prev_pt[0], pt[1] - prev_pt[1])
        new_s[k] = cuml
        prev_pt = pt
    if cuml > 1e-9:
        inv = 1.0 / cuml
        base_s = [v * inv for v in new_s]
    else:
        base_s = [i / max(1, len(out) - 1) for i in range(len(out))]
    base_local = [_local_point_for_disp(pt, disp_frame) for pt in out]
    return base_s, base_local, list(out)


def _apply_displacement_style(out, base_s, base_local, disp_frame, disp_size_ref, sv, pin_start_edge, pin_end_edge):
    new_out = []
    m = len(out)
    for i, (pt, loc, sparam) in enumerate(zip(out, base_local, base_s)):
        dx, dy, _drot, _dlen = _spatial_displacement_field(sv, sparam, disp_size_ref)
        if isinstance(disp_frame, dict):
            ux, uy = disp_frame.get("u", (1.0, 0.0))
            vx, vy = disp_frame.get("v", (0.0, 1.0))
            dx, dy = dx * float(ux) + dy * float(vx), dx * float(uy) + dy * float(vy)
        edge_w = 1.0
        if m > 1 and (pin_start_edge or pin_end_edge):
            if pin_start_edge and pin_end_edge:
                edge_t = min(i, m - 1 - i) / max(1, (m - 1) / 2.0)
            elif pin_start_edge:
                edge_t = i / (m - 1)
            else:
                edge_t = (m - 1 - i) / (m - 1)
            edge_w = edge_t * edge_t * (3.0 - 2.0 * edge_t)
        new_out.append((pt[0] + dx * edge_w, pt[1] + dy * edge_w))
    return new_out, True


def _downsample_repeat_points(rpts, cycles, phase):
    MAX_CYCLES, MAX_OUT, MAX_RPTS = 200, 4000, 256
    cycle_start = int(math.floor(-phase))
    cycle_end = int(math.ceil(cycles - phase))
    ncy = max(1, cycle_end - cycle_start)
    step_c = max(1, int(math.ceil(ncy / MAX_CYCLES)))
    rpts_use = rpts
    if len(rpts_use) > MAX_RPTS:
        step_p = max(1, int(math.ceil(len(rpts_use) / MAX_RPTS)))
        rpts_use = rpts_use[::step_p]
        if rpts_use[-1] != rpts[-1]:
            rpts_use.append(rpts[-1])
    est = ((ncy + step_c - 1) // step_c) * len(rpts_use)
    if est > MAX_OUT and len(rpts_use) > 2:
        step_p2 = max(1, int(math.ceil(est / MAX_OUT)))
        rpts_use = rpts_use[::step_p2]
        if len(rpts_use) < 2:
            rpts_use = rpts[:2]
    return rpts_use, cycle_start, cycle_end, step_c


def _apply_repeat_style(out, base_s, base_local, base_pts, disp_frame, ev):
    rpts = ev.get("repeat_points") or []
    cycles = float(ev.get("cycles", 0.0) or 0.0)
    if len(rpts) < 2 or cycles <= 1e-6 or len(out) < 2:
        return out, base_s, base_local, base_pts, False
    phase = float(ev.get("phase", 0.0) or 0.0) / 360.0
    rpts_use, cycle_start, cycle_end, step_c = _downsample_repeat_points(rpts, cycles, phase)
    path_pts, path_s = out, base_s
    normals = _distortion_normals(path_pts)
    path_nx = [n[0] for n in normals]
    path_ny = [n[1] for n in normals]
    amp_px = float(ev.get("amp_px", 0.0) or 0.0)
    reverse = bool(ev.get("reverse"))
    clamp_mode = ev.get("clamp", "none")
    new_out, j = [], 0
    npath = len(path_pts)
    for c in range(cycle_start, cycle_end + 1, step_c):
        base_c = c + phase
        for rp in rpts_use:
            try:
                pxp = float(rp[0]); pyp = float(rp[1])
            except Exception:
                continue
            if reverse:
                pyp = -pyp
            s_global = (base_c + pxp) / cycles
            if s_global < 0.0 or s_global > 1.0:
                continue
            while j < npath - 2 and path_s[j + 1] < s_global:
                j += 1
            while j > 0 and path_s[j] > s_global:
                j -= 1
            s0, s1p = path_s[j], path_s[j + 1]
            seg = s1p - s0
            tt = 0.0 if seg <= 1e-9 else max(0.0, min(1.0, (s_global - s0) / seg))
            p0, p1 = path_pts[j], path_pts[j + 1]
            x = p0[0] + (p1[0] - p0[0]) * tt
            y = p0[1] + (p1[1] - p0[1]) * tt
            nx = path_nx[j] + (path_nx[j + 1] - path_nx[j]) * tt
            ny = path_ny[j] + (path_ny[j + 1] - path_ny[j]) * tt
            nl = math.hypot(nx, ny)
            if nl > 1e-6:
                nx /= nl; ny /= nl
            off_n = amp_px * pyp
            if clamp_mode == "positive":
                off_n = max(0.0, off_n)
            elif clamp_mode == "negative":
                off_n = min(0.0, off_n)
            new_out.append((x + nx * off_n, y + ny * off_n))
    if len(new_out) < 2:
        return out, base_s, base_local, base_pts, False
    base_s, base_local, base_pts = _rebuild_distortion_param(new_out, disp_frame)
    return new_out, base_s, base_local, base_pts, True


def _apply_thickness_style(out, base_s, base_local, base_pts, disp_frame, ev):
    tpts = ev.get("thickness_points") or []
    if len(tpts) < 2 or len(out) < 2:
        return out, base_s, base_local, base_pts, True, False
    normals = _distortion_normals(out)
    amp_px = float(ev.get("amp_px", 0.0) or 0.0)
    reverse = bool(ev.get("reverse"))
    clamp_mode = ev.get("clamp", "none")
    top = []
    for pt, s, nrmv in zip(out, base_s, normals):
        prof = _thickness_profile_at(s, ev)
        if reverse:
            prof = -prof
        off_n = amp_px * prof
        if clamp_mode == "positive":
            off_n = max(0.0, off_n)
        elif clamp_mode == "negative":
            off_n = min(0.0, off_n)
        nx, ny = nrmv
        top.append((pt[0] + nx * off_n, pt[1] + ny * off_n))
    ribbon = list(out) + list(reversed(top))
    if len(ribbon) < 3:
        return out, base_s, base_local, base_pts, True, False
    base_s, base_local, base_pts = _rebuild_distortion_param(ribbon, disp_frame)
    return ribbon, base_s, base_local, base_pts, False, True


def _apply_wave_offset_style(out, base_s, ev):
    normals = _distortion_normals(out)
    new_out = []
    for pt, s, nrmv in zip(out, base_s, normals):
        x, y = pt
        nx, ny = nrmv
        contrib = ev.get("amp_px", 0.0) * _wave_value_for(ev, s)
        if ev.get("noise", 0.0) != 0.0:
            nz = _smooth_noise1d(s * ev.get("cycles", 0.0) * 4.0, seed=ev.get("seed", 0), scale=ev.get("noise_scale", 2.0))
            contrib += ev.get("noise_px", 0.0) * nz
        offset = _apply_wave_clamp(contrib, ev.get("clamp", "none"))
        new_out.append((x + nx * offset, y + ny * offset))
    return new_out


def _eval_distortion_style(out, base_s, base_local, base_pts, disp_frame, disp_size_ref,
                           ev, sv, pin_start_edge, pin_end_edge, pin_open_endpoints):
    stype = sv.get("type", "wave")
    if stype == "displacement":
        out, pin_open_endpoints = _apply_displacement_style(
            out, base_s, base_local, disp_frame, disp_size_ref, sv, pin_start_edge, pin_end_edge)
        return out, base_s, base_local, base_pts, pin_open_endpoints
    if ev is None:
        return out, base_s, base_local, base_pts, pin_open_endpoints
    shape = ev.get("shape")
    if shape == "repeat":
        out, base_s, base_local, base_pts, _ = _apply_repeat_style(out, base_s, base_local, base_pts, disp_frame, ev)
        return out, base_s, base_local, base_pts, pin_open_endpoints
    if shape == "thickness":
        out, base_s, base_local, base_pts, pin_open_endpoints, _ = _apply_thickness_style(
            out, base_s, base_local, base_pts, disp_frame, ev)
        return out, base_s, base_local, base_pts, pin_open_endpoints
    return _apply_wave_offset_style(out, base_s, ev), base_s, base_local, base_pts, pin_open_endpoints


def sample_distorted_component(stroke, comp_index, samples_per_seg=24):
    """Return sampled polyline points for a component with distortion styles applied.
    Styles are evaluated in stack order on the unbaked (evaluated) curve:
    - wave styles offset along curve normals
    - spatial displacement styles offset points in object space by a procedural field
    Non-destructive: base geometry remains unchanged."""
    comps = _stroke_components(stroke)
    if not (0 <= comp_index < len(comps)):
        return []
    comp = comps[comp_index]
    # Always sample from current stroke base geometry so distortion follows edits/transforms/redraws.
    ranges = _component_ranges(stroke)
    segs = []
    if 0 <= comp_index < len(ranges):
        s0, s1 = ranges[comp_index]
        segs = list(segs_of(stroke)[s0:s1])
    if not segs:
        segs = list(comp.get("segs") or [])
    if not segs:
        return []
    styles = [sv for sv in _get_distortion_styles(comp) if _distortion_style_active(sv)]
    if not styles:
        pts = []
        for si, (p0, c1, c2, p3) in enumerate(segs):
            if si == 0:
                pts.append(p0)
            steps = max(2, int(samples_per_seg))
            for i in range(1, steps + 1):
                pts.append(cubic_bezier_point(p0, c1, c2, p3, i / steps))
        return pts

    # approximate arc-length parameter for stable waves across segments
    seg_samples = max(4, int(samples_per_seg))
    lengths, total = [], 0.0
    for (p0, c1, c2, p3) in segs:
        prev, l = p0, 0.0
        for i in range(1, seg_samples + 1):
            pt = cubic_bezier_point(p0, c1, c2, p3, i / seg_samples)
            l += math.hypot(pt[0] - prev[0], pt[1] - prev[1])
            prev = pt
        lengths.append(l)
        total += l
    if total <= 1e-6:
        total = 1.0

    pts_for_diag = []
    for (p0, c1, c2, p3) in segs:
        pts_for_diag.extend((p0, c1, c2, p3))
    obb = _min_area_obb(pts_for_diag)
    if obb is not None:
        diag = 2.0 * math.hypot(float(obb.get("hw", 0.0)), float(obb.get("hh", 0.0)))
    else:
        xs = [p[0] for p in pts_for_diag] or [0.0]
        ys = [p[1] for p in pts_for_diag] or [0.0]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if diag <= 1e-6:
        diag = total
    geom = {"diag": diag, "length": total}
    disp_frame, disp_size_ref = _disp_frame_and_size(stroke, segs)

    wave_evaluators = {}
    for idx_s, sv in enumerate(styles):
        st = sv.get("type")
        if st == "wave":
            ev = _prepare_wave_evaluator(sv, geom); ev["kind"] = "wave"; wave_evaluators[idx_s] = ev
        elif st == "repeat":
            ev = _prepare_repeat_evaluator(sv, geom); ev["kind"] = "repeat"; wave_evaluators[idx_s] = ev
        elif st == "thickness":
            ev = _prepare_thickness_evaluator(sv, geom); ev["kind"] = "thickness"; wave_evaluators[idx_s] = ev

    steps_list = _distortion_sample_steps(segs, lengths, total, seg_samples, wave_evaluators)
    base_pts, base_s, base_local = _sample_base_component(segs, lengths, total, steps_list, seg_samples, disp_frame)
    if len(base_pts) < 2:
        return base_pts

    closed_comp = _is_closed_segs(segs)
    stroke_closed = _is_closed_segs(segs_of(stroke))
    pin_open_endpoints = True
    ncomps = len(ranges) if ranges else len(_stroke_components(stroke))
    pin_start_edge = (comp_index == 0 and not stroke_closed)
    pin_end_edge = (comp_index == max(0, ncomps - 1) and not stroke_closed)
    out = list(base_pts)
    for idx_s, sv in enumerate(styles):
        ev = wave_evaluators.get(idx_s)
        out, base_s, base_local, base_pts, pin_open_endpoints = _eval_distortion_style(
            out, base_s, base_local, base_pts, disp_frame, disp_size_ref,
            ev, sv, pin_start_edge, pin_end_edge, pin_open_endpoints)

    if out and segs and not closed_comp and pin_open_endpoints:
        out[0] = tuple(segs[0][0])
        out[-1] = tuple(segs[-1][3])
    return out


def _component_distorted_polyline(stroke, comp_index, samples_per_seg=24):
    comps = _stroke_components(stroke)
    if not (0 <= comp_index < len(comps)):
        return []
    comp = comps[comp_index]
    if not _component_wave_enabled(comp):
        return []
    return sample_distorted_component(stroke, comp_index, samples_per_seg=samples_per_seg)


def component_display_segs(stroke, comp_index):
    """Return bezier segs for a component with active spatial (geometry) displacement
    applied for display/edit-view purposes. Returns None when no spatial displacement
    is active (caller should use base segs)."""
    try:
        comps = _stroke_components(stroke)
        if not (0 <= comp_index < len(comps)):
            return None
        comp = comps[comp_index]
        styles = [sv for sv in _get_distortion_styles(comp) if _distortion_style_active(sv) and sv.get("type") == "displacement"]
        if not styles:
            return None
        ranges = _component_ranges(stroke)
        if 0 <= comp_index < len(ranges):
            s0, s1 = ranges[comp_index]
            base_segs = list(segs_of(stroke)[s0:s1])
        else:
            base_segs = list(comp.get("segs") or [])
        if not base_segs:
            return None
        return _apply_spatial_displacements_to_segs(stroke, comp_index, base_segs, styles)
    except Exception:
        return None


def stroke_display_segs(stroke):
    """Return full stroke seg list with spatial displacement applied per component
    where active. Used for showing 'unbaked' displaced nodes/handles in edit views."""
    try:
        base = list(segs_of(stroke))
        if not base:
            return base
        comps = _stroke_components(stroke)
        ranges = _component_ranges(stroke)
        if not comps or not ranges:
            return base
        out = list(base)
        changed = False
        for ci, (s0, s1) in enumerate(ranges):
            dsegs = component_display_segs(stroke, ci)
            if dsegs is None:
                continue
            # only replace if lengths match
            if len(dsegs) == (min(s1, len(base)) - s0):
                out[s0:s1] = list(dsegs)
                changed = True
        return out if changed else base
    except Exception:
        return list(segs_of(stroke))


def bake_component_distortion(stroke, comp_index, samples_per_seg=24):
    """Bake distortion styles (wave/displacement) into a component's base bezier geometry.

    Evaluates the component's distortion stack on the unbaked curve (same as rendering
    evaluation), fits the resulting sampled shape back to bezier segments, replaces the
    component's segs/raw_points, and removes distortion styles so the effect becomes
    permanent base geometry. Returns a new stroke dict, or the original stroke if baking
    is not applicable.
    """
    if not isinstance(stroke, dict):
        return stroke
    try:
        comps = _stroke_components(stroke)
        ranges = _component_ranges(stroke)
        if not (0 <= comp_index < len(comps)) or comp_index >= len(ranges):
            return stroke
        comp = comps[comp_index]
        if not _component_wave_enabled(comp):
            return stroke
        baked_pts = sample_distorted_component(stroke, comp_index, samples_per_seg=samples_per_seg)
        if not baked_pts or len(baked_pts) < 2:
            return stroke

        s0, s1 = ranges[comp_index]
        all_segs = list(segs_of(stroke))
        base_comp_segs = list(all_segs[s0:s1]) if s1 > s0 else list(comp.get("segs") or [])
        was_closed = _is_closed_segs(base_comp_segs)

        raw_points = [tuple(p) for p in baked_pts]
        # For closed components, drop duplicate closing sample to avoid zero-length/degenerate fit.
        if was_closed and len(raw_points) >= 2 and math.hypot(raw_points[0][0] - raw_points[-1][0], raw_points[0][1] - raw_points[-1][1]) < 1e-3:
            raw_points = raw_points[:-1]
        if len(raw_points) < 2:
            return stroke

        max_pts = int(comp.get("draw_max_points", 4) or 4)
        algorithm = comp.get("algorithm", stroke.get("algorithm", "fit"))
        new_segs = stroke_to_beziers(
            raw_points, simplify_epsilon=2.5, tension=0.0,
            max_points=max(2, max_pts), algorithm=algorithm,
        )
        if not new_segs:
            return stroke
        new_segs = [tuple(s) for s in new_segs]

        # Preserve connectivity at component boundaries (adjacent components / open ends).
        n_old = len(all_segs)
        start_corner = is_corner_anchor(stroke, s0, "p0") if s0 < n_old else False
        end_corner = is_corner_anchor(stroke, s1 - 1, "p3") if (s1 - 1) < n_old and s1 > s0 else False
        if s0 > 0 and new_segs:
            prev_end = all_segs[s0 - 1][3]
            ns = list(new_segs[0]); ns[0] = tuple(prev_end); new_segs[0] = tuple(ns)
        if s1 < n_old and new_segs:
            next_start = all_segs[s1][0]
            ns = list(new_segs[-1]); ns[3] = tuple(next_start); new_segs[-1] = tuple(ns)
        # Closed component spanning whole stroke seam.
        if s0 == 0 and s1 == n_old and was_closed and len(new_segs) >= 1:
            ns = list(new_segs[-1]); ns[3] = tuple(new_segs[0][0]); new_segs[-1] = tuple(ns)

        delta = len(new_segs) - (s1 - s0)
        old_corners = set(_corners(stroke))
        new_corners = set()
        for (si, name) in old_corners:
            if si < s0:
                new_corners.add((si, name))
            elif si >= s1:
                new_corners.add((si + delta, name))
            else:
                if si == s0 and name == "p0" and start_corner:
                    new_corners.add((s0, "p0"))
                elif si == s1 - 1 and name == "p3" and end_corner:
                    new_corners.add((s0 + len(new_segs) - 1, "p3"))

        all_segs[s0:s1] = list(new_segs)
        out = _copy_stroke(stroke)
        out["segs"] = all_segs
        out["corner_anchors"] = new_corners

        comps2 = _stroke_components(out)
        if 0 <= comp_index < len(comps2):
            new_comp = dict(comps2[comp_index])
            new_comp["segs"] = list(new_segs)
            new_comp["raw_points"] = raw_points
            # remove distortion styles (baked into geometry)
            kept_styles = [s for s in _component_styles(new_comp) if not _is_distortion_style(s)]
            if kept_styles:
                new_comp["styles"] = kept_styles
            else:
                new_comp.pop("styles", None)
            new_comp.pop("wave", None)
            comps2[comp_index] = new_comp
        out["components"] = comps2
        # structural change: clear hidden segs for simplicity
        out["hidden_segs"] = set()
        try:
            out["obb"] = compute_stroke_obb(out)
        except Exception:
            pass
        return out
    except Exception:
        return stroke

