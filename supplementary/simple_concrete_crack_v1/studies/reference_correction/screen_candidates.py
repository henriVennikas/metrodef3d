"""Read all original sidecars; select every recorded boundary transition or source gap."""
import argparse,json,hashlib
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',required=True,type=Path);a=p.parse_args();here=Path(__file__).resolve().parent;rows=[];hashes={}
 for path in sorted(a.dataset.glob('seeds_*/visible_defect/*.json'),key=lambda p:int(p.stem)):
  raw=path.read_bytes();d=json.loads(raw);hashes[str(path.relative_to(a.dataset))]=hashlib.sha256(raw).hexdigest();src=d['source_profile'];pix=d['centerline_pixels'];points=d['centerline'];hits=[]
  # All released images have 1024x1024 resolution. Validate against metadata
  # for every selected candidate in the regeneration stage.
  def on_boundary(p):return any(abs(float(v)-edge)<=1e-5 for v in p for edge in (0,1024))
  for i,(left,right) in enumerate(zip(src,src[1:])):
   gap=right['segment_index']-left['segment_index']
   boundary=on_boundary(pix[i]) and on_boundary(pix[i+1]) and points[i]!=points[i+1]
   if gap>1 or (gap>=1 and boundary):hits.append(dict(index=i,source_gap=gap,both_on_boundary=boundary))
  if hits:rows.append(dict(seed=int(path.stem),candidates=hits))
  if len(hashes)%1000==0:print(len(hashes),'scanned;',len(rows),'candidate observations',flush=True)
 (here/'original_sidecar_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
 (here/'candidate_screen.json').write_text(json.dumps(dict(scanned=len(hashes),candidates=rows,criterion='source segment gap >1 OR consecutive distinct boundary points from different source segments; no fractional cutoff',note='A screening superset, not a declaration that each candidate is wrong.'),indent=2)+'\n')
 print('SCREEN_COMPLETE',len(hashes),len(rows))
if __name__=='__main__':main()
