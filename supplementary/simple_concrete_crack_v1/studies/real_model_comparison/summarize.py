from pathlib import Path
import csv,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
METHODS=['transformer','resnet50','convnext_tiny','conventional'];TARGETS=['centerline_length','mean_width','max_width','crack_area']
def write(name,rows):
 with (HERE/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 protocol=json.loads((HERE/'protocol.json').read_text());rows=[];runtime={};hashes={}
 for m in METHODS:
  runtime[m]=json.loads((HERE/'results'/m/'run.json').read_text());assert runtime[m]['protocol_sha256']==hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()
  for image in protocol['images']:
   d=json.loads((HERE/'results'/m/(image+'.json')).read_text());ref=json.loads((HERE/'inputs'/image/'reference.json').read_text())['reference']
   if image in hashes:assert hashes[image]==d['input_sha256'],('different input',m,image)
   hashes[image]=d['input_sha256']
   for t in TARGETS:
    a=ref[t];p=d['predictions'][t];mu=p['mu'];lo=p['calibrated_lower'];hi=p['calibrated_upper']
    assert np.isfinite([a,mu,lo,hi]).all() and lo<=mu<=hi and a>0
    rows.append(dict(method=m,image=image,target=t,reference=a,prediction=mu,lower=lo,upper=hi,signed_difference=mu-a,absolute_relative_difference_percent=100*abs(mu-a)/a,reference_inside_interval=lo<=a<=hi,interval_width=hi-lo,inference_seconds=d['inference_seconds']))
 write('comparison.csv',rows);summary=[]
 for m in METHODS:
  for t in TARGETS:
   rr=[r for r in rows if r['method']==m and r['target']==t];err=np.array([r['signed_difference'] for r in rr]);ar=np.array([r['absolute_relative_difference_percent'] for r in rr])
   summary.append(dict(method=m,target=t,n=len(rr),mae=float(abs(err).mean()),rmse=float(np.sqrt(np.mean(err**2))),r2=float(1-np.sum(err**2)/np.sum((np.array([r['reference'] for r in rr])-np.mean([r['reference'] for r in rr]))**2)),mean_absolute_relative_difference_percent=float(ar.mean()),median_absolute_relative_difference_percent=float(np.median(ar)),min_absolute_relative_difference_percent=float(ar.min()),max_absolute_relative_difference_percent=float(ar.max()),interval_inclusions=sum(r['reference_inside_interval'] for r in rr),mean_interval_width=float(np.mean([r['interval_width'] for r in rr]))))
 write('summary.csv',summary)
 checks=dict(common_input_sha256=hashes,paired_cases=5,methods=4,scalar_comparisons=len(rows),synthetic_calibration_only=True,no_training=True,original_predictions_and_annotations_preserved=True)
 # Original field inference was float32 CPU. Check the retained transformer explicitly.
 old=list(csv.DictReader((HERE/'historical_transformer.csv').open()));parity=[]
 for r in old:
  new=next(x for x in rows if x['method']=='transformer' and x['image']==r['image'] and x['target']==r['target'])
  parity.append(dict(image=r['image'],target=r['target'],prediction_difference=new['prediction']-float(r['prediction']),reference_difference=new['reference']-float(r['reference']),lower_difference=new['lower']-float(r['synthetic_calibrated_lower']),upper_difference=new['upper']-float(r['synthetic_calibrated_upper'])))
 write('transformer_parity.csv',parity);checks['transformer_max_absolute_prediction_difference']=max(abs(r['prediction_difference']) for r in parity);checks['transformer_max_absolute_reference_difference']=max(abs(r['reference_difference']) for r in parity)
 assert checks['transformer_max_absolute_prediction_difference']<5e-5
 assert checks['transformer_max_absolute_reference_difference']==0
 (HERE/'verification.json').write_text(json.dumps(checks,indent=2)+'\n')
 for m in METHODS:
  print(m, 'mean ARD', [round(r['mean_absolute_relative_difference_percent'],2) for r in summary if r['method']==m], 'inside',sum(r['reference_inside_interval'] for r in rows if r['method']==m),'/20')
 print(checks)
if __name__=='__main__':main()
