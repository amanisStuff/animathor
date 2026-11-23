import ast, re, os
path='src/controllers/app_controller.py'
src=open(path,encoding='utf-8').read()
lines=src.splitlines(keepends=True)
start=1228-1
end=1696-1  # before render
block=lines[start:end]
# dedent 8
dedented=[]
for l in block:
    if l.startswith('        '): dedented.append(l[8:])
    elif l.strip()=='': dedented.append('\n')
    else: dedented.append(l.lstrip(' '))
wrapped='if True:\n'+''.join('    '+l if l.strip() else l for l in dedented)
t=ast.parse(wrapped)
assigned=set()
class V(ast.NodeVisitor):
    def visit_Name(self,n):
        if isinstance(n.ctx,(ast.Store,ast.Del)): assigned.add(n.id)
    def visit_arg(self,n): assigned.add(n.arg)
    def visit_FunctionDef(self,n): assigned.add(n.name); self.generic_visit(n)
V().visit(t)
outside=''.join(lines[:start]+lines[end:])
sync=[n for n in sorted(assigned) if not n.startswith('__') and re.search(r'\b'+re.escape(n)+r'\b', outside)]
critical={'strokes','selected_strokes','selected_point','selected_curve','selected_curves','drawing','current_points','cut_points','cutting','drag_last','transform_drag','gradient_drag','marquee_select','pending_transform_toggle','pivot_drag','pan_drag','ref_drag','guide_drag','guides','bezier_pen','text_entry','tool_mode','draw_tool','draw_shape','workspace','panel_collapsed','help_open','menu_open','export_dialog_open','export_dialog_format','export_dpi','export_scale','eyedropper_pick','snap_enabled','selection_submode','redrawing_curve','curve_cut_mode','smart_snap_guides','shape_menu_key','shape_menu_anchor','reference_image','reference_error','bucket_picker_drag','obj_opacity_drag','ref_opacity_drag','fill_stop_pos_drag','picker_drag_sv','picker_drag_hue','picker_drag_alpha','wave_slider_drag','wave_custom_drag','wave_formula_focus','max_points_per_curve','bucket_fill_color','color_target','picker_h','picker_s','picker_v','xform_field_focus','xform_field_buffer','pivot_pos','_bezier_last_click','repeat_pick_mode','repeat_pick_target','space_panning','running','state','cfg','screen','clock'}
for c in critical:
    if c not in sync and re.search(r'\b'+re.escape(c)+r'\b', outside): sync.append(c)
sync=sorted(set(sync))
read_names=set()
class R(ast.NodeVisitor):
    def visit_Name(self,n):
        if isinstance(n.ctx,ast.Load): read_names.add(n.id)
R().visit(t)
ctx_names=set(sync)
for n in read_names:
    if re.search(r'\b'+re.escape(n)+r'\b', outside): ctx_names.add(n)
skip={'True','False','None','print','len','range','min','max','abs','int','float','str','bool','list','dict','set','tuple','sorted','reversed','enumerate','zip','any','all','map','filter','sum','round','isinstance','getattr','setattr','hasattr','type','Exception','ValueError','TypeError','KeyError','IndexError','AttributeError','RuntimeError','math','pygame','copy','cfg','ctx','process_events'}
ctx_names-=skip
body_src=''.join(dedented)
bt=ast.parse(body_src)
local_defs={n.name for n in ast.iter_child_nodes(bt) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
ctx_names-=local_defs
replacements=[]
class RW(ast.NodeVisitor):
    def visit_Name(self,n):
        if n.id in ctx_names and hasattr(n,'end_col_offset'):
            replacements.append((n.lineno-1,n.col_offset,n.end_col_offset,f'ctx.{n.id}'))
    def visit_Attribute(self,n): self.visit(n.value)
    def visit_FunctionDef(self,n):
        for d in n.decorator_list: self.visit(d)
        self.visit(n.args)
        for s in n.body: self.visit(s)
    def visit_arg(self,n): pass
RW().visit(bt)
body_lines=body_src.splitlines(keepends=True)
by={}
for ln,c,ec,nt in replacements: by.setdefault(ln,[]).append((c,ec,nt))
for ln,reps in by.items():
    reps.sort(key=lambda x:-x[0])
    line=body_lines[ln]
    for c,ec,nt in reps: line=line[:c]+nt+line[ec:]
    body_lines[ln]=line
body_lines=[('    '+l if l.strip() else '\n') for l in body_lines]
mod=['"""Event loop (extracted for SRP)."""\n','import copy, math, pygame\n','import config as cfg\n','from models import *\n','from views import *\n','from controllers.coordinates import *\n','\n','def process_events(ctx):\n']+body_lines+['    return None\n']
os.makedirs('src/controllers',exist_ok=True)
open('src/controllers/event_loop.py','w',encoding='utf-8').writelines(mod)
repl=['        # Event loop (extracted)\n','        import types as _types\n','        _ev_ctx=_types.SimpleNamespace()\n','        _ev_ctx.__dict__.update({k:v for k,v in locals().items()})\n','        from controllers.event_loop import process_events as _pe\n','        _pe(_ev_ctx)\n']
for n in sync: repl.append(f'        if hasattr(_ev_ctx,{n!r}): {n}=_ev_ctx.{n}\n')
new_lines=lines[:start]+repl+lines[end:]
open(path,'w',encoding='utf-8').writelines(new_lines)
print('SYNC',len(sync))
