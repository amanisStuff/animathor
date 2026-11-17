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
        "formula": "sin(x)",
        "custom_points": [],
    }

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
        d = default_wave_params()
        d.update({k: s0.get(k, d[k]) for k in d.keys() if k != "type"})
        d["type"] = "wave"
        out.append(d)
    return out

def _get_wave_style(component, index=0):
    styles = _get_wave_styles(component)
    if 0 <= index < len(styles):
        return styles[index]
    return default_wave_params()

def _set_wave_style(component, wave_style, index=0):
    if not isinstance(component, dict):
        return
    d = default_wave_params()
    if isinstance(wave_style, dict):
        d.update({k: wave_style.get(k, d[k]) for k in d.keys() if k != "type"})
    d["type"] = "wave"
    others = [dict(s0) for s0 in _component_styles(component) if not (isinstance(s0, dict) and s0.get("type") == "wave")]
    waves = [dict(s0) for s0 in _wave_style_raw_list(component)]
    while len(waves) <= index:
        waves.append(default_wave_params())
    waves[index] = d
    component["styles"] = others + waves
    # legacy single-wave key mirrors the first style for backward compatibility
    component["wave"] = {k: waves[0][k] for k in waves[0].keys() if k != "type"}

def _remove_wave_style(component, index=0):
    if not isinstance(component, dict):
        return
    others = [dict(s0) for s0 in _component_styles(component) if not (isinstance(s0, dict) and s0.get("type") == "wave")]
    waves = [dict(s0) for s0 in _wave_style_raw_list(component)]
    if waves:
        if 0 <= index < len(waves):
            del waves[index]
        else:
            waves.pop()
    component["styles"] = others + waves
    if waves:
        component["wave"] = {k: waves[0][k] for k in waves[0].keys() if k != "type"}
    else:
        component.pop("wave", None)

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

def _component_wave_enabled(component):
    return any(_wave_style_active(wv) for wv in _get_wave_styles(component))

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
    }
    ev["reverse"] = bool(w.get("reverse"))
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
    """Paint the waveform under the cursor (click-hold-drag inside the box).

    `drag` is [last_index, last_amplitude], or None when starting a stroke.
    Every sample between the previous and current column is filled so fast
    horizontal moves stay continuous, exactly like LMMS Bit Invader."""
    if not box or box.w <= 0 or box.h <= 0:
        return drag
    t = clamp((pos[0] - box.x) / max(1, box.w - 1), 0.0, 1.0)
    amp = clamp((pos[1] - (box.y + box.h / 2.0)) / max(1, box.h / 2.0), -1.0, 1.0)
    n = CUSTOM_WAVE_SAMPLES
    pts = w.get("custom_points")
    if not pts or len(pts) != n:
        # convert legacy sparse points (or empty) onto the uniform grid first
        pts = _custom_uniform_samples(pts)
        w["custom_points"] = pts
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
    """One normalized cycle of a wave style, for drawing shape thumbnail icons."""
    w = dict(wave) if isinstance(wave, dict) else {}
    w["frequency"] = 1.0
    w["phase"] = 0.0
    w["noise"] = 0.0
    ev = _prepare_wave_evaluator(w)
    pts = []
    for i in range(n + 1):
        s = i / n
        pts.append((s, _wave_value_for(ev, s)))
    return pts

def _wave_preview_polyline(wave, n=None):
    """Composed wave (amplitude/frequency/phase/noise) over the whole stroke,
    normalized to roughly [-1,1] for the live preview box."""
    ev = _prepare_wave_evaluator(wave if isinstance(wave, dict) else {})
    if n is None:
        # enough points to render every cycle and noise lattice cell smoothly
        cycles = abs(ev["cycles"])
        n = int(min(2400, max(240, cycles * 24)))
        if ev["shape"] == "noise" or ev["noise"] != 0.0:
            # noise needs several samples per lattice cell to look smooth
            noise_cells = max(1.0, cycles) * 4.0 * max(0.1, ev["noise_scale"])
            n = int(min(2400, max(n, noise_cells * 6)))
    pts = []
    for i in range(n + 1):
        s = i / n
        total = ev["amp"] * _wave_value_for(ev, s)
        if ev["noise"] != 0.0:
            nz = _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
            total += ev["noise"] * nz
        pts.append((s, total / 100.0))
    return pts

def sample_distorted_component(stroke, comp_index, samples_per_seg=24):
    """Return sampled polyline points for a component with wave distortion applied.
    Distortion is for rendering only; base geometry remains unchanged."""
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
    waves = [wv for wv in _get_wave_styles(comp) if _wave_style_active(wv)]
    if not waves:
        # no visible distortion: return dense samples of base for consistency? caller can choose; but return base polyline
        pts = []
        for si, (p0, c1, c2, p3) in enumerate(segs):
            if si == 0:
                pts.append(p0)
            steps = max(2, int(samples_per_seg))
            for i in range(1, steps + 1):
                pts.append(cubic_bezier_point(p0, c1, c2, p3, i / steps))
        return pts
    # approximate arc-length parameter for stable waves across segments
    # precompute cumulative lengths
    seg_samples = max(4, int(samples_per_seg))
    lengths = []
    total = 0.0
    for (p0, c1, c2, p3) in segs:
        prev = p0
        l = 0.0
        for i in range(1, seg_samples + 1):
            pt = cubic_bezier_point(p0, c1, c2, p3, i / seg_samples)
            l += math.hypot(pt[0] - prev[0], pt[1] - prev[1])
            prev = pt
        lengths.append(l)
        total += l
    if total <= 1e-6:
        total = 1.0

    # bounding box diagonal: frequency/amplitude are relative to the shape size.
    # Use oriented (min-area) bbox so rotation doesn't change the wave.
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

    # prepare each stacked wave style once; offsets are summed per sample
    evaluators = [_prepare_wave_evaluator(wv, geom) for wv in waves]
    # Per-evaluator sample requirements: 32 samples per wave cycle, plus 8
    # samples per noise lattice cell (cells = cycles * 4 * smoothing scale) for
    # the standalone noise shape and any legacy per-wave noise. The hungriest
    # style in the stack dictates the sample density.
    SAMPLES_PER_CYCLE = 32
    SAMPLES_PER_NOISE_CELL = 8
    needed = 8
    for ev in evaluators:
        needed = max(needed, int(math.ceil(abs(ev["cycles"]) * SAMPLES_PER_CYCLE)) + 8)
        if ev["shape"] == "noise" or ev["noise"] != 0.0:
            noise_cells = max(1.0, abs(ev["cycles"])) * 4.0 * max(0.1, ev["noise_scale"])
            needed = max(needed, int(math.ceil(noise_cells * SAMPLES_PER_NOISE_CELL)) + 8)

    # Adaptive sampling density: the wave phase advances cycles*tau across the
    # whole component, so a fixed samples_per_seg aliases into jagged zigzags
    # at high frequency. 'needed' (computed above) covers both cycles and
    # noise lattice cells for every style in the stack.
    fixed_total = seg_samples * max(1, len(segs))
    needed_total = min(max(fixed_total, needed), 8192)
    steps_list = []
    for _l in lengths:
        frac = (_l / total) if total > 0 else (1.0 / max(1, len(lengths)))
        steps_list.append(max(4, int(round(needed_total * frac))))

    # sample base points and tangents along whole component for stable normals
    base_pts = []
    base_s = []
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
        cum += seg_len
    if len(base_pts) < 2:
        return base_pts

    # compute normals from finite differences to avoid derivative singularities/flips
    normals = []
    n = len(base_pts)
    for i in range(n):
        if i == 0:
            dx = base_pts[1][0] - base_pts[0][0]
            dy = base_pts[1][1] - base_pts[0][1]
        elif i == n - 1:
            dx = base_pts[-1][0] - base_pts[-2][0]
            dy = base_pts[-1][1] - base_pts[-2][1]
        else:
            dx = base_pts[i + 1][0] - base_pts[i - 1][0]
            dy = base_pts[i + 1][1] - base_pts[i - 1][1]
        l = math.hypot(dx, dy)
        if l < 1e-6:
            # fallback to previous normal or arbitrary
            if normals:
                normals.append(normals[-1])
            else:
                normals.append((0.0, -1.0))
            continue
        normals.append((-dy / l, dx / l))

    # ensure normal consistency (avoid sudden flips)
    for i in range(1, len(normals)):
        px, py = normals[i - 1]
        nx, ny = normals[i]
        if px * nx + py * ny < 0:
            normals[i] = (-nx, -ny)


    out = []
    for i, (pt, s, nrmv) in enumerate(zip(base_pts, base_s, normals)):
        x, y = pt
        nx, ny = nrmv
        offset = 0.0
        for ev in evaluators:
            offset += ev["amp_px"] * _wave_value_for(ev, s)
            if ev["noise"] != 0.0:
                nz = _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
                offset += ev["noise_px"] * nz
        out.append((x + nx * offset, y + ny * offset))

    # Keep distorted curve endpoints exactly on the base/guide curve endpoints
    if out and segs:
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
