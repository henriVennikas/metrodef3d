"""Recompute benchmark metrics using only this supplement. No model execution."""
from pathlib import Path
import csv,json
import numpy as np
R=Path(__file__).resolve().parent
summary=list(csv.DictReader((R/'comparison.csv').open()));targets=['centerline_length','mean_width','max_width','crack_area'];anchor=None;checks=0
for directory,tag in [('transformer','Transformer'),('convnext_tiny','ConvNeXt'),('resnet50','ResNet')]:
 d=R/directory;parts={k:list(csv.DictReader((d/f'{k}_predictions.csv').open())) for k in ['val','test']};cfg=json.loads((d/'config.json').read_text());factors=json.loads((d/'calibration.json').read_text())['posthoc_calibration']['interval_scales'];split=json.loads((d/'split_seeds.json').read_text())
 references={k:[(x['seed'],x['stream'],*[float(x[t+'_actual']) for t in targets]) for x in rows] for k,rows in parts.items()}
 if anchor is None:anchor=references
 else:assert references==anchor,'Reference identity mismatch'
 for k,rows in parts.items():assert len(rows)==1494 and [int(x['seed']) for x in rows]==sorted(split[k])
 for j,t in enumerate(targets):
  def arrays(k):return [np.array([float(x[t+'_'+s]) for x in parts[k]]) for s in ['actual','mu','lower','upper']]
  va,vm,vl,vh=arrays('val');sc=float(np.quantile(np.maximum(1,np.where(va<vm,(vm-va)/np.maximum(vm-vl,1e-9),(va-vm)/np.maximum(vh-vm,1e-9))),.95));assert np.isclose(sc,factors[t],rtol=4e-6)
  a,m,l,h=arrays('test');l=m-(m-l)*sc;h=m+(h-m)*sc;e=m-a;positive=a>0;floor=cfg.get('relative_floors',np.array(cfg['target_mean'])*.02)[j];score=h-l+40*(np.maximum(l-a,0)+np.maximum(a-h,0))
  calculated=dict(mae=np.mean(abs(e)),rmse=np.sqrt(np.mean(e*e)),r2=1-np.sum(e*e)/np.sum((a-a.mean())**2),positive_mare_percent=100*np.mean(abs(e[positive])/a[positive]),coverage_percent=100*np.mean((l<=a)&(a<=h)),mean_interval_width=np.mean(h-l),relative_interval_score_percent=100*np.mean(score/np.maximum(abs(a),floor)))
  row=next(x for x in summary if x['model'].startswith(tag) and x['target']==t)
  for metric,value in calculated.items():assert np.isclose(value,float(row[metric]),rtol=5e-6,atol=5e-6),(directory,t,metric,value,row[metric]);checks+=1
print(json.dumps(dict(status='passed',metric_checks=checks,paired_references=True,calibration_validation_only=True)))
