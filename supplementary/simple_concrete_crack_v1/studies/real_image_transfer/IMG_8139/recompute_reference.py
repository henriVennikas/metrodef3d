"""Geometric reference and single-image frozen-model comparison for IMG_8139."""
from pathlib import Path
import json, hashlib, csv
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parent
ARTICLE=ROOT
def cross(a,b): return a[...,0]*b[...,1]-a[...,1]*b[...,0]
def project(p,H):
 q=np.c_[p,np.ones(len(p))]@H.T
 return q[:,:2]/q[:,2:]
def chain(p): return np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
def interp(s,p,t):return np.column_stack([np.interp(t,s,p[:,i]) for i in range(2)])
def inside(q,p):
 a=p;b=np.roll(p,-1,axis=0);out=[]
 for x,y in q:
  ok=(a[:,1]>y)!=(b[:,1]>y);out.append(bool(np.count_nonzero(ok & (x < (b[:,0]-a[:,0])*(y-a[:,1])/(b[:,1]-a[:,1]+1e-300)+a[:,0]))%2))
 return np.array(out)
def crossings(p):
 hits=[];n=len(p)
 for i in range(n):
  a=p[i];v=p[(i+1)%n]-a
  for j in range(i+2,n):
   if i==0 and j==n-1:continue
   b=p[j];w=p[(j+1)%n]-b;d=cross(v,w)
   if abs(d)<1e-12:continue
   t=cross(b-a,w)/d;u=cross(b-a,v)/d
   if 1e-9<t<1-1e-9 and 1e-9<u<1-1e-9:hits.append([i,j])
 return hits

def sections(line,poly,step=.05,window=1):
 s=chain(line);L=s[-1];ts=np.arange(step/2,L,step);q=interp(s,line,ts)
 tang=interp(s,line,np.minimum(L,ts+window/2))-interp(s,line,np.maximum(0,ts-window/2))
 tang/=np.linalg.norm(tang,axis=1)[:,None];normal=np.column_stack([-tang[:,1],tang[:,0]])
 a=poly;b=np.roll(poly,-1,axis=0);e=b-a;contained=inside(q,poly);rows=[]
 for station,P,n,inc in zip(ts,q,normal,contained):
  d=cross(n,e);good=np.abs(d)>1e-12;v=a-P
  t=np.divide(cross(v,e),d,out=np.full(len(e),np.nan),where=good)
  u=np.divide(cross(v,n),d,out=np.full(len(e),np.nan),where=good)
  vals=np.sort(t[good&(u>=0)&(u<1)]);vals=vals[np.r_[True,np.diff(vals)>1e-8]] if len(vals) else vals
  neg=vals[vals<=0];pos=vals[vals>=0];valid=bool(inc and len(neg) and len(pos))
  width=float(pos[0]-neg[-1]) if valid else None
  ends=[(P+n*neg[-1]).tolist(),(P+n*pos[0]).tolist()] if valid else None
  rows.append(dict(station_mm=float(station),width_mm=width,inside=bool(inc),intersection_count=len(vals),endpoints_mm=ends))
 valid=[r for r in rows if r['width_mm'] is not None]
 return dict(step_mm=step,tangent_window_mm=window,stations=len(rows),valid_stations=len(valid),outside_stations=int((~contained).sum()),multi_intersection_stations=sum(r['intersection_count']>2 for r in rows),max_width_mm=max(r['width_mm'] for r in valid),mean_section_width_mm=float(np.mean([r['width_mm'] for r in valid])),maximum=max(valid,key=lambda r:r['width_mm']),rows=rows)

def tests():
 p=np.array([[0.,-1],[10,-1],[10,1],[0,1]]);line=np.array([[0.,0],[10,0]])
 r=sections(line,p);assert np.allclose([a['width_mm'] for a in r['rows']],2)
 ang=.71;R=np.array([[np.cos(ang),-np.sin(ang)],[np.sin(ang),np.cos(ang)]])
 assert abs(sections(line@R,p@R)['max_width_mm']-2)<1e-9
 tapered=np.array([[0.,-.5],[10,-1.5],[10,1.5],[0,.5]])
 r=sections(line,tapered);assert all(abs(a['width_mm']-(1+.2*a['station_mm']))<1e-9 for a in r['rows'])
 assert not crossings(p) and crossings(np.array([[0.,0],[1,1],[0,1],[1,0]]))

def main():
 tests();source=ROOT/'IMG_8139_annotation.json';ann=json.loads(source.read_text());H=np.array(ann['pixelToScannerMm']);prep=json.loads((ROOT/'preprocessing.json').read_text())['images'][0]
 np.testing.assert_allclose(H,prep['homography'],rtol=0,atol=1e-14)
 assert not ann['draft']['points'];lines=[a for a in ann['annotations'] if a['kind']=='centreline'];polys=[a for a in ann['annotations'] if a['kind']=='boundary'];assert len(lines)==len(polys)==1
 line_px=np.array(lines[0]['points']);poly_px=np.array(polys[0]['points']);line=project(line_px,H);poly=project(poly_px,H)
 L=float(chain(line)[-1]);A=float(abs(cross(poly,np.roll(poly,-1,axis=0)).sum())/2)
 assert abs(L-lines[0]['measuredValue'])<1e-8 and abs(A-polys[0]['measuredValue'])<1e-8
 intersections=crossings(poly);assert not intersections,('Self-intersecting boundary',intersections)
 baseline=sections(line,poly);sensitivity=[]
 for step,window in [(.05,.5),(.05,2),(.025,1),(.1,1)]:
  r=sections(line,poly,step,window);sensitivity.append({k:v for k,v in r.items() if k!='rows'})
 ref={'image':'IMG_8139','annotation_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'method':'Planar polyline length, polygon area, area/length mean; sampled perpendicular maximum','reference':{'centerline_length':L,'mean_width':A/L,'max_width':baseline['max_width_mm'],'crack_area':A},'self_intersections':intersections,'baseline':{k:v for k,v in baseline.items() if k!='rows'},'sensitivity':sensitivity,'tests':'Rectangle, rotated rectangle, linear taper and crossing detection passed','reference_uncertainty':'Not quantified; sensitivity is not a confidence interval. Boundary encloses debris. Shared scale/image prevents full independence.'}
 (ROOT/'reference.json').write_text(json.dumps(ref,indent=2));(ROOT/'width_sections.json').write_text(json.dumps(baseline['rows'],indent=2))
 with (ROOT/'width_sections.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['station_mm','width_mm','inside','intersection_count']);w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in baseline['rows'])
 rgb=Image.open(ROOT/'IMG_8139.jpeg').convert('RGB').resize((1024,1024));scale=1024/3024
 cv=lambda p:[tuple((v+.5)*scale-.5) for v in p]
 overlay=rgb.copy();d=ImageDraw.Draw(overlay);d.line(cv(np.vstack([poly_px,poly_px[0]])),fill=(20,255,120),width=2);d.line(cv(line_px),fill=(70,200,255),width=2)
 maxpx=project(np.array(baseline['maximum']['endpoints_mm']),np.linalg.inv(H));d.line(cv(maxpx),fill=(255,0,255),width=4);overlay.save(ROOT/'annotation_overlay.png')
 print(json.dumps(ref,indent=2))
 if not (ROOT/'predictions.json').exists():return
 pred=json.loads((ROOT/'predictions.json').read_text());assert pred['status']=='complete' and pred['weights_and_buffers_unchanged'];assert len(pred['images'])==1
 rows=[]
 for name,value in ref['reference'].items():
  p=pred['images'][0]['predictions'][name];lo=p['synthetic_calibrated_lower'];hi=p['synthetic_calibrated_upper'];m=p['prediction']
  rows.append(dict(target=name,unit=p['unit'],reference=value,prediction=m,signed_difference=m-value,signed_relative_difference_percent=100*(m-value)/value,absolute_relative_difference_percent=100*abs(m-value)/value,raw_lower=p['raw_lower'],raw_upper=p['raw_upper'],synthetic_calibrated_lower=lo,synthetic_calibrated_upper=hi,reference_inside_interval=bool(lo<=value<=hi)))
 maskim=Image.new('1',(1024,1024));ImageDraw.Draw(maskim).polygon(cv(poly_px),fill=1);truth=np.array(maskim,bool);dense=np.load(ROOT/'IMG_8139_dense.npz');prob=dense['defect_probability'];mask=prob>=.5;tp=int((mask&truth).sum());fp=int((mask&~truth).sum());fn=int((~mask&truth).sum())
 seg={'threshold':.5,'annotated_mask_pixels':int(truth.sum()),'model_mask_pixels':int(mask.sum()),'intersection_over_union':tp/(tp+fp+fn),'precision':tp/(tp+fp),'recall':tp/(tp+fn),'mean_probability_inside_annotation':float(prob[truth].mean()),'note':'Auxiliary mask vs rasterized outer annotation including debris. Not the source of scalar predictions.'}
 comp={'image':'IMG_8139','rows':rows,'auxiliary_mask':seg,'annotation_sha256':ref['annotation_sha256'],'checkpoint_sha256':pred['checkpoint_sha256'],'no_training':not pred['training_performed']}
 (ROOT/'comparison.json').write_text(json.dumps(comp,indent=2))
 with (ROOT/'comparison.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 panel=Image.new('RGB',(1800,640),'white');draw=ImageDraw.Draw(panel)
 for i,(im,title) in enumerate([(rgb,'Original image'),(overlay,'Manual boundary (green), path (blue), max section (magenta)'),(Image.open(ROOT/'IMG_8139_overlay.png'),'Model auxiliary mask, threshold 0.5')]):
  panel.paste(im.resize((600,600)),(600*i,40));draw.text((600*i+8,12),title,fill='black')
 panel.save(ROOT/'comparison_overview.jpg',quality=95)
 print('COMPARISON',json.dumps(comp,indent=2))
if __name__=='__main__':main()
