"""Run frozen model assets on the frozen common real-image panel."""
from pathlib import Path
import argparse,json,time,hashlib,platform,importlib.metadata
import numpy as np
import torch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'source'))
from metrodef_models.engine import Predictor
from metrodef_models.inputs import image_input
HERE=Path(__file__).resolve().parent
def state_hash(model):
 h=hashlib.sha256()
 for k,v in model.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--model',choices=['transformer','resnet50','convnext_tiny'],required=True);a=p.parse_args()
 out=HERE/'results'/a.model;out.mkdir(parents=True,exist_ok=False)
 protocol=json.loads((HERE/'protocol.json').read_text());cal=json.loads((HERE/'calibration.json').read_text())[a.model]['corrected_refs_valid_cohort'];torch.set_num_threads(4)
 start=time.perf_counter();predictor=Predictor(a.assets/a.model,device='cpu',precision='float32',dense=False);before=state_hash(predictor.model);rows=[]
 for name in protocol['images']:
  d=HERE.parent/'inputs'/name;inputs=image_input(d/(name+'.jpeg'),scale_path=d/'scale.npz',scale_grid='model');h=hashlib.sha256(inputs.numpy().tobytes()).hexdigest();t=time.perf_counter();pred,_=predictor.predict(inputs);elapsed=time.perf_counter()-t
  for target,r in pred.items():r['calibrated_lower']=r['mu']-(r['mu']-r['lower'])*cal[target];r['calibrated_upper']=r['mu']+(r['upper']-r['mu'])*cal[target]
  row=dict(image=name,input_sha256=h,predictions=pred,inference_seconds=elapsed);rows.append(row);(out/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n');print(a.model,name,round(elapsed,2),'s',flush=True)
 assert state_hash(predictor.model)==before,'Inference mutated model state'
 config=dict(predictor.config);(out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
 env=dict(platform=platform.platform(),python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,torchvision=importlib.metadata.version('torchvision'),device='cpu',precision='float32',threads=torch.get_num_threads(),weights_sha256=predictor.config['weights_sha256'],model_state_sha256=before,weights_and_buffers_unchanged=True,wall_seconds=time.perf_counter()-start,protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest(),calibration_sha256=hashlib.sha256((HERE/'calibration.json').read_bytes()).hexdigest())
 (out/'run.json').write_text(json.dumps(env,indent=2)+'\n')
if __name__=='__main__':main()
