"""Execute frozen production sidecar export in Blender; no rendering or fitting."""
import sys,json,traceback,hashlib,ast
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import production_export as prod
cases=json.loads((HERE/'fixtures.json').read_text());results=[]
out=HERE/'results';out.mkdir(exist_ok=True)

def evaluate(case,tag,namespace):
    camdef=case['camera'];scene=bpy.context.scene
    scene.render.resolution_x=camdef['resolution'][0];scene.render.resolution_y=camdef['resolution'][1];scene.render.resolution_percentage=100
    scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
    cam=namespace['configure_camera'](camdef,tag)
    path=out/(tag+'.json');row=dict(id=tag,fixture=case['id'],group=case['group'])
    try:
        namespace['write_visible_defect'](str(path),scene,cam,case['defect'],camdef)
        record=json.loads(path.read_text());row.update(status='ok',measurands=record['measurands'])
    except Exception as e:
        row.update(status='exception',exception_type=type(e).__name__,message=str(e))
    bpy.data.objects.remove(cam,do_unlink=True)
    return row

for c in cases:results.append(evaluate(c,c['id'],vars(prod)))
# In-memory numerical sensitivity copies only. Original source remains untouched.
source=(HERE/'production_export.py').read_text()
base=next(c for c in cases if c['id']=='tilt15_fov100_angle37')
for tol in [1e-8,1e-10,1e-12,1e-14]:
    tree=ast.parse(source);count=0
    class Change(ast.NodeTransformer):
        def visit_FunctionDef(self,n):
            if n.name not in ['clip_unit_square_interval','uv_intersection']:return n
            return self.generic_visit(n)
        def visit_Constant(self,n):
            global count
            if isinstance(n.value,float) and n.value==1e-12:count+=1;return ast.copy_location(ast.Constant(tol),n)
            return n
    tree=Change().visit(tree);ast.fix_missing_locations(tree);ns={};exec(compile(tree,'tolerance_diagnostic','exec'),ns)
    c=dict(base,group='tolerance');r=evaluate(c,f'tolerance_{tol}',ns);r['tolerance']=tol;r['changed_constants']=count;results.append(r)
(out/'runs.json').write_text(json.dumps(dict(blender_version=bpy.app.version_string,rows=results),indent=2)+'\n')
print('REFERENCE_VALIDATION_COMPLETE',len(results),'cases',sum(r['status']=='exception' for r in results),'exceptions retained')
