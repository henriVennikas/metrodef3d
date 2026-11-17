from pathlib import Path
import json,hashlib
import numpy as np
from reference_geometry import project,chain,cross,crossings,sections,tests
P=Path(__file__).resolve().parent
KEYS=['centerline_length','mean_width','max_width','crack_area']
def stats(x):
 return dict(n=len(x),mean=x.mean(0).tolist(),sample_sd=x.std(0,ddof=1).tolist(),relative_sd_percent=(100*x.std(0,ddof=1)/x.mean(0)).tolist(),u_mean_if_independent=(x.std(0,ddof=1)/len(x)**.5).tolist(),sample_covariance=np.cov(x,rowvar=False,ddof=1).tolist(),minimum=x.min(0).tolist(),maximum=x.max(0).tolist())
def main():
 tests();out={}
 for n,h in json.loads((P/'input_checksums.json').read_text()).items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 cal=json.loads((P/'inputs/calibration.json').read_text())['transformer']['corrected_refs_valid_cohort']
 for ident in ['IMG_8184','IMG_8162']:
  d=P/'inputs'/ident;H=np.array(json.loads((d/'preprocessing.json').read_text())['images'][0]['homography']);rows=[]
  for i in range(5):
   a=json.loads((d/f'annotation_{i}.json').read_text())
   line=project(np.array(next(t['points'] for t in a['annotations'] if t['kind']=='centreline')),H)
   poly=project(np.array(next(t['points'] for t in a['annotations'] if t['kind']=='boundary')),H)
   hits=crossings(poly);assert not hits,(ident,i,hits)
   L=float(chain(line)[-1]);A=float(abs(cross(poly,np.roll(poly,-1,axis=0)).sum())/2);sec=sections(line,poly)
   bad=[x['station_mm'] for x in sec['rows'] if not x['inside'] and x['station_mm']>.05 and L-x['station_mm']>.05]
   values=[L,A/L,sec['max_width_mm'],A]
   rows.append(dict(pass_index=i,role='adopted original' if i==0 else 'new repeat',values=dict(zip(KEYS,values)),boundary_points=len(poly),centreline_points=len(line),self_intersections=hits,interior_centreline_stations_outside=bad,section_diagnostics={k:v for k,v in sec.items() if k!='rows'}))
  x=np.array([[r['values'][k] for k in KEYS] for r in rows]);ref=json.loads((d/'reference.json').read_text())['reference'];np.testing.assert_allclose(x[0],[ref[k] for k in KEYS],rtol=0,atol=1e-9)
  pred=json.loads((d/'prediction.json').read_text())['predictions'];comparison={}
  for j,t in enumerate(KEYS):
   v=pred[t];m=v['mu'];lo=m-cal[t]*(m-v['lower']);hi=m+cal[t]*(v['upper']-m)
   comparison[t]=dict(prediction=m,calibrated_lower=lo,calibrated_upper=hi,original_reference=x[0,j],repeat_mean=x[:,j].mean(),signed_difference_from_mean_percent=100*(m-x[:,j].mean())/x[:,j].mean(),mean_within_bounds=bool(lo<=x[:,j].mean()<=hi),individual_annotations_within_bounds=int(sum((x[:,j]>=lo)&(x[:,j]<=hi))))
  out[ident]=dict(annotations=rows,five=stats(x),four_new=stats(x[1:]),original_minus_new_mean=(x[0]-x[1:].mean(0)).tolist(),transformer_comparison=comparison)
 prior=json.loads((P/'inputs/IMG_8579_reference_budget.json').read_text());x=np.array(prior['previous_annotation_values']);out['IMG_8579']=dict(five=stats(x),four_new=stats(x[1:]),scope='Earlier completed five-annotation study, prior fixed image scale, included for descriptive comparison only.')
 result=dict(quantities=KEYS,units=['mm','mm','mm','mm^2'],cases=out,limits=['Within-operator variability, not annotation accuracy or common bias.','Original and repeat annotations come from different sessions; five-pass statistics and four-new-only sensitivity are both reported.','s/sqrt(n) is conditional on independent repeats and applies to the mean, not a single annotation.','Do not pool images into a universal annotation uncertainty.','Fixed original image scales; no new model inference or replacement of manuscript references.'])
 (P/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 for ident,c in out.items():
  print(ident,'mean',np.round(c['five']['mean'],5),'sd',np.round(c['five']['sample_sd'],5),'relative SD %',np.round(c['five']['relative_sd_percent'],2),'new-only SD',np.round(c['four_new']['sample_sd'],5))
  if 'annotations' in c:print('outside stations per trace',[len(r['interior_centreline_stations_outside']) for r in c['annotations']])
if __name__=='__main__':main()
