"""Reproduce the Metrosert-to-paper-to-photo reference example without inference."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
import cv2
from reference_geometry import project,chain,cross,crossings,sections,tests
P=Path(__file__).resolve().parent
KEYS=['centerline_length','mean_width','max_width','crack_area']
def dump(name,obj): (P/'results'/name).write_text(json.dumps(obj,indent=2)+'\n')
def values(H,d,full=True):
 line=project(np.array(next(a['points'] for a in d['annotations'] if a['kind']=='centreline')),H)
 poly=project(np.array(next(a['points'] for a in d['annotations'] if a['kind']=='boundary')),H)
 L=float(chain(line)[-1]);A=float(abs(cross(poly,np.roll(poly,-1,axis=0)).sum())/2)
 if not full:return np.array([L,A/L,A])
 assert not crossings(poly);s=sections(line,poly)
 assert all(r['inside'] or r['station_mm']<.05 or L-r['station_mm']<.05 for r in s['rows']), 'Interior centreline station outside boundary'
 return np.array([L,A/L,s['max_width_mm'],A])
def main():
 tests()
 for name,h in json.loads((P/'input_checksums.json').read_text()).items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==h,name
 cert=json.loads((P/'inputs/metrosert_values.json').read_text());scans=json.loads((P/'inputs/scanner/spans.json').read_text());oldsp=np.array(cert['reference_old_mm']);newsp=np.array(cert['span_mm'])
 coefficients=[]
 for s in scans:
  dots=np.genfromtxt(P/'inputs/scanner'/(s['scan']+'_dots.csv'),delimiter=',',names=True)
  g=np.stack([dots['pixel_x'],dots['pixel_y']],axis=1).reshape(50,50,2)
  measured=[np.linalg.norm(g[0,0]-g[0,-1]),np.linalg.norm(g[-1,0]-g[-1,-1]),np.linalg.norm(g[0,0]-g[-1,0]),np.linalg.norm(g[0,-1]-g[-1,-1])]
  np.testing.assert_allclose(measured,[s['spans'][k]['observed_px'] for k in cert['span_names']],atol=2e-6,rtol=0)
  px=np.array([s['spans'][k]['observed_px'] for k in cert['span_names']]);a=np.zeros((2,4));a[0,:2]=.5/px[:2];a[1,2:]=.5/px[2:]
  if s['rotation_cw']%180:a=a[::-1]
  coefficients.append(a)
 coefficients=np.array(coefficients);old_scales=coefficients@oldsp;new_scales=coefficients@newsp;oldmean=old_scales.mean(0);newmean=new_scales.mean(0)
 previous_scales=np.array([.010066935,.010012375]);np.testing.assert_allclose(oldmean,previous_scales,atol=5e-10,rtol=0)
 # The same certificate span error affects every use of the target; never average it away.
 cert_shift=coefficients.mean(0)@np.full(4,cert['standard_uncertainty_mm']);cert_cov=np.outer(cert_shift,cert_shift);scan_cov=np.cov(new_scales,rowvar=False,ddof=1)
 norm=np.outer(newmean,newmean);rel_cert_cov=cert_cov/norm;rel_scan_cov=scan_cov/norm
 paper=np.load(P/'inputs/paper_target_01_points_previous.npz');paper_px=paper['pixel_centres'];paper_mm=paper_px*newmean
 np.savez_compressed(P/'results/paper_target_01_points_metrosert.npz',pixel_centres=paper_px,scanner_mm=paper_mm,detected=paper['detected'])
 grid=np.load(P/'inputs/photo_grid_points.npz');pix=grid['pixel_centres'];ij=grid['grid_col_row'];physical=paper_mm[ij[:,1],ij[:,0]];H,_=cv2.findHomography(pix,physical,0)
 oldH=np.array(json.loads((P/'inputs/previous_scale_preprocessing.json').read_text())['images'][0]['homography']);D=np.diag([*(newmean/previous_scales),1])
 np.testing.assert_allclose(project(pix,H),project(pix,D@oldH),atol=2e-5,rtol=0)
 residual=project(pix,H)-physical;hold=(ij[:,1]*50+ij[:,0])%5==0;hh,_=cv2.findHomography(pix[~hold],physical[~hold],0);held=project(pix[hold],hh)-physical[hold]
 anns=[json.loads((P/'inputs/annotations'/f'annotation_{i}.json').read_text()) for i in range(5)]
 data=np.array([values(H,d) for d in anns]);olddata=np.array([values(oldH,d) for d in anns]);earlier=json.loads((P/'inputs/previous_annotation_comparison.json').read_text())
 np.testing.assert_allclose(olddata,np.array([[r['values'][k] for k in KEYS] for r in earlier['annotations']]),atol=1e-10,rtol=0)
 stat={}
 for key,x in [('five',data),('four_new',data[1:])]:stat[key]=dict(n=len(x),mean=x.mean(0).tolist(),sample_sd=x.std(0,ddof=1).tolist(),relative_sd_percent=(x.std(0,ddof=1)/x.mean(0)*100).tolist(),sample_covariance=np.cov(x,rowvar=False,ddof=1).tolist(),u_mean_if_independent=(x.std(0,ddof=1)/np.sqrt(len(x))).tolist())
 # Differentiate reference quantities with respect to relative physical X and Y scale.
 J=[];sensitivity=[]
 for axis in range(2):
  vals=[]
  for sign in [-1,1]:
   t=np.eye(3);t[axis,axis]+=sign*.001;v=np.array([values(t@H,d) for d in anns]).mean(0);vals.append(v)
   sensitivity.append(dict(axis=axis,relative_change=sign*.001,mean_reference=v.tolist()))
  J.append((vals[1]-vals[0])/.002)
 J=np.array(J).T
 Ccert=J@rel_cert_cov@J.T;Cscan=J@rel_scan_cov@J.T;Cann=np.cov(data,rowvar=False,ddof=1);Cmean=Cann/5+Ccert+Cscan;Csingle=Cann+Ccert+Cscan
 # Deterministic spatial block deletion diagnoses mapping stability. Not a standard uncertainty.
 bx=np.minimum(4,((pix[:,0]-pix[:,0].min())/np.ptp(pix[:,0])*5).astype(int));by=np.minimum(4,((pix[:,1]-pix[:,1].min())/np.ptp(pix[:,1])*5).astype(int));blocks=bx+5*by
 nominal_fast=np.array([values(H,d,False) for d in anns]).mean(0);blockresults=[]
 for b in np.unique(blocks):
  keep=blocks!=b;hb,_=cv2.findHomography(pix[keep],physical[keep],0);v=np.array([values(hb,d,False) for d in anns]).mean(0)
  blockresults.append(dict(block=int(b),removed_points=int((~keep).sum()),mean_values_length_width_area=v.tolist(),change_from_full_fit=(v-nominal_fast).tolist()))
 # Scale maps use finite physical distances between neighbouring pixel centres.
 yy,xx=np.mgrid[:1024,:1024];ratio=3024/1024;p=np.c_[((xx+.5)*ratio-.5).ravel(),((yy+.5)*ratio-.5).ravel()]
 dx=project(p+[ratio/2,0],H)-project(p-[ratio/2,0],H);dy=project(p+[0,ratio/2],H)-project(p-[0,ratio/2],H)
 sx=np.linalg.norm(dx,axis=1).reshape(1024,1024);sy=np.linalg.norm(dy,axis=1).reshape(1024,1024)
 np.savez_compressed(P/'results/IMG_8579_scale_metrosert.npz',scale_x_mm_per_px=sx.astype('float32'),scale_y_mm_per_px=sy.astype('float32'),geometric_mean_mm_per_px=np.sqrt(sx*sy).astype('float32'),pixel_to_scanner_mm=H)
 np.savez_compressed(P/'results/scale_vectors.npz',dx=dx.reshape(1024,1024,2),dy=dy.reshape(1024,1024,2))
 # Basic exact sensitivity checks are independent of the statistical assumptions.
 u=1.01;for_uniform=np.array([values(np.diag([u,u,1])@H,d,False) for d in anns]);base=np.array([values(H,d,False) for d in anns]);np.testing.assert_allclose(for_uniform/base,np.broadcast_to([u,u,u*u],base.shape),rtol=1e-10)
 result=dict(quantities=KEYS,units=['mm','mm','mm','mm^2'],scanner=dict(n=14,old_mean_mm_per_px=oldmean.tolist(),previous_rounded_mean_mm_per_px=previous_scales.tolist(),metrosert_mean_mm_per_px=newmean.tolist(),relative_correction_percent=((newmean/previous_scales-1)*100).tolist(),per_scan_mm_per_px=new_scales.tolist(),per_scan_sample_covariance=scan_cov.tolist(),per_scan_sample_sd=np.sqrt(np.diag(scan_cov)).tolist(),certificate_common_shift_mm_per_px=cert_shift.tolist(),relative_certificate_covariance=rel_cert_cov.tolist(),relative_transfer_covariance=rel_scan_cov.tolist()),photo_fit=dict(homography=H.tolist(),n=len(pix),rms_mm=float(np.sqrt(np.mean(np.sum(residual**2,axis=1)))),heldout_rms_mm=float(np.sqrt(np.mean(np.sum(held**2,axis=1)))),heldout_n=int(hold.sum()),block_deletion=blockresults,block_deletion_max_absolute_change_length_width_area=np.max(np.abs([r['change_from_full_fit'] for r in blockresults]),axis=0).tolist()),annotation_values=data.tolist(),previous_annotation_values=olddata.tolist(),reference_statistics=stat,reference_derivative_wrt_relative_physical_axes=J.tolist(),conditional_budget=dict(certificate_standard_component=np.sqrt(np.diag(Ccert)).tolist(),scanner_transfer_standard_component=np.sqrt(np.diag(Cscan)).tolist(),annotation_single_standard_component=np.sqrt(np.diag(Cann)).tolist(),annotation_mean_standard_component=np.sqrt(np.diag(Cann/5)).tolist(),u_reference_mean=np.sqrt(np.diag(Cmean)).tolist(),u_reference_single=np.sqrt(np.diag(Csingle)).tolist(),reference_mean_covariance=Cmean.tolist(),reference_single_covariance=Csingle.tolist(),scope='Quantified components only; excludes mapping model inadequacy, plane/pose mismatch, unmeasured local glass errors and common annotation bias. Spatial block-deletion results are sensitivity checks, not a fitted uncertainty term.'),checks=dict(original_annotation_values_reproduced=True,all_annotation_boundaries_valid=True,input_hashes_verified=True,uniform_scale_law_verified=True,model_evaluated=False),reference_sensitivity=sensitivity)
 dump('reference_budget.json',result)
 print('New scanner scales',newmean,'relative correction %',result['scanner']['relative_correction_percent']);print('Mean values',data.mean(0));print('Conditional u mean',result['conditional_budget']['u_reference_mean']);print('Certificate u',result['conditional_budget']['certificate_standard_component']);print('Scanner transfer u',result['conditional_budget']['scanner_transfer_standard_component']);print('Block deletion max changes',result['photo_fit']['block_deletion_max_absolute_change_length_width_area'])
if __name__=='__main__':main()
