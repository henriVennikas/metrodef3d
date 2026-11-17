"""Apply the frozen conventional pipeline without field-specific tuning."""
from pathlib import Path
import json,time,hashlib,platform
import numpy as np
from PIL import Image,ImageDraw
from classical_pipeline import predict
HERE=Path(__file__).resolve().parent
p=json.loads((HERE/'protocol.json').read_text());cfg=json.loads((HERE/'classical_settings.json').read_text())['config'];radii=json.loads((HERE/'calibration.json').read_text())['conventional']['corrected_refs_valid_cohort']
out=HERE/'results/conventional';out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
for name in p['images']:
 d=HERE/'inputs'/name
 rgb=np.asarray(Image.open(d/(name+'.jpeg')).convert('RGB').resize((1024,1024),Image.Resampling.BILINEAR))
 with np.load(d/(name+'_scale.npz')) as z:sx=z['scale_x_mm_per_px'].astype(np.float32);sy=z['scale_y_mm_per_px'].astype(np.float32)
 tensor=np.concatenate([(rgb.astype(np.float32)/255).transpose(2,0,1),np.sqrt(sx*sy)[None]],axis=0)[None];h=hashlib.sha256(tensor.tobytes()).hexdigest()
 t=time.perf_counter();values,diag=predict(rgb,sx,sy,cfg,diagnostic=True);elapsed=time.perf_counter()-t
 predictions={k:dict(mu=v,lower=max(0,v-radii[k]),upper=v+radii[k],calibrated_lower=max(0,v-radii[k]),calibrated_upper=v+radii[k],unit='mm2' if k=='crack_area' else 'mm') for k,v in values.items()}
 np.savez_compressed(out/(name+'_mask.npz'),mask=diag.pop('mask'))
 paths=diag.pop('paths');overlay=Image.fromarray(rgb);draw=ImageDraw.Draw(overlay)
 for path in paths:
  if len(path)>1:draw.line([tuple(q) for q in path],fill=(255,0,0),width=2)
 overlay.save(out/(name+'_paths.jpg'),quality=90)
 row=dict(image=name,input_sha256=h,predictions=predictions,diagnostics=diag,inference_seconds=elapsed);(out/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n');print(name,round(elapsed,2),'s',flush=True)
(out/'run.json').write_text(json.dumps(dict(wall_seconds=time.perf_counter()-start,platform=platform.platform(),numpy=np.__version__,settings=cfg,calibration='corrected_refs_valid_cohort',protocol_sha256=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()),indent=2)+'\n')
