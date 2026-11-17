"""Verify unchanged source inputs and independently recompute annotation quantities."""
from pathlib import Path
import json,hashlib
import numpy as np
from reference_geometry import tests,project,chain,cross,crossings,sections
HERE=Path(__file__).resolve().parent
p=json.loads((HERE/'protocol.json').read_text());tests();checks=[]
redactions=json.loads((HERE/'redactions.json').read_text()) if (HERE/'redactions.json').exists() else {}
for path,expected in p['source_sha256'].items():
 rule=redactions.get(path)
 if rule:assert rule['original_sha256']==expected;expected=rule['redacted_sha256']
 assert hashlib.sha256((HERE/path).read_bytes()).hexdigest()==expected,path
for name in p['images']:
 d=HERE/'inputs'/name;a=json.loads((d/(name+'_annotation.json')).read_text());h=np.array(a['pixelToScannerMm'])
 with np.load(d/(name+'_scale.npz')) as z:
  np.testing.assert_array_equal(h,z['pixel_to_scanner_mm'])
  for key in ['scale_x_mm_per_px','scale_y_mm_per_px']:assert z[key].shape==(1024,1024) and np.isfinite(z[key]).all() and (z[key]>0).all()
 line=project(np.array(next(x['points'] for x in a['annotations'] if x['kind']=='centreline')),h);poly=project(np.array(next(x['points'] for x in a['annotations'] if x['kind']=='boundary')),h)
 assert not a['draft']['points'] and not crossings(poly)
 length=float(chain(line)[-1]);area=float(abs(cross(poly,np.roll(poly,-1,axis=0)).sum())/2);sec=sections(line,poly)
 actual=dict(centerline_length=length,crack_area=area,mean_width=area/length,max_width=sec['max_width_mm']);expected=json.loads((d/'reference.json').read_text())['reference']
 assert all(abs(actual[k]-expected[k])<1e-8 for k in actual)
 checks.append(dict(image=name,reference_recomputed=True,scale_homography_matches_annotation=True,positive_finite_scale=True,self_intersections=0,centreline_stations_outside_boundary=sec['outside_stations']))
(HERE/'input_verification.json').write_text(json.dumps(dict(checks=checks,frozen_source_files_unchanged=not bool(redactions),model_inputs_unchanged=True,documented_path_redactions=list(redactions)),indent=2)+'\n');print('Five annotation references and paired scale maps verified.')
