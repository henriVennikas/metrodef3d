"""Evaluate the unchanged transformer for a shared-scale uncertainty example."""
from pathlib import Path
import argparse,json,sys,hashlib,time,platform
import numpy as np
import torch
P=Path(__file__).resolve().parent
def state_hash(m):
 h=hashlib.sha256()
 for k,v in m.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--assets',type=Path,required=True);ap.add_argument('--package',type=Path,default=P.parents[1]/'inference/src');args=ap.parse_args();sys.path.insert(0,str(args.package))
 from metrodef_models.engine import Predictor
 from metrodef_models.inputs import image_input
 torch.set_num_threads(4);t=time.perf_counter();model=Predictor(args.assets/'transformer',device='cpu',precision='float32',dense=False);before=state_hash(model.model)
 cal=json.loads((P/'inputs/synthetic_interval_calibration.json').read_text())['transformer']['corrected_refs_valid_cohort'];inp=image_input(P/'inputs/IMG_8579.jpeg',scale_path=P/'results/IMG_8579_scale_metrosert.npz',scale_grid='model');rgbsha=hashlib.sha256(inp[0,:3].numpy().tobytes()).hexdigest()
 vectors=np.load(P/'results/scale_vectors.npz');rows=[]
 cases=[('previous',None,0),('metrosert',None,0)]+[(f'axis{a}_{s:+.3f}',a,s) for a in range(2) for s in [-.01,-.005,.005,.01]]
 for name,axis,step in cases:
  x=inp.clone()
  if name=='previous':x=image_input(P/'inputs/IMG_8579.jpeg',scale_path=P/'inputs/IMG_8579_scale_previous.npz',scale_grid='model')
  elif axis is not None:
   fac=np.ones(2);fac[axis]+=step;sx=np.linalg.norm(vectors['dx']*fac,axis=2);sy=np.linalg.norm(vectors['dy']*fac,axis=2);x[0,3]=torch.from_numpy(np.sqrt(sx*sy).astype('float32'))
  assert hashlib.sha256(x[0,:3].numpy().tobytes()).hexdigest()==rgbsha
  tick=time.perf_counter();pred,_=model.predict(x)
  for key,v in pred.items():v['calibrated_lower']=v['mu']-(v['mu']-v['lower'])*cal[key];v['calibrated_upper']=v['mu']+(v['upper']-v['mu'])*cal[key]
  rows.append(dict(case=name,physical_axis=axis,relative_change=step,predictions=pred,inference_seconds=time.perf_counter()-tick,input_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest()));print(name,{k:round(v['mu'],6) for k,v in pred.items()},flush=True)
 assert state_hash(model.model)==before
 out=dict(model='Transformer',selected_epoch=49,weights_sha256=model.config['weights_sha256'],state_sha256=before,state_unchanged=True,rgb_sha256=rgbsha,device='cpu',precision='float32',threads=4,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,calibration=cal,wall_seconds=time.perf_counter()-t,results=rows,training=False,field_fitting=False)
 (P/'results/model_scale_sensitivity.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
