"""Geometric reference and single-image frozen-model comparison for IMG_8184."""
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
