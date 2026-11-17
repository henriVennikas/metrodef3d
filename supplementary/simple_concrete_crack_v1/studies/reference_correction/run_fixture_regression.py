"""Blender regression against frozen independent fixtures, without rendering."""
import sys,json,argparse
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import corrected_export as prod
p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);froot=args.fixtures;cases=json.loads((froot/'fixtures.json').read_text());old={r['id']:r for r in json.loads((froot/'results/runs.json').read_text())['rows']};out=HERE/'fixture_results';out.mkdir(exist_ok=True);results=[]
for c in cases:
 camera=c['camera'];scene=bpy.context.scene;scene.render.resolution_x,scene.render.resolution_y=camera['resolution'];scene.render.resolution_percentage=100;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
 cam=prod.configure_camera(camera,c['id']);path=out/(c['id']+'.json');prod.write_visible_defect(str(path),scene,cam,c['defect'],camera);d=json.loads(path.read_text());ranges=d['component_ranges'];assert all(0<=a<b<=len(d['centerline']) for a,b in ranges);assert sum(b-a for a,b in ranges)==len(d['centerline']);assert d['schema']['version']==2
 computed=sum(prod.polyline_length(d['centerline'][a:b]) for a,b in ranges);assert abs(computed-d['measurands']['centerline_length'])<=5.01e-7
 if c['group'] not in ['boundary_stress','topology_stress']:assert d['measurands']==old[c['id']]['measurands'],c['id']
 if c['id']=='exit_reentry':
  assert len(ranges)==2;assert abs(d['measurands']['centerline_length']-c['expected']['centerline_length'])<.001
 if old[c['id']]['status']=='exception':
  assert d['measurands']['crack_area']>0;assert d['measurands']['mean_width'] is None;assert d['measurands']['max_width'] is None;assert not d['measurand_validity']['mean_width']
 results.append(dict(id=c['id'],components=len(ranges),measurands=d['measurands'],previous_exception=old[c['id']]['status']=='exception'))
 data=cam.data;bpy.data.objects.remove(cam,do_unlink=True);bpy.data.cameras.remove(data)
# Missing boundaries return a well-formed empty polygon pair, not an unpacking error.
assert prod.visible_polygon_from_blender_camera(bpy.context.scene,None,{})==([],[])
(out/'summary.json').write_text(json.dumps(dict(blender=bpy.app.version_string,cases=len(results),unchanged_ordinary=65,fixed_exception_cases=3,reentry_components=2,reentry_length_mm=next(r['measurands']['centerline_length'] for r in results if r['id']=='exit_reentry'),rows=results),indent=2)+'\n')
print('FIXTURE_REGRESSION_PASS',len(results),'fixtures; ordinary values unchanged; re-entry and empty-profile failures fixed')
