import ast, re, os
path='src/controllers/app_controller.py'
src=open(path,encoding='utf-8').read()
lines=src.splitlines(keepends=True)
start=1696-1  # 0-based
end=2027      # exclusive
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
critical={'strokes','selected_strokes','selected_point','selected_curve','selected_curves','drawing','current_points','redrawing_curve','tool_mode','selection_submode','workspace','shape_states','text_entry','picker_h','picker_s','picker_v','pivot_pos','state','color_target','screen','clock','render_strokes','text_preview_index','_eff_pivot','_grad_edit_info','guides','smart_snap_guides','active','running','cfg'}
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
skip={'True','False','None','print','len','range','min','max','abs','int','float','str','bool','list','dict','set','tuple','sorted','reversed','enumerate','zip','any','all','map','filter','sum','round','isinstance','getattr','setattr','hasattr','type','Exception','ValueError','TypeError','KeyError','IndexError','AttributeError','RuntimeError','math','pygame','copy','cfg','ctx','render_frame'}
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
mod=['"""Render frame (extracted for SRP)."""\n','import copy, math, pygame\n','import config as cfg\n','from models import *\n','from views import *\n','from controllers.coordinates import *\n','\n','def render_frame(ctx):\n']+body_lines+['    return None\n']
os.makedirs('src/controllers',exist_ok=True)
open('src/controllers/render_frame.py','w',encoding='utf-8').writelines(mod)
repl=['        # Render frame (extracted)\n','        import types as _types\n','        _rf_ctx=_types.SimpleNamespace()\n','        _rf_ctx.__dict__.update({k:v for k,v in locals().items()})\n','        from controllers.render_frame import render_frame as _rf\n','        _rf(_rf_ctx)\n']
for n in sync: repl.append(f'        if hasattr(_rf_ctx,{n!r}): {n}=_rf_ctx.{n}\n')
new_lines=lines[:start]+repl+lines[end:]
open(path,'w',encoding='utf-8').writelines(new_lines)
print('SYNC',len(sync))
