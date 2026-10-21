"""Estimate printed target dimensions using independently calibrated scanner axes.
Original TIFFs remain untouched. No fit to nominal paper dimensions sets scale.
"""
from pathlib import Path
import json,sys,math
import cv2
import numpy as np
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path, help='Directory of 2540 dpi paper-target TIFFs')
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
from jdgrid.core import detect,read_dpi,orient_grid,infer_rotation_cw
ROOT=args.output
ROOT.mkdir(parents=True, exist_ok=True)
SOURCE=args.source
SCALE=np.array([.010066935,.010012375])
all_results=[]
for path in sorted(SOURCE.glob('*.tif')):
 print('Processing',path.name,flush=True)
 gray=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
 dpi=read_dpi(path)
 assert dpi==(2540.,2540.)
 # Detect at half sampling, then refine every actual centre on original pixels.
 small=cv2.resize(gray,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
 grid,mask=detect(small,tuple(d*.5 for d in dpi))
 grid=(grid+.5)*2-.5
 diameter=[]; diameter_low=[];diameter_high=[]
 for row,col in np.argwhere(mask):
  x,y=grid[row,col];cx,cy=round(x),round(y);rad=70
  x0=max(0,cx-rad);y0=max(0,cy-rad)
  patch=gray[y0:cy+rad+1,x0:cx+rad+1].astype(float)
  bg=float(np.percentile(patch,90));dark=float(np.percentile(patch,10))
  weights=np.clip(bg-patch,0,None);yy,xx=np.indices(patch.shape)
  grid[row,col]=[x0+np.sum(xx*weights)/weights.sum(),y0+np.sum(yy*weights)/weights.sum()]
  for fraction,collection in [(0.5,diameter),(.4,diameter_low),(.6,diameter_high)]:
   binary=(patch < dark+fraction*(bg-dark)).astype('uint8')
   contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
   contour=max(contours,key=cv2.contourArea).astype(float)*SCALE
   area=cv2.contourArea(contour.astype('float32'))
   collection.append(2*math.sqrt(area/math.pi))
 rotation=infer_rotation_cw(mask)
 grid=orient_grid(grid,rotation);mask=orient_grid(mask,rotation)
 physical=grid*SCALE
 # Independently scaled physical points, fit index->mm only to summarize pitch/distortion.
 rr,cc=np.mgrid[:50,:50];design=np.stack([cc,rr,np.ones_like(cc)],axis=-1)
 affine=np.linalg.lstsq(design[mask],physical[mask],rcond=None)[0]
 residual=physical-design@affine
 norm=lambda v:float(np.linalg.norm(v))
 spans={'top':norm(physical[0,-1]-physical[0,0]),'bottom':norm(physical[-1,-1]-physical[-1,0]),'left':norm(physical[-1,0]-physical[0,0]),'right':norm(physical[-1,-1]-physical[0,-1])}
 width=(spans['top']+spans['bottom'])/2;height=(spans['left']+spans['right'])/2
 result={'target':path.stem,'source':str(path),'metadata_dpi':dpi,'scanner_mm_per_pixel':SCALE.tolist(),'detected_solid_dots':int(mask.sum()),'inferred_hollow_marks':int((~mask).sum()),'rotation_cw':rotation,'edge_spans_mm':spans,'width_mm':width,'height_mm':height,'width_error_mm':width-98,'height_error_mm':height-98,'width_error_percent':100*(width/98-1),'height_error_percent':100*(height/98-1),'mean_pitch_from_outer_span_mm':[width/49,height/49],'fitted_pitch_mm':[norm(affine[0]),norm(affine[1])],'axis_angle_deg':math.degrees(math.acos(np.dot(affine[0],affine[1])/norm(affine[0])/norm(affine[1]))),'affine_residual_rms_um':float(np.sqrt(np.mean(np.sum(residual[mask]**2,axis=1)))*1000),'median_equivalent_dot_diameter_mm':float(np.median(diameter)),'median_diameter_threshold_sensitivity_mm':[float(np.median(diameter_low)),float(np.median(diameter_high))]}
 (ROOT/(path.stem+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 np.savez_compressed(ROOT/(path.stem+'_points.npz'),pixel_centres=grid,scanner_mm=physical,detected=mask)
 preview=cv2.cvtColor(cv2.resize(gray,None,fx=.12,fy=.12,interpolation=cv2.INTER_AREA),cv2.COLOR_GRAY2BGR)
 for r,c in np.argwhere(mask):
  x,y=np.rint(grid[r,c]*.12).astype(int);cv2.circle(preview,(x,y),1,(0,0,255),-1)
 corners=grid[[0,0,-1,-1],[0,-1,-1,0]]*.12
 cv2.polylines(preview,[np.rint(corners).astype('int32')],True,(255,0,0),2)
 cv2.imwrite(str(ROOT/(path.stem+'_qa.jpg')),preview)
 all_results.append(result)
 print(json.dumps(result),flush=True)
(ROOT/'summary.json').write_text(json.dumps(all_results,indent=2)+'\n')
