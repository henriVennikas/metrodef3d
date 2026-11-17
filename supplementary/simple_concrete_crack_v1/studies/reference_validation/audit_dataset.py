"""Read-only audit of released sidecars for out-of-frame centreline bridges.
A candidate is confirmed using independently projected original world points.
Never changes references, exclusions, benchmark predictions or model weights.
"""
import argparse,json,math,csv
from pathlib import Path
import numpy as np


def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--split',type=Path,required=True);args=p.parse_args();base=Path(__file__).resolve().parent
 split=json.loads(args.split.read_text());parts={int(s):name for name in ['train','val','test'] for s in split[name]}
 findings=[];candidates=[];total=0
 for path in sorted(args.dataset.glob('seeds_*/visible_defect/*.json'),key=lambda x:int(x.stem)):
  d=json.loads(path.read_text());total+=1;src=d['source_profile'];xyz=d['centerline'];hits=[]
  for i,(a,b) in enumerate(zip(src,src[1:])):
   gap=b['segment_index']-a['segment_index']
   if gap>1 or (gap==1 and a['segment_fraction']<.99 and b['segment_fraction']>.01):
    hits.append(i)
  if hits:
   meta=json.loads((path.parent.parent/'json'/path.name).read_text());camera=meta['outputs']['captures'][0]['camera'];pts=np.array(meta['defect']['centerline']);positions=np.array(camera['position']);forward=np.array(camera['target'])-positions;forward/=np.linalg.norm(forward)
   right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right);up=np.cross(right,forward)
   # Blender track-quaternion Y-up roll acts in local camera XY axes.
   roll=math.radians(camera.get('roll_degrees',0));r=right*math.cos(roll)+up*math.sin(roll);u=-right*math.sin(roll)+up*math.cos(roll)
   rel=pts-positions;depth=rel@forward;tan=math.tan(math.radians(camera['fov_degrees'])/2)
   uv=np.column_stack([.5+(rel@r)/(2*tan*depth),.5+(rel@u)/(2*tan*depth)])
   # Independent homogeneous world-space segment clipping. Retain separate
   # visible intervals and sum lengths without joining disconnected pieces.
   normals=np.array([tan*forward+r,tan*forward-r,tan*forward+u,tan*forward-u,forward])
   plane=rel@normals.T;left=plane[:-1];delta=plane[1:]-left
   lo=np.zeros(len(left));hi=np.ones(len(left));valid=np.ones(len(left),dtype=bool)
   for j in range(5):
    parallel=abs(delta[:,j])<1e-14;valid &= ~(parallel & (left[:,j]<0))
    ratio=np.divide(-left[:,j],delta[:,j],out=np.zeros(len(left)),where=~parallel)
    lo=np.maximum(lo,np.where(delta[:,j]>1e-14,ratio,0))
    hi=np.minimum(hi,np.where(delta[:,j]<-1e-14,ratio,1))
   visible=valid & (hi>=lo)
   independent_length=float(np.sum(np.linalg.norm(np.diff(pts,axis=0),axis=1)*np.where(visible,hi-lo,0)))
   # Check reconstructed camera axes against the saved pixel coordinates.
   vp=np.array(xyz)-positions;vz=vp@forward
   pixels=np.column_stack([(.5+vp@r/(2*tan*vz))*camera['resolution'][0],(.5-vp@u/(2*tan*vz))*camera['resolution'][1]])
   pixel_discrepancy=float(np.max(abs(pixels-np.array(d['centerline_pixels']))))
   extra=0.;confirmed=[]
   for i in hits:
    a,b=src[i:i+2];between=uv[a['segment_index']+1:b['segment_index']+1]
    outside=np.any((between< -1e-6)|(between>1+1e-6),axis=1)
    dist=float(np.linalg.norm(np.array(xyz[i+1])-xyz[i]))
    hit=dict(sample_index=i,from_segment=a['segment_index'],to_segment=b['segment_index'],bridge_mm=dist,intermediate_vertices=len(between),outside_vertices=int(outside.sum()))
    if len(between) and outside.all():extra+=dist;confirmed.append(hit)
   candidates.append(dict(seed=int(path.stem),candidate_gaps=len(hits),confirmed_gaps=len(confirmed)))
   if confirmed:
    L=d['measurands']['centerline_length'];A=d['measurands']['crack_area']
    findings.append(dict(seed=int(path.stem),partition=parts.get(int(path.stem),'excluded'),recorded_length_mm=L,bridge_sum_mm=extra,bridge_fraction_percent=100*extra/L,length_without_bridges_mm=L-extra,recorded_mean_width_mm=d['measurands']['mean_width'],area_over_unbridged_length_mm=A/(L-extra),independent_visible_length_mm=independent_length,unbridged_vs_independent_mm=(L-extra)-independent_length,projection_discrepancy_px=pixel_discrepancy,gaps=confirmed))
  if total%1000==0:print(total,'sidecars scanned;',len(findings),'confirmed affected',flush=True)
 result=dict(sidecars_scanned=total,candidate_count=len(candidates),confirmed_count=len(findings),partition_counts={k:sum(r['partition']==k for r in findings) for k in ['train','val','test','excluded']},candidates=candidates,findings=findings,note='Diagnostic subtraction of false connecting edges only. Not an independently regenerated dataset or authorized replacement labels. Camera projection independently reconstructed from recorded pose, FOV and roll. Candidate detector ignores sub-percent fractional gaps to avoid round-trip noise. Boundaries-only failures cannot be detected from already successful sidecars.')
 (base/'dataset_topology_audit.json').write_text(json.dumps(result,indent=2)+'\n')
 if findings:
  fields=[k for k in findings[0] if k!='gaps']
  with (base/'dataset_topology_audit.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(findings)
 print('AUDIT_COMPLETE',total,len(candidates),len(findings),result['partition_counts'])

if __name__=='__main__':main()
