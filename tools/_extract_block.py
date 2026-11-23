import ast, re, sys, os

src_path, start_s, end_s, out_path, func_name, skip_first = sys.argv[1:7]
start = int(start_s) - 1
end = int(end_s) - 1
skip_first = skip_first == '1'

src = open(src_path, encoding='utf-8').read()
lines = src.splitlines(keepends=True)
block = lines[start:end]

# detect base indent
base_indent = 12
for l in block:
    if l.strip():
        base_indent = len(l) - len(l.lstrip(' '))
        break

dedented = []
for l in block:
    if l.startswith(' ' * base_indent):
        dedented.append(l[base_indent:])
    elif l.strip() == '':
        dedented.append('\n')
    else:
        dedented.append(l.lstrip(' '))

if skip_first and dedented:
    dedented = dedented[1:]

wrapped2 = 'if True:\n' + ''.join('    ' + l if l.strip() else l for l in dedented)
t = ast.parse(wrapped2)

loop_nodes = (ast.For, ast.While, ast.AsyncFor)
continue_lines = set()
class Finder(ast.NodeVisitor):
    def __init__(self): self.loop_depth = 0
    def visit_For(self, n): self.loop_depth += 1; self.generic_visit(n); self.loop_depth -= 1
    def visit_While(self, n): self.loop_depth += 1; self.generic_visit(n); self.loop_depth -= 1
    def visit_AsyncFor(self, n): self.loop_depth += 1; self.generic_visit(n); self.loop_depth -= 1
    def visit_Continue(self, n):
        if self.loop_depth == 0: continue_lines.add(n.lineno)
Finder().visit(t)

new_dedented = []
for i, l in enumerate(dedented):
    wline = i + 2
    if wline in continue_lines:
        indent = len(l) - len(l.lstrip(' '))
        new_dedented.append(l[:indent] + "return 'continue'\n")
    else:
        new_dedented.append(l)

t2 = ast.parse('if True:\n' + ''.join('    ' + l if l.strip() else l for l in new_dedented))
assigned = set()
class V(ast.NodeVisitor):
    def visit_Name(self, n):
        if isinstance(n.ctx, (ast.Store, ast.Del)): assigned.add(n.id)
    def visit_arg(self, n): assigned.add(n.arg)
    def visit_FunctionDef(self, n): assigned.add(n.name); self.generic_visit(n)
    def visit_AsyncFunctionDef(self, n): assigned.add(n.name); self.generic_visit(n)
V().visit(t2)

outside = ''.join(lines[:start] + lines[end:])
sync = []
for n in sorted(assigned):
    if n.startswith('__'): continue
    if re.search(r'\b' + re.escape(n) + r'\b', outside):
        sync.append(n)

critical = {'strokes','selected_strokes','selected_point','selected_curve','selected_curves',
 'drawing','current_points','cut_points','cutting','drag_last','transform_drag','gradient_drag',
 'marquee_select','pending_transform_toggle','pivot_drag','pan_drag','ref_drag','guide_drag',
 'guides','bezier_pen','text_entry','tool_mode','draw_tool','draw_shape','workspace',
 'panel_collapsed','help_open','menu_open','export_dialog_open','export_dialog_format',
 'export_dpi','export_scale','eyedropper_pick','snap_enabled','selection_submode',
 'redrawing_curve','curve_cut_mode','smart_snap_guides','shape_menu_key','shape_menu_anchor',
 'reference_image','reference_error','bucket_picker_drag','obj_opacity_drag','ref_opacity_drag',
 'fill_stop_pos_drag','picker_drag_sv','picker_drag_hue','picker_drag_alpha','wave_slider_drag',
 'wave_custom_drag','wave_formula_focus','max_points_per_curve','bucket_fill_color',
 'color_target','picker_h','picker_s','picker_v','xform_field_focus','xform_field_buffer',
 'pivot_pos','_bezier_last_click','repeat_pick_mode','repeat_pick_target','space_panning',
 'running','state','screen','clock'}
for c in critical:
    if c not in sync and re.search(r'\b'+re.escape(c)+r'\b', outside):
        sync.append(c)
sync = sorted(set(sync))
temps = {'_','_rs','_si','_draw_keys','_gfg','_gsi','_gst'}
sync_filtered = [n for n in sync if n in critical or n not in temps]

read_names = set()
class R(ast.NodeVisitor):
    def visit_Name(self, n):
        if isinstance(n.ctx, ast.Load): read_names.add(n.id)
R().visit(t2)
ctx_names = set(sync_filtered)
for n in read_names:
    if re.search(r'\b' + re.escape(n) + r'\b', outside):
        ctx_names.add(n)
skip = {'True','False','None','print','len','range','min','max','abs','int','float','str','bool',
 'list','dict','set','tuple','sorted','reversed','enumerate','zip','any','all','map','filter',
 'sum','round','isinstance','getattr','setattr','hasattr','type','super','object','Exception',
 'ValueError','TypeError','KeyError','IndexError','AttributeError','RuntimeError','NameError',
 'math','pygame','copy','cfg','event','ctx',func_name}
ctx_names -= skip

body_src = ''.join(new_dedented)
# dedent 4 for parsing
parse_lines = []
for l in body_src.splitlines(keepends=True):
    if l.startswith('    '): parse_lines.append(l[4:])
    elif l.strip() == '': parse_lines.append('\n')
    else: parse_lines.append(l)
parse_src = ''.join(parse_lines)
bt = ast.parse(parse_src)
local_defs = set()
for node in ast.iter_child_nodes(bt):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        local_defs.add(node.name)
ctx_names -= local_defs

replacements = []
class Rewriter(ast.NodeVisitor):
    def visit_Name(self, n):
        if n.id in ctx_names and hasattr(n, 'end_col_offset'):
            replacements.append((n.lineno-1, n.col_offset, n.end_col_offset, f'ctx.{n.id}'))
        self.generic_visit(n)
    def visit_Attribute(self, n):
        self.visit(n.value)
    def visit_FunctionDef(self, n):
        for d in n.decorator_list: self.visit(d)
        self.visit(n.args)
        for s in n.body: self.visit(s)
    def visit_arg(self, n): pass
Rewriter().visit(bt)

body_lines = parse_src.splitlines(keepends=True)
by_line = {}
for ln, c, ec, nt in replacements:
    by_line.setdefault(ln, []).append((c, ec, nt))
for ln, reps in by_line.items():
    reps.sort(key=lambda x: -x[0])
    line = body_lines[ln]
    for c, ec, nt in reps:
        line = line[:c] + nt + line[ec:]
    body_lines[ln] = line
# re-indent by 4 for function body
body_lines = [('    ' + l if l.strip() else '\n') for l in body_lines]

mod_lines = [f'"""Extracted handler: {func_name}."""\n',
 'import copy, math, pygame\n', 'import config as cfg\n',
 'from models import *\n', 'from views import *\n', 'from controllers.coordinates import *\n',
 '\n', f'def {func_name}(ctx, event=None):\n'] + body_lines + ['    return None\n']
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.writelines(mod_lines)

repl = [lines[start],
 '                import types as _types\n',
 '                _ex_ctx = _types.SimpleNamespace()\n',
 '                _ex_ctx.__dict__.update({k:v for k,v in locals().items()})\n']
mod_import = out_path.replace('/', '.').replace('\\', '.')
if mod_import.endswith('.py'): mod_import = mod_import[:-3]
if mod_import.startswith('src.'): mod_import = mod_import[4:]
repl.append(f'                from {mod_import} import {func_name} as _hf\n')
repl.append('                _ex_r = _hf(_ex_ctx, event)\n')
for n in sync_filtered:
    repl.append(f'                if hasattr(_ex_ctx, {n!r}): {n} = _ex_ctx.{n}\n')
repl.append("                if _ex_r == 'continue':\n")
repl.append('                    continue\n')

new_lines = lines[:start] + repl + lines[end:]
with open(src_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('SYNC', len(sync_filtered), 'OK')
