"""Compare frozen outputs before/after reference correction. No model execution."""
import argparse,csv,json,hashlib,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
TARGETS=['centerline_length','mean_width','max_width','crack_area']

def readcsv(p):
 with p.open() as f:return list(csv.DictReader(f))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def arrays(rows):return {k:np.array([[float(r[t+'_'+k]) for t in TARGETS] for r in rows]) for k in ['actual','mu','lower','upper']}
def refs(rows,overlay):
 a=arrays(rows)['actual'].copy()
 for i,r in enumerate(rows):
  if int(r['seed']) in overlay:a[i]=[overlay[int(r['seed'])][t] for t in TARGETS]
 return a

def quantile_scale(a,mu,lo,hi):
 required=np.maximum(1,np.where(a<mu,(mu-a)/np.maximum(mu-lo,1e-9),(a-mu)/np.maximum(hi-mu,1e-9)))
 return np.quantile(required,.95,axis=0)
def learned_bounds(x,scale):return x['mu']-(x['mu']-x['lower'])*scale,x['mu']+(x['upper']-x['mu'])*scale
def classical_bounds(mu,radii):return np.maximum(0,mu-radii),mu+radii

def metrics(a,mu,lo,hi,floors):
 result=[]
 for j,t in enumerate(TARGETS):
  y=a[:,j];p=mu[:,j];e=p-y;l=lo[:,j];u=hi[:,j];pos=y>0;covered=(y>=l)&(y<=u);width=u-l;score=width+40*np.maximum(l-y,0)+40*np.maximum(y-u,0)
  n=len(y);ph=covered.mean();z=1.959963984540054;den=1+z*z/n;mid=(ph+z*z/(2*n))/den;half=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
  result.append(dict(target=t,n=n,n_positive=int(pos.sum()),mae=float(abs(e).mean()),rmse=float(np.sqrt(np.mean(e*e))),r2=float(1-np.sum(e*e)/np.sum((y-y.mean())**2)),bias=float(e.mean()),mare_percent=float(100*np.mean(abs(e[pos])/y[pos])),coverage_percent=float(100*ph),coverage_wilson_low_percent=100*(mid-half),coverage_wilson_high_percent=100*(mid+half),mean_interval_width=float(width.mean()),interval_score=float(score.mean()),normalized_interval_score_percent=float(100*np.mean(score/np.maximum(abs(y),floors[j])))))
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--learned-study',type=Path,required=True);p.add_argument('--classical-study',type=Path,required=True);args=p.parse_args();learned=args.learned_study;classic=args.classical_study
 regeneration=json.loads((HERE/'regeneration.json').read_text());overlay={r['seed']:r['corrected_measurands'] for r in regeneration['rows'] if r['corrected']}
 floors=np.array(json.loads((classic/'protocol.json').read_text())['relative_floors']);prior=readcsv(learned/'comparison.csv');original_metric={(r['model'].split()[0],r['target']):r for r in prior};input_hashes={};table=[];calibration={};validation={};pred_dir=HERE/'predictions';pred_dir.mkdir(exist_ok=True)
 common=None
 for method in ['transformer','resnet50','convnext_tiny','conventional']:
  isclassic=method=='conventional';paths=[classic/'results/test_predictions.csv',classic/'results/calibration_predictions.csv'] if isclassic else [learned/method/'test_predictions.csv',learned/method/'val_predictions.csv']
  test,val=map(readcsv,paths)
  for path in paths:input_hashes[str(path.relative_to(classic if isclassic else learned))+'|'+method]=digest(path)
  ids=[int(r['seed']) for r in test]
  if common is None:common=ids
  assert ids==common and len(set(ids))==1494
  x=arrays(test);v=arrays(val);new_y=refs(test,overlay);new_v=refs(val,overlay);valid=np.array([int(r['seed'])!=551 for r in val]);old_v=v['actual']
  if isclassic:
   oldcal=np.array([json.loads((classic/'calibration.json').read_text())['radii'][t] for t in TARGETS]);repro=np.quantile(abs(old_v-v['mu']),.95,axis=0,method='higher');assert np.allclose(repro,oldcal,atol=1e-12)
   newcal=np.quantile(abs(new_v-v['mu']),.95,axis=0,method='higher');validold=oldcal;samecohort=newcal
   makebounds=lambda cal:classical_bounds(x['mu'],cal)
  else:
   oldcal=np.array([json.loads((learned/method/'calibration.json').read_text())['posthoc_calibration']['interval_scales'][t] for t in TARGETS]);repro=quantile_scale(old_v,v['mu'],v['lower'],v['upper']);assert np.allclose(repro,oldcal,rtol=0,atol=1e-12)
   validold=quantile_scale(old_v[valid],v['mu'][valid],v['lower'][valid],v['upper'][valid]);samecohort=quantile_scale(new_v,v['mu'],v['lower'],v['upper']);newcal=quantile_scale(new_v[valid],v['mu'][valid],v['lower'][valid],v['upper'][valid]);makebounds=lambda cal:learned_bounds(x,cal)
  calibration[method]=dict(kind='absolute_residual_radius' if isclassic else 'asymmetric_expansion_factor',old=dict(zip(TARGETS,oldcal.tolist())),original_refs_valid_cohort=dict(zip(TARGETS,validold.tolist())),corrected_refs_original_cohort=dict(zip(TARGETS,samecohort.tolist())),corrected_refs_valid_cohort=dict(zip(TARGETS,newcal.tolist())),original_n=len(val),valid_n=int(valid.sum()),corrected_validation_rows=sum(int(r['seed']) in overlay for r in val),excluded_invalid_seeds=[] if isclassic else [551],calibration_reproduction_max_error=float(max(abs(repro-oldcal))))
  modes=[('original',x['actual'],oldcal),('corrected_fixed_calibration',new_y,oldcal),('corrected_recalibrated_same_cohort',new_y,samecohort),('corrected_recalibrated_valid_cohort',new_y,newcal),('original_valid_cohort',x['actual'],validold)]
  for mode,y,cal in modes:
   lo,hi=makebounds(cal);m=metrics(y,x['mu'],lo,hi,floors)
   if mode=='original':
    if isclassic:
     previous=json.loads((classic/'results/test_metrics.json').read_text())
     for j,r in enumerate(m):
      for a,b in [('mare_percent','mare_percent'),('rmse','rmse'),('coverage_percent','coverage_percent'),('normalized_interval_score_percent','relative_interval_score_percent')]:assert np.isclose(r[a],previous[j][b],atol=1e-9), (method,a,r[a],previous[j][b])
    else:
     label={'transformer':'Transformer','resnet50':'ResNet-50','convnext_tiny':'ConvNeXt-Tiny'}[method]
     for r in m:
      previous=original_metric[(label,r['target'])]
      for a,b in [('mare_percent','positive_mare_percent'),('rmse','rmse'),('coverage_percent','coverage_percent'),('normalized_interval_score_percent','relative_interval_score_percent')]:assert abs(r[a]-float(previous[b]))<1e-9,(method,a,r[a],previous[b])
   table.extend(dict(method=method,mode=mode,**r) for r in m)
   if mode in ['corrected_fixed_calibration','corrected_recalibrated_valid_cohort']:
    output=[]
    for i,seed in enumerate(ids):
     row=dict(seed=seed,reference_corrected=seed in overlay)
     for j,t in enumerate(TARGETS):row.update({t+'_actual':float(y[i,j]),t+'_mu':float(x['mu'][i,j]),t+'_lower':float(lo[i,j]),t+'_upper':float(hi[i,j])})
     output.append(row)
    dest=pred_dir/(method+'_'+mode+'.csv')
    with dest.open('w') as f:w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
  validation[method]=dict(test_n=len(test),test_corrected=sum(s in overlay for s in ids),unchanged_central_predictions=True,original_metrics_reproduced=True)
 with (HERE/'benchmark_comparison.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 (HERE/'calibration_comparison.json').write_text(json.dumps(calibration,indent=2)+'\n');(HERE/'benchmark_verification.json').write_text(json.dumps(dict(input_sha256=input_hashes,methods=validation,relative_floors=dict(zip(TARGETS,floors.tolist())),test_identity_exact=True,point_estimates_not_retrained=True,note='Corrected entries use six-decimal overlay quantities; unmodified neural reference entries retain original float32 CSV representation. The baseline metrics and factors reproduce original records. No test exclusion or new inference.'),indent=2)+'\n')
 print('MARE: original -> corrected (same central predictions)')
 for method in validation:
  old=[r['mare_percent'] for r in table if r['method']==method and r['mode']=='original'];new=[r['mare_percent'] for r in table if r['method']==method and r['mode']=='corrected_fixed_calibration'];print(method,' / '.join(f'{a:.4f}->{b:.4f}' for a,b in zip(old,new)))
 print('Coverage: original -> corrected fixed calibration -> corrected valid-cohort recalibration')
 for method in validation:
  print(method,[[round(r['coverage_percent'],3) for r in table if r['method']==method and r['mode']==m] for m in ['original','corrected_fixed_calibration','corrected_recalibrated_valid_cohort']])
if __name__=='__main__':main()
