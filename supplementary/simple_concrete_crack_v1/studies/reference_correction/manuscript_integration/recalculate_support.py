"""Apply corrected scalar references and interval factors to saved supporting outputs.
No inference, mask regeneration or parameter fitting is performed here.
"""
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
TARGETS=['centerline_length','mean_width','max_width','crack_area']
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def write(p,rows):
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--classical-study',type=Path,required=True);p.add_argument('--real-study',type=Path,required=True);args=p.parse_args()
 overlay={r['seed']:r['corrected_measurands'] for r in json.loads((HERE.parent/'regeneration.json').read_text())['rows'] if r['corrected']}
 path=args.classical_study/'results/reference_mask_predictions.csv';rows=read(path);stats=[];n=0
 for r in rows:
  if int(r['seed']) in overlay:
   n+=1
   for t in TARGETS:r[t+'_actual']=overlay[int(r['seed'])][t]
 for t in TARGETS:
  a=np.array([float(r[t+'_actual']) for r in rows]);mu=np.array([float(r[t+'_mu']) for r in rows]);pos=a>0
  stats.append(dict(target=t,n=len(a),n_positive=int(pos.sum()),mare_percent=float(100*np.mean(abs(mu[pos]-a[pos])/a[pos])),rmse=float(np.sqrt(np.mean((mu-a)**2)))))
 write(HERE/'reference_mask_corrected_predictions.csv',rows)
 (HERE/'reference_mask_corrected_metrics.json').write_text(json.dumps(stats,indent=2)+'\n')
 realpath=args.real_study/'comparison.csv';real=read(realpath)
 cal=json.loads((HERE.parent/'calibration_comparison.json').read_text())['transformer'];changes=[]
 for r in real:
  mu=float(r['prediction']);lo=float(r['raw_lower']);hi=float(r['raw_upper']);ref=float(r['reference']);t=r['target']
  assert abs((mu-cal['old'][t]*(mu-lo))-float(r['synthetic_calibrated_lower']))<2e-6
  lower=mu-cal['corrected_refs_valid_cohort'][t]*(mu-lo);upper=mu+cal['corrected_refs_valid_cohort'][t]*(hi-mu)
  covered=lower<=ref<=upper
  if covered!=(r['reference_inside_interval']=='True'):changes.append([r['image'],t])
  r.update(synthetic_calibrated_lower=lower,synthetic_calibrated_upper=upper,reference_inside_interval=covered)
 write(HERE/'real_image_corrected_calibration.csv',real)
 summary=dict(reference_mask_corrected_observations=n,reference_mask_predictions_unchanged=True,real_image_central_predictions_and_references_unchanged=True,real_image_interval_membership_changes=changes,original_source_sha256={str(path.relative_to(args.classical_study)):hashlib.sha256(path.read_bytes()).hexdigest(),str(realpath.relative_to(args.real_study)):hashlib.sha256(realpath.read_bytes()).hexdigest()})
 (HERE/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(stats,indent=2));print(summary)
if __name__=='__main__':main()
