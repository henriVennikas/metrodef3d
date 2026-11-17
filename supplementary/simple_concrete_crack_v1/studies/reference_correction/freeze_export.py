"""Freeze exact current exporter functions for a reproducible correction study."""
import ast,hashlib,json,argparse
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--generator-root',type=Path,required=True);a=p.parse_args();here=Path(__file__).resolve().parent;source=a.generator_root/'src/metrodef3d/render.py';tree=ast.parse(source.read_text());template=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BLENDER_SCRIPT_TEMPLATE' for t in n.targets));funcs={n.name:n for n in ast.parse(template).body if isinstance(n,ast.FunctionDef)};needed=set()
 def follow(name):
  if name in needed:return
  needed.add(name)
  for n in ast.walk(funcs[name]):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in funcs:follow(n.func.id)
 for n in ['configure_camera','write_visible_defect']:follow(n)
 init=ast.parse((a.generator_root/'src/metrodef3d/__init__.py').read_text());schema=next(ast.literal_eval(n.value) for n in init.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VISIBLE_DEFECT_SCHEMA_VERSION' for t in n.targets));assert schema==2
 code='"""Frozen corrected production functions; see source_manifest.json."""\nimport json, math\nimport bpy\nfrom bpy_extras.object_utils import world_to_camera_view\nfrom mathutils import Vector\nVERSIONING={"visible_defect_schema_version":2}\n\n'+'\n\n'.join(ast.get_source_segment(template,n) for n in ast.parse(template).body if isinstance(n,ast.FunctionDef) and n.name in needed)+'\n'
 path=here/'corrected_export.py';assert not path.exists();path.write_text(code)
 (here/'source_manifest.json').write_text(json.dumps(dict(schema_version=2,reference_revision='component-aware-2',production_source='src/metrodef3d/render.py',production_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),extracted_sha256=hashlib.sha256(code.encode()).hexdigest(),functions=sorted(needed)),indent=2)+'\n')
 print('Frozen',len(needed),'corrected functions')
if __name__=='__main__':main()
