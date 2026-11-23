import ast, os
path='src/controllers/mouse_button_down_panel.py'
src=open(path,encoding='utf-8').read()
lines=src.splitlines(keepends=True)
t=ast.parse(src)
funcs=[(n.name,n.lineno-1,n.end_lineno) for n in ast.iter_child_nodes(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
header=['"""Panel click helpers (split for SRP)."""\n','import copy, math, pygame\n','import config as cfg\n','from models import *\n','from views import *\n','from controllers.coordinates import *\n','\n']
move={'_handle_panel_click_a':'src/controllers/mbd_panel_a.py','_handle_panel_click_b':'src/controllers/mbd_panel_b.py','_handle_panel_click_c':'src/controllers/mbd_panel_c.py'}
moved=set()
for name,s,e in funcs:
    if name in move:
        mod=header[:]+[f'# {name}\n\n']
        mod.extend(lines[s:e])
        with open(move[name],'w',encoding='utf-8') as f: f.writelines(mod)
        for i in range(s,e): moved.add(i)
new=[]
for i,l in enumerate(lines):
    if i in moved: continue
    new.append(l)
last_imp=0
for i,l in enumerate(new):
    if l.startswith('import ') or l.startswith('from '): last_imp=i
for name in ['_handle_panel_click_c','_handle_panel_click_b','_handle_panel_click_a']:
    mod=move[name].replace('/','.').replace('\\','.')
    if mod.endswith('.py'): mod=mod[:-3]
    if mod.startswith('src.'): mod=mod[4:]
    new.insert(last_imp+1, f'from {mod} import {name}\n')
with open(path,'w',encoding='utf-8') as f: f.writelines(new)
print('ok')
